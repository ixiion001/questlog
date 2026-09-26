# Recorded GitHub API fixtures

Captured on 2026-09-26 with the authenticated GitHub CLI. All samples are
public activity: most are authored by `ixiion001`, and the accepted-answers
pages come from `huoyaoyuan`, a public account used because `ixiion001` has no
accepted answers to capture. No private repository data is included.
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

`graphql-discussion-answers-page-1.json` is empty, and that is the whole story
for `ixiion001`: the account has no discussion answers marked as accepted, so
the real response has no nodes and no next page. It pins the response envelope
(`data.user.repositoryDiscussionComments`) and the empty case.

An empty capture cannot show that nodes parse, so the two page files below are
real captures for `huoyaoyuan`, a public account with accepted answers, using
the same query and page size 2:

```json
[
  {
    "file": "graphql-discussion-answers-account-page-1.json",
    "login": "huoyaoyuan",
    "first": 2,
    "after": null
  },
  {
    "file": "graphql-discussion-answers-account-page-2.json",
    "login": "huoyaoyuan",
    "first": 2,
    "after": "Y3Vyc29yOnYyOpHOAAHNSQ=="
  }
]
```

That account has 233 accepted answers, so no real capture is ever the last
page. The test therefore clears `hasNextPage` on the final page before
replaying it; that flag is the only synthetic part, and every node, repository
and timestamp in both files is a real value. The two pages span three
repositories, so they also cover the case where one number can be shared
between repositories.

Repeated cursors, duplicate answers and API failures are synthetic variations
in tests, shaped from these real responses, and are not claims about real
users.

Tests replay these files with page size 2. The PR sample includes open, merged,
and closed-unmerged PRs. None has submitted reviews; review states, overflowing
review connections, API failures, and high-volume search windows are explicitly
synthetic variations in tests rather than claims about these real users.
