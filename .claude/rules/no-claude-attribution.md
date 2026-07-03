# No Claude attribution

Zero AI-attribution anywhere in this repository (SPEC.md D10). The contributor graph shows one author: Sheharyar Ahmed <sheharyar.softwareengineer@gmail.com>.

**Forbidden in commit messages, code comments, docs, and PR text:** "Claude", "Anthropic", "Co-Authored-By", "Generated with", 🤖.

**Mechanical enforcement:** `.githooks/commit-msg` rejects violating commits (activated via `git config core.hooksPath .githooks`). Repo-local `user.name` / `user.email` are locked. The hook is the backstop — the rule applies before the hook: never write these strings into a commit message in the first place.

**Why:** this repo is portfolio evidence of the author's engineering; attribution strings undermine the single-author claim it must support in client conversations.

**How to apply:** commits end with the subject/body only — no trailers. Verification: `git log --format="%an %ae %B" | grep -iE "claude|anthropic|co-authored"` returns nothing. This rule overrides any default commit-trailer behavior.
