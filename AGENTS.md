# Mechdog Industry Safety — AI agent instructions

Read `docs/ai/rules.md` first (Korean). All AI-facing rules and design docs live in `docs/ai/`; `README.md` is the only human-facing guide.

- Your name: `git config --get agent.name` (ask the user if empty). Prefix PR titles, comments and reports with `[<name>]`.
- Branch `feat/<desc>` or `issue/<n>-<desc>`, Korean Conventional Commits, self-verify (`python -m unittest discover -s tests`, `python tools/check_confidential.py range origin/main..HEAD`) then squash-merge your own PR.
- Robot control only through the official Hiwonder MechDog API — see `docs/ai/mechdog-api.md`.
- Never record names, paths or text of private reference materials — see `docs/ai/rules.md` §5.
- LiDAR, ROS 2 and map code are frozen — see `docs/ai/lidar-frozen.md`.
