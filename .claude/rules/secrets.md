# Secrets rules (always apply)

- Never read, print, grep or copy environment files, key files or secret stores. Document variables in `.env.example` with placeholder values only.
- Secrets come only from environment variables or a secret manager at runtime. Never commit them, including "dev-only" real-looking values (the legacy `../rms` committed one in `docker-compose.yml` — do not repeat that).
- Never put secrets, tokens, passwords, cookies or connection strings in code, tests, fixtures, logs, error messages, docs, commit messages, change records or agent output.
- If you find a secret in the repo, do not paste it anywhere. Report `file:line` as "secret-like value", severity `critical` — it must be rotated, not only deleted.
- Before any commit, check staged changes for secret-like values (`gitleaks protect --staged` if installed; otherwise grep for high-signal patterns such as private-key headers and provider key prefixes).
