"""Offline replays of recorded responses, plus explicit synthetic edge cases."""

import copy
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from questlog import github
from questlog.github import GitHubError, fetch_activity, gh_json

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def prohibit_subprocesses(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Tests must not execute gh or access the network")

    monkeypatch.setattr(subprocess, "run", forbidden)


def variables(args):
    assert args[:2] == ["api", "graphql"]
    assert len(args[2:]) % 2 == 0
    result = {}
    for flag, field in zip(args[2::2], args[3::2], strict=True):
        assert flag in ("-f", "-F")
        name, value = field.split("=", 1)
        result[name] = value
    return result


class Replay:
    def __init__(self):
        self.pages = {
            "first": fixture("graphql-prs-page-1.json"),
            "second": fixture("graphql-prs-page-2.json"),
            "issues": fixture("graphql-issues-page-1.json"),
        }
        self.discussion_pages = [fixture("graphql-discussion-answers-page-1.json")]
        self.discussion_login = "ixiion001"
        self.owned_pages = [fixture("graphql-owned-repos-page-1.json")]
        self.calls = []
        self.review_page = None

    def __call__(self, args):
        value = variables(args)
        self.calls.append(value)
        if "id" in value:
            assert self.review_page is not None
            return copy.deepcopy(self.review_page)
        if "login" in value:
            if "stargazerCount" in value["query"]:
                page = self.owned_pages[0]
                if len(self.owned_pages) > 1:
                    self.owned_pages.pop(0)
                return copy.deepcopy(page)
            assert value["login"] == self.discussion_login
            page = self.discussion_pages[0]
            if len(self.discussion_pages) > 1:
                self.discussion_pages.pop(0)
            return copy.deepcopy(page)
        assert "author:ixiion001" in value["search"]
        assert "created:" in value["search"]
        assert "sort:created-asc" in value["search"]
        assert "is:public" not in value["search"]
        if "is:issue" in value["search"]:
            assert "is:closed" in value["search"]
            key = "issues"
        elif "after" in value:
            assert value["after"] == "Y3Vyc29yOjI="
            key = "second"
        else:
            key = "first"
        return copy.deepcopy(self.pages[key])


def test_recorded_activity_is_batched_paginated_and_utc(monkeypatch):
    monkeypatch.setattr(github, "_PAGE_SIZE", 2)
    run = Replay()
    activity = fetch_activity("ixiion001", run)
    assert activity.login == "ixiion001"
    assert len(activity.pull_requests) == 4
    opened, merged, closed, second_open = activity.pull_requests
    assert opened.repo == "isaiahbjork/Auto-GPT-Crypto-Plugin"
    assert opened.number == 6
    assert opened.closed_at is opened.merged_at is None
    assert merged.repo == "ixiion001/openai-filesearch-mcp"
    assert merged.merged_at == datetime(2025, 5, 17, 0, 35, 46, tzinfo=UTC)
    assert merged.closed_at == merged.merged_at
    assert closed.closed_at is not None and closed.merged_at is None
    assert second_open.closed_at is None
    assert all(not pr.reviewed for pr in activity.pull_requests)
    assert len(activity.issues) == 1
    assert activity.issues[0].repo == "Aider-AI/aider"
    assert activity.issues[0].number == 170
    assert activity.issues[0].closed_at == datetime(2023, 9, 27, 17, 30, 22, tzinfo=UTC)
    assert all(
        item.created_at.tzinfo is UTC for item in (*activity.pull_requests, *activity.issues)
    )
    # Two PR pages, one issue page, one discussion page and one owned-repos
    # page; no per-PR calls.
    assert len(run.calls) == 5
    assert not [call for call in run.calls if "id" in call]
    assert all(call["first"] == "2" for call in run.calls)


@pytest.mark.parametrize(
    ("state", "submitted", "expected"),
    [
        ("PENDING", None, False),
        ("COMMENTED", "2025-05-17T00:35:45Z", True),
        ("DISMISSED", "2025-05-17T00:35:46Z", True),
        ("CHANGES_REQUESTED", "2025-05-17T00:35:45Z", True),
        ("APPROVED", "2025-05-17T00:35:47Z", False),
    ],
)
def test_synthetic_review_states_respect_merge_time(state, submitted, expected):
    run = Replay()
    merged = run.pages["first"]["data"]["search"]["nodes"][1]
    merged["reviews"]["nodes"] = [{"state": state, "submittedAt": submitted}]
    assert fetch_activity("ixiion001", run).pull_requests[1].reviewed is expected


def test_open_pr_counts_submitted_review_and_normalizes_timezone():
    run = Replay()
    opened = run.pages["first"]["data"]["search"]["nodes"][0]
    opened["createdAt"] = "2023-05-14T15:22:56+02:00"
    opened["reviews"]["nodes"] = [{"state": "APPROVED", "submittedAt": "2025-01-01T00:00:00Z"}]
    pr = fetch_activity("ixiion001", run).pull_requests[0]
    assert pr.reviewed is True
    assert pr.created_at == datetime(2023, 5, 14, 13, 22, 56, tzinfo=UTC)


def test_synthetic_reviews_paginate_until_a_submitted_review_is_found():
    run = Replay()
    merged = run.pages["first"]["data"]["search"]["nodes"][1]
    merged["reviews"] = {
        "nodes": [{"state": "PENDING"}],
        "pageInfo": {"hasNextPage": True, "endCursor": "review-page-1"},
    }
    run.review_page = {
        "data": {
            "node": {
                "reviews": {
                    "nodes": [{"state": "COMMENTED", "submittedAt": merged["mergedAt"]}],
                    "pageInfo": {"hasNextPage": False, "endCursor": "review-page-2"},
                }
            }
        }
    }
    assert fetch_activity("ixiion001", run).pull_requests[1].reviewed
    calls = [call for call in run.calls if "id" in call]
    assert len(calls) == 1
    assert calls[0]["id"] == merged["id"]
    assert calls[0]["after"] == "review-page-1"


def test_existing_qualifying_review_needs_no_further_pages():
    run = Replay()
    pr = run.pages["first"]["data"]["search"]["nodes"][0]
    pr["reviews"] = {
        "nodes": [{"state": "COMMENTED", "submittedAt": pr["createdAt"]}],
        "pageInfo": {"hasNextPage": True, "endCursor": "more"},
    }
    assert fetch_activity("ixiion001", run).pull_requests[0].reviewed
    # The batched review was enough, so no per-node review query is sent.
    assert not [call for call in run.calls if "id" in call]
    assert len(run.calls) == 5


def response(nodes, count=None, has_next=False, cursor=None):
    return {
        "data": {
            "search": {
                "nodes": nodes,
                "issueCount": len(nodes) if count is None else count,
                "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
            }
        }
    }


def window(search):
    dates = next(
        word.removeprefix("created:") for word in search.split() if word.startswith("created:")
    )
    start, end = dates.split("..")
    return datetime.fromisoformat(start), datetime.fromisoformat(end)


@pytest.mark.parametrize("count", [1000, 1001])
def test_fixture_derived_large_history_splits_windows_without_dropping_records(count):
    # Synthetic volume based on a recorded PR; no extra fixtures pretend to be real.
    base = fixture("graphql-prs-page-1.json")["data"]["search"]["nodes"][0]
    start = datetime(2024, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(count):
        node = copy.deepcopy(base)
        node.update(
            id=f"synthetic-{index}",
            number=index + 1,
            createdAt=(start + timedelta(seconds=index)).isoformat(),
        )
        rows.append(node)
    ranges = []

    def run(args):
        value = variables(args)
        if "login" in value:
            if "stargazerCount" in value["query"]:
                return fixture("graphql-owned-repos-page-1.json")
            return fixture("graphql-discussion-answers-page-1.json")
        if "is:issue" in value["search"]:
            return response([])
        lower, upper = window(value["search"])
        matches = [
            row for row in rows if lower <= datetime.fromisoformat(row["createdAt"]) <= upper
        ]
        offset = int(value.get("after", "0"))
        page_size = int(value["first"])
        page = matches[offset : offset + page_size]
        has_next = offset + len(page) < len(matches)
        ranges.append((lower, upper, len(matches)))
        return response(page, len(matches), has_next, str(offset + len(page)))

    result = fetch_activity("ixiion001", run)
    assert len(result.pull_requests) == count
    assert {pr.number for pr in result.pull_requests} == set(range(1, count + 1))
    assert any(total >= 1000 for _, _, total in ranges)
    assert any(0 < total < 1000 for _, _, total in ranges)


def test_split_second_boundary_has_no_gap_or_overlap():
    base = fixture("graphql-prs-page-1.json")["data"]["search"]["nodes"]
    start = datetime(2024, 1, 1, tzinfo=UTC)
    calls = []

    def run(args):
        bounds = window(variables(args)["search"])
        calls.append(bounds)
        if len(calls) == 1:
            return response(base, 1000)
        return response([base[len(calls) - 2]])

    assert len(github._search_window("is:pr", start, start + timedelta(seconds=3), run)) == 2
    assert calls[1:] == [
        (start, start + timedelta(seconds=1)),
        (start + timedelta(seconds=2), start + timedelta(seconds=3)),
    ]


def test_unsplittable_search_fails_instead_of_truncating():
    stamp = datetime(2024, 1, 1, tzinfo=UTC)
    with pytest.raises(GitHubError, match="one second"):
        github._search_window("is:pr", stamp, stamp, lambda _: response([], 1000))


@pytest.mark.parametrize(
    "problem", ["partial", "graphql", "duplicate", "naive", "null-node", "count-change", "cursor"]
)
def test_incomplete_or_invalid_activity_is_not_reported_as_success(problem):
    run = Replay()
    first = run.pages["first"]["data"]["search"]
    second = run.pages["second"]["data"]["search"]
    if problem == "partial":
        first["pageInfo"]["hasNextPage"] = False
    elif problem == "graphql":
        run.pages["first"]["errors"] = [{"message": "timed out"}]
    elif problem == "duplicate":
        second["nodes"][0] = copy.deepcopy(first["nodes"][0])
    elif problem == "naive":
        first["nodes"][0]["createdAt"] = "2023-05-14T13:22:56"
    elif problem == "null-node":
        first["nodes"][0] = None
    elif problem == "count-change":
        second["issueCount"] = 5
    elif problem == "cursor":
        second["pageInfo"] = copy.deepcopy(first["pageInfo"])
    with pytest.raises(GitHubError):
        fetch_activity("ixiion001", run)


def test_review_pagination_does_not_loop_on_repeated_cursor():
    run = Replay()
    pr = run.pages["first"]["data"]["search"]["nodes"][0]
    pr["reviews"] = {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "same"}}
    run.review_page = {"data": {"node": {"reviews": copy.deepcopy(pr["reviews"])}}}
    with pytest.raises(GitHubError, match="pagination"):
        fetch_activity("ixiion001", run)


@pytest.mark.parametrize(
    "value", [{}, {"data": {"search": None}}, {"data": {"search": {"issueCount": True}}}]
)
def test_missing_response_fields_raise_actionable_error(value):
    with pytest.raises(GitHubError):
        fetch_activity("ixiion001", lambda _: value)


@pytest.mark.parametrize("login", ["", "user is:merged", "-f", "owner/repo", None])
def test_invalid_login_never_calls_cli(login):
    def run(_):
        pytest.fail("Invalid login must fail before reading GitHub")

    with pytest.raises(ValueError, match="login"):
        fetch_activity(login, run)


@pytest.mark.parametrize("value", [{"data": {}}, []])
def test_gh_json_decodes_cli_output_without_a_shell(monkeypatch, value):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps(value), stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    assert gh_json(["api", "graphql", "-f", "query={viewer{login}}"]) == value
    assert calls[0][0] == ["gh", "api", "graphql", "-f", "query={viewer{login}}"]
    assert calls[0][1] == {"capture_output": True, "text": True, "timeout": 60, "check": False}


@pytest.mark.parametrize(
    ("code", "out", "err", "message"),
    [
        (4, "", "", "authentication"),
        (1, "", "run gh auth login", "authentication"),
        (1, "", "HTTP 401 Bad credentials", "authentication"),
        (1, "", "API rate limit exceeded", "rate limit"),
        (1, "", "HTTP 403 Access denied; sensitive diagnostic", "repository access"),
        (0, "invalid", "", "invalid JSON"),
        (0, "null", "", "unexpected JSON"),
    ],
)
def test_cli_failures_are_clear_without_echoing_diagnostics(monkeypatch, code, out, err, message):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=code, stdout=out, stderr=err)
    )
    with pytest.raises(GitHubError, match=message) as caught:
        gh_json(["api", "graphql"])
    assert "sensitive diagnostic" not in str(caught.value)


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (FileNotFoundError(), "missing"),
        (subprocess.TimeoutExpired("gh", 60), "timed out"),
        (PermissionError(), "execute"),
    ],
)
def test_cli_execution_errors(monkeypatch, error, message):
    def run(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(GitHubError, match=message):
        gh_json(["api", "graphql"])


@pytest.mark.parametrize("changes", [1, 2])
def test_recorded_search_recovers_from_count_changes_without_stale_results(changes):
    recorded = Replay()
    attempts = 0

    def run(args):
        nonlocal attempts
        value = variables(args)
        page = recorded(args)
        if "search" in value and "is:pr" in value["search"]:
            if "after" not in value:
                attempts += 1
                if attempts <= changes:
                    page["data"]["search"]["nodes"][0]["number"] = 999999
            elif attempts <= changes:
                page["data"]["search"]["issueCount"] += 1
        return page

    result = fetch_activity("ixiion001", run)
    assert attempts == changes + 1
    assert [pr.number for pr in result.pull_requests] == [6, 1, 1, 2]
    assert len(result.issues) == 1
    searches = [call for call in recorded.calls if "search" in call and "is:pr" in call["search"]]
    assert len(searches) == 2 * (changes + 1)
    assert len({call["search"] for call in searches}) == 1
    assert ["after" in call for call in searches] == [False, True] * (changes + 1)
    # The PR pages above, one issue page, one discussion page and one
    # owned-repos page.
    assert len(recorded.calls) == 2 * (changes + 1) + 3


def test_changing_search_stops_after_three_attempts():
    recorded = Replay()
    recorded.pages["second"]["data"]["search"]["issueCount"] += 1
    with pytest.raises(GitHubError, match="changed during pagination.*3 attempts"):
        fetch_activity("ixiion001", recorded)
    # The search fails before the discussion and owned-repos pages are ever
    # requested.
    assert len(recorded.calls) == 6
    assert not [call for call in recorded.calls if "login" in call]
    assert all("is:pr" in call["search"] for call in recorded.calls)
    assert ["after" in call for call in recorded.calls] == [False, True] * 3


@pytest.mark.parametrize("keeps_changing", [False, True])
def test_only_changing_child_window_restarts(keeps_changing):
    recorded = Replay()
    nodes = recorded.pages["first"]["data"]["search"]["nodes"]
    second_nodes = recorded.pages["second"]["data"]["search"]["nodes"]
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = start + timedelta(seconds=3)
    left = (start, start + timedelta(seconds=1))
    right = (start + timedelta(seconds=2), end)
    calls = []
    attempts = 0

    def run(args):
        nonlocal attempts
        value = variables(args)
        bounds = window(value["search"])
        calls.append(bounds)
        if bounds == (start, end):
            return response([], 1000)
        if bounds == left:
            assert "after" not in value
            return response(nodes)
        assert bounds == right
        if "after" not in value:
            attempts += 1
            return response(second_nodes[:1], 2, True, "right-first")
        assert value["after"] == "right-first"
        changed = keeps_changing or attempts == 1
        return response(second_nodes[1:], 3 if changed else 2)

    if keeps_changing:
        with pytest.raises(GitHubError, match="3 attempts"):
            github._search_window("is:pr", start, end, run)
        assert attempts == 3
    else:
        result = github._search_window("is:pr", start, end, run)
        assert result == nodes + second_nodes
        assert attempts == 2
    assert calls == [(start, end), left] + [right] * (2 * attempts)


def test_graphql_failure_is_not_retried():
    recorded = Replay()
    recorded.pages["second"]["errors"] = [{"message": "rate limit exceeded"}]
    with pytest.raises(GitHubError, match="GraphQL returned errors"):
        fetch_activity("ixiion001", recorded)
    assert len(recorded.calls) == 2


def answers_page(nodes, has_next=False, cursor=None):
    # Synthetic variation shaped from the recorded empty page: that account has
    # no accepted answers, so real responses carry no nodes to replay.
    return {
        "data": {
            "user": {
                "repositoryDiscussionComments": {
                    "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                    "nodes": nodes,
                }
            }
        }
    }


def answer(repo, number, created="2026-02-03T09:15:00Z"):
    return {
        "createdAt": created,
        "discussion": {"number": number, "repository": {"nameWithOwner": repo}},
    }


def one_node(discussion, created="2026-02-03T09:15:00Z"):
    """A single-answer response whose discussion and timestamp the caller controls."""
    return answers_page([{"createdAt": created, "discussion": discussion}])


def test_recorded_account_has_no_accepted_discussion_answers():
    run = Replay()
    assert fetch_activity("ixiion001", run).discussion_answers == ()
    asked = [call for call in run.calls if "repositoryDiscussionComments" in call["query"]]
    assert len(asked) == 1
    assert asked[0]["login"] == "ixiion001"
    assert "after" not in asked[0]


def test_recorded_accepted_answers_are_parsed_across_two_pages(monkeypatch):
    monkeypatch.setattr(github, "_PAGE_SIZE", 2)
    run = Replay()
    run.discussion_login = "answerer"
    pages = [
        fixture("graphql-discussion-answers-account-page-1.json"),
        fixture("graphql-discussion-answers-account-page-2.json"),
    ]
    # The account has 233 accepted answers, so a real capture is never the last
    # page. Only this termination flag is synthetic; every node below is real.
    pages[-1]["data"]["user"]["repositoryDiscussionComments"]["pageInfo"]["hasNextPage"] = False
    run.discussion_pages = pages

    # Replayed straight through the reader: the search side of the harness is
    # recorded for ixiion001 and says nothing about discussion answers.
    answers = github._discussion_answers("answerer", run)
    assert [(item.repo, item.number) for item in answers] == [
        ("dotnet/csharplang", 2628),
        ("dotnet/roslyn", 49101),
        ("dotnet/runtime", 43941),
        ("dotnet/runtime", 43883),
    ]
    assert answers[0].created_at == datetime(2019, 7, 3, 12, 42, 47, tzinfo=UTC)
    assert all(item.created_at.tzinfo is UTC for item in answers)
    asked = [call for call in run.calls if "repositoryDiscussionComments" in call["query"]]
    assert [call.get("after") for call in asked] == [None, "Y3Vyc29yOnYyOpHOAAHNSQ=="]


def test_accepted_answers_are_paginated_sorted_and_utc(monkeypatch):
    monkeypatch.setattr(github, "_PAGE_SIZE", 2)
    run = Replay()
    run.discussion_pages = [
        answers_page(
            [answer("b/repo", 2, "2026-05-01T10:00:00+02:00"), answer("a/repo", 9)],
            has_next=True,
            cursor="Y3Vyc29yOjE=",
        ),
        answers_page([answer("a/repo", 1, "2025-12-31T23:00:00Z")]),
    ]
    activity = fetch_activity("ixiion001", run)
    assert [(item.repo, item.number) for item in activity.discussion_answers] == [
        ("a/repo", 1),
        ("a/repo", 9),
        ("b/repo", 2),
    ]
    assert all(item.created_at.tzinfo is UTC for item in activity.discussion_answers)
    assert activity.discussion_answers[0].created_at == datetime(2025, 12, 31, 23, tzinfo=UTC)
    assert activity.discussion_answers[2].created_at == datetime(2026, 5, 1, 8, tzinfo=UTC)
    asked = [call for call in run.calls if "repositoryDiscussionComments" in call["query"]]
    assert [call.get("after") for call in asked] == [None, "Y3Vyc29yOjE="]
    assert all(call["first"] == "2" for call in asked)


def test_duplicate_accepted_answer_is_rejected():
    run = Replay()
    run.discussion_pages = [answers_page([answer("a/repo", 4), answer("a/repo", 4)])]
    with pytest.raises(GitHubError, match="duplicate accepted discussion answer"):
        fetch_activity("ixiion001", run)


def test_same_number_in_two_repositories_is_not_a_duplicate():
    run = Replay()
    run.discussion_pages = [answers_page([answer("a/repo", 4), answer("b/repo", 4)])]
    answers = fetch_activity("ixiion001", run).discussion_answers
    assert [(item.repo, item.number) for item in answers] == [("a/repo", 4), ("b/repo", 4)]


def test_discussion_pagination_does_not_loop_on_repeated_cursor():
    run = Replay()
    run.discussion_pages = [
        answers_page([answer("a/repo", 1)], has_next=True, cursor="same"),
        answers_page([], has_next=True, cursor="same"),
    ]
    with pytest.raises(GitHubError, match="pagination did not advance"):
        fetch_activity("ixiion001", run)


@pytest.mark.parametrize(
    ("problem", "message"),
    [
        ({"data": {"user": {}}}, "incomplete discussion response"),
        (
            {"data": {"user": {"repositoryDiscussionComments": {"nodes": [], "pageInfo": {}}}}},
            "incomplete discussion response",
        ),
        (
            one_node({"number": 7, "repository": {"nameWithOwner": "a/repo"}}, created=None),
            "missing or invalid timestamp",
        ),
        (
            one_node({"number": 7, "repository": {"nameWithOwner": "a/repo"}}, created="x"),
            "without a valid timezone",
        ),
        (
            one_node(
                {"number": 7, "repository": {"nameWithOwner": "a/repo"}},
                created="2026-05-01T10:00:00",
            ),
            "without a valid timezone",
        ),
        (
            one_node({"number": 0, "repository": {"nameWithOwner": "a/repo"}}),
            "invalid discussion identifiers",
        ),
        (
            one_node({"number": -1, "repository": {"nameWithOwner": "a/repo"}}),
            "invalid discussion identifiers",
        ),
        (
            one_node({"number": "7", "repository": {"nameWithOwner": "a/repo"}}),
            "invalid discussion identifiers",
        ),
        (
            one_node({"number": 7, "repository": {"nameWithOwner": ""}}),
            "invalid discussion identifiers",
        ),
        (one_node({"number": 7, "repository": {}}), "incomplete discussion response"),
        (one_node({"number": 7}), "incomplete discussion response"),
        (one_node({"number": 7, "repository": None}), "invalid response object"),
        (
            {"data": {"user": {"repositoryDiscussionComments": {"nodes": None, "pageInfo": {}}}}},
            "invalid or inaccessible result node",
        ),
    ],
)
def test_malformed_discussion_response_is_not_reported_as_success(problem, message):
    # Only the discussion request is malformed. Feeding the same payload to the
    # search would let the search reject it, and the case would pass for the
    # wrong reason while the discussion reader went untested.
    recorded = Replay()

    def run(args):
        value = variables(args)
        if "login" in value and "repositoryDiscussionComments" in value["query"]:
            return problem
        return recorded(args)

    with pytest.raises(GitHubError, match=message):
        fetch_activity("ixiion001", run)
    assert [call for call in recorded.calls if "search" in call]


def test_discussion_failures_are_not_hidden_by_the_activity_search():
    def run(args):
        value = variables(args)
        if "login" in value and "repositoryDiscussionComments" in value["query"]:
            return {"data": {}, "errors": [{"message": "bad credentials"}]}
        return Replay()(args)

    with pytest.raises(GitHubError, match="GraphQL returned errors"):
        fetch_activity("ixiion001", run)


def test_recorded_owned_repos_page_keeps_star_order_and_values():
    run = Replay()
    repos = fetch_activity("ixiion001", run).owned_repos
    assert [(repo.name, repo.stars) for repo in repos] == [
        ("octocat/Spoon-Knife", 14062),
        ("octocat/Hello-World", 3831),
        ("octocat/octocat.github.io", 1174),
        ("octocat/boysenberry-repo-1", 480),
    ]
    asked = [call for call in run.calls if "stargazerCount" in call["query"]]
    assert len(asked) == 1
    assert asked[0]["login"] == "ixiion001"


def test_owned_repos_stop_after_one_page_even_when_more_exist():
    # One bounded page is the design: the first node holds the most stars of
    # any repository the user owns, and no rule needs more. Later pages exist
    # in the API and are deliberately not requested.
    run = Replay()
    page = run.owned_pages[0]["data"]["user"]["repositories"]
    page["pageInfo"] = {"hasNextPage": True, "endCursor": "more-repos"}
    assert len(fetch_activity("ixiion001", run).owned_repos) == 4
    assert len([call for call in run.calls if "stargazerCount" in call["query"]]) == 1


def test_zero_star_repositories_count_and_forks_are_not_filtered():
    # Forks count because the query filters only on ownership; the absence of
    # any fork filter is the pin asked for in the second-opinion review.
    assert "isFork" not in github._OWNED_REPOS_QUERY
    run = Replay()
    run.owned_pages[0]["data"]["user"]["repositories"]["nodes"] = [
        {"nameWithOwner": "octocat/forked-thing", "stargazerCount": 0}
    ]
    repos = fetch_activity("ixiion001", run).owned_repos
    assert [(repo.name, repo.stars) for repo in repos] == [("octocat/forked-thing", 0)]


def test_empty_owned_repos_page_is_an_empty_tuple():
    run = Replay()
    run.owned_pages[0]["data"]["user"]["repositories"]["nodes"] = []
    assert fetch_activity("ixiion001", run).owned_repos == ()


@pytest.mark.parametrize(
    ("problem", "message"),
    [
        ({}, "incomplete owned-repositories response"),
        ({"data": {}}, "incomplete owned-repositories response"),
        ({"data": {"user": None}}, "invalid response object"),
        ({"data": {"user": {}}}, "incomplete owned-repositories response"),
        ({"data": {"user": {"repositories": None}}}, "invalid response object"),
        ({"data": {"user": {"repositories": {}}}}, "incomplete owned-repositories response"),
        ("bad-name", "invalid repository data"),
        ("empty-name", "invalid repository data"),
        ("invalid-stars", "invalid repository data"),
        ("negative-stars", "invalid repository data"),
        ("duplicate", "duplicate owned repository"),
        ("null-node", "invalid or inaccessible result node"),
    ],
)
def test_malformed_owned_repos_response_is_not_reported_as_success(problem, message):
    # Only the owned-repos request is malformed, so the search and discussion
    # readers cannot reject the payload first and mask the case.
    recorded = Replay()

    def run(args):
        value = variables(args)
        if "stargazerCount" in value["query"]:
            if not isinstance(problem, str):
                return problem
            page = recorded.owned_pages[0]
            nodes = page["data"]["user"]["repositories"]["nodes"]
            if problem == "bad-name":
                nodes[0]["nameWithOwner"] = 123
            elif problem == "empty-name":
                nodes[0]["nameWithOwner"] = ""
            elif problem == "invalid-stars":
                nodes[0]["stargazerCount"] = "many"
            elif problem == "negative-stars":
                nodes[0]["stargazerCount"] = -1
            elif problem == "duplicate":
                nodes[1] = copy.deepcopy(nodes[0])
            elif problem == "null-node":
                nodes[0] = None
            return copy.deepcopy(page)
        return recorded(args)

    with pytest.raises(GitHubError, match=message):
        fetch_activity("ixiion001", run)
    assert [call for call in recorded.calls if "search" in call]
