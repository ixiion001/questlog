# How each achievement is counted

`questlog` counts what it can read from GitHub for one account and compares
the count with the tiers in `src/questlog/achievements.yaml`. This page says
what each rule counts and where the count can differ from what GitHub shows
on your profile.

All rules work from the same data:

- pull requests the account **authored**, with when each was opened, closed
  and merged, and whether it had a review before it was merged;
- closed issues the account **authored**, with when each was opened and
  closed;
- discussion answers the account wrote that are marked as the accepted
  answer.

Only items your `gh` login can see are counted. See
[What gets counted](usage.md#what-gets-counted) for how the search works.

## Pull Shark

Tiers: 2, 16, 128, 1024.

Counts pull requests you opened that were merged. A pull request that was
closed without merging does not count, and neither does one that is still
open.

## YOLO

Tier: 1.

Counts pull requests you opened that were merged without a review.

A pull request counts as reviewed if anyone, including you, submitted a
review before the merge: an approval, a request for changes, a review
comment, or a review that was later dismissed. Pending reviews and reviews
submitted after the merge do not count.

This is an approximation. The achievement is about the person who merges,
but `questlog` does not know who merged a pull request and does not look at
pull requests by other people. So it can:

- count a pull request of yours that someone else merged without a review,
  and
- miss a pull request by someone else that you merged without a review.

## Quickdraw

Tier: 1.

Counts issues and pull requests you opened that were closed within 5 minutes
of being opened. The 5 minutes are inclusive. A pull request that was merged
within 5 minutes counts too, because merging also closes it.

This is an approximation. `questlog` only sees items you opened and does not
know who closed them, so it can:

- count an item of yours that someone else closed, and
- miss an item by someone else that you closed.

## Galaxy Brain

Tiers: 2, 8, 16, 32.

Counts your discussion answers that are marked as the accepted answer. Each
accepted answer counts once. An answer in a repository your `gh` login can't
see is not counted.

## When a count looks wrong

- Run `questlog explain NAME` to see its summary and tiers.
- Check that the item is visible to your `gh` login. Items in private
  repositories you have lost access to are not counted.
- GitHub can change a rule or its tiers without notice. The tiers are in
  `src/questlog/achievements.yaml`; the rules are in `src/questlog/rules/`.
  To add a rule, see [Adding an achievement](adding-an-achievement.md).
