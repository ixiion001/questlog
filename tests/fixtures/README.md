# Recorded GitHub API fixtures

Captured on 2026-09-26 with the authenticated GitHub CLI. All samples are public
activity authored by `ixiion001`; no private repository data is included.
GraphQL selects only the identifiers, timestamps, review state and pagination
metadata used by the reader, preserving the returned values and counts.

The query is `_SEARCH_QUERY` in `src/questlog/github.py`. Each file is one real
`gh api graphql -f query=<query> -F first=2 -f search=<search>` response; subsequent
pages add `-f after=<cursor>`. The following are the exact variables:

```json
[
  {
    "file": "graphql-prs-page-1.json",
    "search": "author:ixiion001 is:pr is:public created:<2026-09-01 sort:created-asc",
    "first": 2,
    "after": null
  },
  {
    "file": "graphql-prs-page-2.json",
    "search": "author:ixiion001 is:pr is:public created:<2026-09-01 sort:created-asc",
    "first": 2,
    "after": "Y3Vyc29yOjI="
  },
  {
    "file": "graphql-issues-page-1.json",
    "search": "author:ixiion001 is:issue is:closed is:public sort:created-asc",
    "first": 2,
    "after": null
  }
]
```

The accepted-answers reader uses `_DISCUSSIONS_QUERY` in
`src/questlog/github.py`, with these variables:

```json
[
  {
    "file": "graphql-discussion-answers-page-1.json",
    "login": "ixiion001",
    "first": 2,
    "after": null
  }
]
```

This capture is empty and is the whole story for that account: `ixiion001` has
no discussion answers marked as accepted, so the real response has no nodes
and no next page. It pins the response envelope
(`data.user.repositoryDiscussionComments`) and the empty case. Discussion
answers with content, second pages, repeated cursors and duplicate answers are
synthetic variations in tests, shaped from this envelope, and are not claims
about real users.

Tests replay these files with page size 2. The PR sample includes open, merged,
and closed-unmerged PRs. None has submitted reviews; review states, overflowing
review connections, API failures, and high-volume search windows are explicitly
synthetic variations in tests rather than claims about these real users.
