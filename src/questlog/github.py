"""Read GitHub activity through the authenticated ``gh`` CLI."""

import json
import re
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from questlog.models import Activity, DiscussionAnswer, Issue, OwnedRepo, PullRequest

_PAGE_SIZE = 100
_SEARCH_LIMIT = 1000
_SEARCH_ATTEMPTS = 3
_START = datetime(1970, 1, 1, tzinfo=UTC)
_SECOND = timedelta(seconds=1)
_SEARCH_QUERY = """query($search: String!, $first: Int!, $after: String) {
  search(query: $search, type: ISSUE, first: $first, after: $after) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      __typename
      ... on PullRequest {
        id number createdAt closedAt mergedAt
        repository { nameWithOwner }
        reviews(first: $first) {
          nodes { state submittedAt }
          pageInfo { hasNextPage endCursor }
        }
      }
      ... on Issue {
        id number createdAt closedAt
        repository { nameWithOwner }
      }
    }
  }
}
"""
_REVIEWS_QUERY = """query($id: ID!, $first: Int!, $after: String) {
  node(id: $id) {
    ... on PullRequest {
      reviews(first: $first, after: $after) {
        nodes { state submittedAt }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""
_DISCUSSIONS_QUERY = """query($login: String!, $first: Int!, $after: String) {
  user(login: $login) {
    repositoryDiscussionComments(onlyAnswers: true, first: $first, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes {
        createdAt
        discussion { number repository { nameWithOwner } }
      }
    }
  }
}
"""
_OWNED_REPOS_QUERY = """query($login: String!, $first: Int!) {
  user(login: $login) {
    repositories(
      ownerAffiliations: OWNER, first: $first, orderBy: {field: STARGAZERS, direction: DESC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes { nameWithOwner stargazerCount }
    }
  }
}
"""


class GitHubError(RuntimeError):
    """The CLI or API could not provide complete activity."""


class _SearchChanged(Exception):
    """A search window must be restarted because its result count changed."""


def gh_json(args: list[str]) -> dict | list:
    """Run ``gh`` without a shell and decode one JSON response.

    Authentication is supplied by the user's existing GitHub CLI session.
    CLI diagnostics are classified rather than echoed, to avoid exposing secrets.
    """
    try:
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=60, check=False
        )
    except FileNotFoundError as exc:
        raise GitHubError(
            "GitHub CLI 'gh' is missing. Install it and run 'gh auth login'."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise GitHubError("GitHub request timed out. Check your connection and try again.") from exc
    except OSError as exc:
        raise GitHubError("Could not execute the GitHub CLI. Check your gh installation.") from exc
    if result.returncode:
        diagnostic = result.stderr.lower()
        if "rate limit" in diagnostic:
            raise GitHubError("GitHub API rate limit reached. Wait for the limit to reset.")
        if result.returncode == 4 or any(
            text in diagnostic
            for text in ("auth login", "not logged", "bad credentials", "http 401")
        ):
            raise GitHubError("GitHub authentication failed. Run 'gh auth login' and try again.")
        raise GitHubError(
            f"GitHub request failed (gh exit {result.returncode}). "
            "Check your connection, repository access and 'gh auth status'."
        )
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise GitHubError("GitHub CLI returned invalid JSON.") from exc
    if not isinstance(data, (dict, list)):
        raise GitHubError("GitHub CLI returned an unexpected JSON value.")
    return data


def _object(value: object) -> dict:
    if not isinstance(value, dict):
        raise GitHubError("GitHub returned an invalid response object.")
    return value


def _nodes(connection: dict) -> list[dict]:
    value = connection["nodes"]
    if not isinstance(value, list) or any(not isinstance(node, dict) for node in value):
        raise GitHubError("GitHub returned an invalid or inaccessible result node.")
    return value


def _graphql(run: Callable, query: str, **variables: str | int) -> dict:
    args = ["api", "graphql", "-f", f"query={query}", "-F", f"first={_PAGE_SIZE}"]
    for name, value in variables.items():
        args.extend(["-f", f"{name}={value}"])
    result = _object(run(args))
    if result.get("errors"):
        raise GitHubError("GitHub GraphQL returned errors; activity may be incomplete. Try again.")
    return _object(result["data"])


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise GitHubError("GitHub returned a missing or invalid timestamp.")
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            raise ValueError("missing timezone")
        return parsed.astimezone(UTC)
    except ValueError as exc:
        raise GitHubError("GitHub returned a timestamp without a valid timezone.") from exc


def _optional_timestamp(value: object) -> datetime | None:
    return None if value is None else _timestamp(value)


def _next_cursor(connection: dict, seen: set[str]) -> str | None:
    info = _object(connection["pageInfo"])
    if info["hasNextPage"] is False:
        return None
    cursor = info["endCursor"]
    if (
        info["hasNextPage"] is not True
        or not isinstance(cursor, str)
        or not cursor
        or cursor in seen
    ):
        raise GitHubError("GitHub pagination did not advance; activity may be incomplete.")
    seen.add(cursor)
    return cursor


def _search_window(query: str, start: datetime, end: datetime, run: Callable) -> list[dict]:
    for _ in range(_SEARCH_ATTEMPTS):
        try:
            return _search_window_once(query, start, end, run)
        except _SearchChanged:
            # Restart with fresh nodes and cursors, leaving completed sibling
            # windows alone. Other errors must not consume another retry budget.
            continue
    raise GitHubError(
        f"GitHub activity changed during pagination after {_SEARCH_ATTEMPTS} attempts. Try again."
    )


def _search_window_once(query: str, start: datetime, end: datetime, run: Callable) -> list[dict]:
    search = f"{query} created:{start.isoformat()}..{end.isoformat()} sort:created-asc"
    connection = _object(_graphql(run, _SEARCH_QUERY, search=search)["search"])
    count = connection["issueCount"]
    if type(count) is not int or count < 0:
        raise GitHubError("GitHub returned an invalid search count.")
    # Search exposes only the first 1,000 matches. Split before reaching the cap,
    # preserving inclusive second-resolution boundaries without overlaps.
    if count >= _SEARCH_LIMIT:
        seconds = int((end - start).total_seconds())
        if seconds < 1:
            raise GitHubError("Too many results in one second to read complete GitHub activity.")
        middle = start + timedelta(seconds=seconds // 2)
        return _search_window(query, start, middle, run) + _search_window(
            query, middle + _SECOND, end, run
        )
    nodes = []
    cursors: set[str] = set()
    while True:
        if connection["issueCount"] != count:
            raise _SearchChanged
        nodes.extend(_nodes(connection))
        after = _next_cursor(connection, cursors)
        if after is None:
            break
        connection = _object(_graphql(run, _SEARCH_QUERY, search=search, after=after)["search"])
    if len(nodes) != count:
        raise GitHubError("GitHub returned incomplete search results. Try again.")
    return nodes


def _reviewed(node: dict, merged_at: datetime | None, run: Callable) -> bool:
    connection = _object(node["reviews"])
    cursors: set[str] = set()
    while True:
        for review in _nodes(connection):
            state = review["state"]
            if not isinstance(state, str) or not state:
                raise GitHubError("GitHub returned an invalid review state.")
            if state == "PENDING":
                continue
            submitted = _timestamp(review["submittedAt"])
            if merged_at is None or submitted <= merged_at:
                return True
        after = _next_cursor(connection, cursors)
        if after is None:
            return False
        data = _graphql(run, _REVIEWS_QUERY, id=node["id"], after=after)
        connection = _object(_object(data["node"])["reviews"])


def _discussion_answers(login: str, run: Callable) -> list[DiscussionAnswer]:
    """Collect the discussion answers the user wrote that GitHub accepted.

    ``onlyAnswers`` means every node is already an accepted answer. A
    discussion holds a single accepted answer, so ``(repo, number)`` identifies
    one uniquely; seeing it twice means the response cannot be trusted.
    """
    answers: list[DiscussionAnswer] = []
    seen: set[tuple[str, int]] = set()
    cursors: set[str] = set()
    try:
        data = _graphql(run, _DISCUSSIONS_QUERY, login=login)
        connection = _object(_object(data["user"])["repositoryDiscussionComments"])
        while True:
            for node in _nodes(connection):
                discussion = _object(node["discussion"])
                repo = _object(discussion["repository"])["nameWithOwner"]
                number = discussion["number"]
                if not isinstance(repo, str) or not repo or type(number) is not int or number < 1:
                    raise GitHubError("GitHub returned invalid discussion identifiers.")
                if (repo, number) in seen:
                    raise GitHubError("GitHub returned a duplicate accepted discussion answer.")
                seen.add((repo, number))
                answers.append(DiscussionAnswer(repo, number, _timestamp(node["createdAt"])))
            after = _next_cursor(connection, cursors)
            if after is None:
                break
            data = _graphql(run, _DISCUSSIONS_QUERY, login=login, after=after)
            connection = _object(_object(data["user"])["repositoryDiscussionComments"])
    except (KeyError, TypeError) as exc:
        raise GitHubError("GitHub returned an incomplete discussion response.") from exc
    return answers


def _owned_repos(login: str, run: Callable) -> tuple[OwnedRepo, ...]:
    """Collect the repositories the user owns, most stars first.

    One bounded page is the whole story by design: the first node holds the
    most stars of any repository the user owns, which is all any rule needs.
    Forks count because they are repositories the user owns. A repeated
    repository name means the response cannot be trusted.
    """
    repos: list[OwnedRepo] = []
    seen: set[str] = set()
    try:
        connection = _object(
            _object(_graphql(run, _OWNED_REPOS_QUERY, login=login)["user"])["repositories"]
        )
        for node in _nodes(connection):
            name = node["nameWithOwner"]
            stars = node["stargazerCount"]
            if not isinstance(name, str) or not name or type(stars) is not int or stars < 0:
                raise GitHubError("GitHub returned invalid repository data.")
            if name in seen:
                raise GitHubError("GitHub returned a duplicate owned repository.")
            seen.add(name)
            repos.append(OwnedRepo(name, stars))
    except (KeyError, TypeError) as exc:
        raise GitHubError("GitHub returned an incomplete owned-repositories response.") from exc
    return tuple(repos)


def fetch_activity(login: str, run: Callable[[list[str]], dict | list] = gh_json) -> Activity:
    """Collect authored PRs, closed issues, accepted answers and owned repositories.

    Search uses creation-time windows below GitHub's 1,000-result cap. Lifecycle
    data and the first review page are batched in each GraphQL search request;
    only overflowing review connections need follow-up requests. ``reviewed``
    means any submitted review except PENDING (including comments/dismissals).
    For merged PRs, only reviews submitted at or before the merge count.
    A search window whose result count changes is restarted at most twice.
    Owned repositories arrive in one bounded page, most stars first.
    All timestamps are aware UTC. Incomplete API responses raise GitHubError.
    """
    if not isinstance(login, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", login):
        raise ValueError("Enter a GitHub login using letters, numbers and hyphens.")
    until = datetime.now(UTC).replace(microsecond=0)
    pulls = []
    issues = []
    identities: set[str] = set()
    try:
        for kind in ("is:pr", "is:issue is:closed"):
            for node in _search_window(f"author:{login} {kind}", _START, until, run):
                identity = node["id"]
                if not isinstance(identity, str) or not identity or identity in identities:
                    raise GitHubError("GitHub returned duplicate or invalid activity identifiers.")
                identities.add(identity)
                repo = _object(node["repository"])["nameWithOwner"]
                number = node["number"]
                if not isinstance(repo, str) or not repo or type(number) is not int or number < 1:
                    raise GitHubError("GitHub returned invalid repository or item identifiers.")
                created = _timestamp(node["createdAt"])
                closed = _optional_timestamp(node["closedAt"])
                if kind == "is:pr" and node["__typename"] == "PullRequest":
                    merged = _optional_timestamp(node["mergedAt"])
                    pulls.append(
                        PullRequest(
                            repo, number, created, closed, merged, _reviewed(node, merged, run)
                        )
                    )
                elif kind == "is:issue is:closed" and node["__typename"] == "Issue" and closed:
                    issues.append(Issue(repo, number, created, closed))
                else:
                    raise GitHubError("GitHub returned an unexpected item for the activity search.")
    except (KeyError, TypeError) as exc:
        raise GitHubError("GitHub returned an incomplete activity response.") from exc
    answers = _discussion_answers(login, run)
    repos = _owned_repos(login, run)
    return Activity(
        login,
        tuple(sorted(pulls, key=lambda item: (item.created_at, item.repo, item.number))),
        tuple(sorted(issues, key=lambda item: (item.created_at, item.repo, item.number))),
        tuple(sorted(answers, key=lambda item: (item.created_at, item.repo, item.number))),
        repos,
    )
