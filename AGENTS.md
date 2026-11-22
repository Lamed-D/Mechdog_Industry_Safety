# Mechdog Industry Safety — AI agent instructions

Read `ai/rules.md` first (Korean). All AI-facing rules and design docs live in `ai/`; `README.md` is the only human-facing guide.

- Your name: `git config --get agent.name` (ask the user if empty). Prefix PR titles, comments and reports with `[<name>]`.
- Branch `feat/<desc>` or `issue/<n>-<desc>`, Korean Conventional Commits, self-verify (`python -m compileall -q dashboard ai firmware/robot/python`, `python tools/check_confidential.py range origin/main..HEAD`) then squash-merge your own PR.
- Robot control only through the official Hiwonder MechDog API — see `ai/mechdog-api.md`.
- Never record names, paths or text of private reference materials — see `ai/rules.md` §5.
- Real hardware only: no tests, mocks or fake devices.
- LiDAR code is frozen — see `ai/lidar-frozen.md`.
