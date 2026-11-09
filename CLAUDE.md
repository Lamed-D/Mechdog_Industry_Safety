# Mechdog Industry Safety

AI agents work here: claude1, codex1 and claude2, each in its own working folder.
Your name is the output of `git config --get agent.name` (set by `python tools/setup_agent.py <name>`); if empty, ask the user.
Prefix issue/PR titles, comments and reports with [<your name>]; talk to the others through GitHub issues and treat
`to:<your name>` + `agent:request` issues as assigned work.
If you are claude1, you also act as the user's delegate approver for `to:user` issues and shared-rule PRs (docs/dev/agents.md §9).

Work rules for AI agents live in docs/dev. Read them before changing code.

@docs/dev/agents.md
@docs/dev/confidentiality.md
@docs/dev/mechdog-api.md
@docs/dev/ai-guide.md
@docs/dev/branch-rules.md
@docs/dev/code-review.md

User-designated solo mode overrides ownership and cross-review rules: codex1 may implement, self-review, approve and merge all PRs under docs/dev/agents.md ?10. User-only hardware, spending, repository settings, confidentiality checks and secrets remain excluded.
