# Git rules (always apply)

- Commit or push only when the user asks. Never force-push, hard-reset, or rewrite shared history.
- Work on a branch per change: `<type>/<NNNN>-<slug>` (e.g. `feat/0012-partial-payments`). Never commit directly to the default branch.
- Conventional Commits: `feat|fix|refactor|test|docs|chore|security(scope): summary`. Reference the change record number in the body.
- One logical change per commit; no unrelated formatting or refactors mixed in.
- Check staged files for secrets before committing (see `secrets.md`). Never commit environment files, keys, dumps or `media/`.
- Commit migrations together with the model change that requires them.
