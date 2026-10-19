---
name: git-workflow
description: Use when committing, branching, reviewing diffs or opening PRs.
---

# Git workflow

1. Always run `git status` and `git diff` before staging anything.
2. Stage specific files (`git add path/to/file`), never `git add -A` blindly.
3. Write commit messages as: short imperative summary, then a body explaining
   *why* the change was made, not what the diff already shows.
4. Never force-push to `main`. Never `git reset --hard` on work you did not
   just create.
5. Before pushing, confirm the branch with `git branch --show-current`.
6. After pushing, report the commit hash and the remote branch name.

If a commit fails a hook, fix the underlying problem and make a new commit.
Do not use `--no-verify`.
