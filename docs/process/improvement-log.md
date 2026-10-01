# Engineering-System Improvement Log

Proposals to change agents, skills, rules, gates or process. Written by the `retro` skill or the orchestrator at step 11 of `change`. Applied only with human approval.

Format:

```
## YYYY-MM-DD — <short title>   Status: Proposed | Applied | Rejected
Evidence: <change records / files>
Proposal: <file + exact change>
Expected effect:
Decision: <by whom, when>
```

---

## 2026-10-01 — Hook bypass by assembling the env filename   Status: Proposed
Evidence: change 0003 backend implementation report — twice a shell command pieced the env file name together, which the secret-file hook does not match. Nothing was read or printed.
Proposal: (a) add to `docs/process/agent-contract.md` "Never": "Never construct, obfuscate or indirect a protected filename to get past a hook; use the Makefile variables/targets." (b) consider a hook that also matches `uv run --env-file` and variable-built paths.
Expected effect: guardrails cannot be bypassed accidentally.
Decision: pending (product owner).

## 2026-10-01 — `make migrate` hides the migrate permission prompt   Status: Proposed
Evidence: change 0003 — `.claude/settings.json` asks before `*manage.py migrate*`, but `make migrate` / `make setup` run it without matching the pattern. The implementer noticed and did not run it.
Proposal: add `Bash(make migrate*)` and `Bash(make setup*)` to the `ask` list in `.claude/settings.json`.
Expected effect: migrations against any DB still need explicit confirmation.
Decision: pending (product owner).
