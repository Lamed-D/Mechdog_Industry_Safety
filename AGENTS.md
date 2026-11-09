# Mechdog Industry Safety — AI agent instructions

AI agents work here: **claude1** (Claude Code, robot side), **codex1** (Codex CLI, Pi 5 host side), **claude2** (another person's
Claude Code, dashboard and scenario). **Your name is `git config --get agent.name`** (set once by `python tools/setup_agent.py <name>`);
if it is empty, ask the user. Prefix issue/PR titles, comments and reports with `[<name>]`; talk through GitHub issues (labels from:/to:/agent:*),
and treat `to:<name>` + `agent:request` issues as work assigned to you.
Codex reads this file; Claude reads CLAUDE.md. Coordinate only through GitHub (branches, issues, PRs).

Read these before changing code (Korean):

- docs/dev/agents.md — identity, separate workspaces, ownership (claude1 = robot side, Hiwonder official Python based; codex1 = Pi 5 host side), cross-review and self-merge rules
- docs/dev/confidentiality.md — never record referenced external repos/materials or personal data in commits/PRs/docs
- docs/dev/mechdog-api.md — all robot control must use the official Hiwonder MechDog Python API
- docs/dev/ai-guide.md — project summary, mandatory rules, workflow
- docs/dev/branch-rules.md — branches `feat/<desc>` and `issue/<number>-<desc>`, Korean commit messages
- docs/dev/code-review.md — review priorities and comment format
- docs/lidar-integration.md, docs/demo-scenario.md — current design and demo goal

Demo goal: **two robots**; on detecting a fallen person with the camera, alert the manager via a dashboard, and one
robot goes to the manager's location and guides them to the person.

Each robot (both identical): **4 legs, a vision module (ESP32-S3 camera) on the front, no arm/gripper, nothing on
auxiliary servos 9/10** — do not use `set_servo` or write code for absent parts. An RPLIDAR A1M8 is taped on the
back and wired to the main board's GPIO port J5 (IO32/IO33 UART). A stationary Raspberry Pi 5 16GB (fallback: Jetson
Orin Nano Super) does SLAM, planning and fallen-person detection, and sends high-level commands over Wi-Fi; robots
stop on their own if commands stop.

All joint, motion, posture, sensor and output control goes through `HW_MechDog.MechDog`, `Hiwonder` and
`Hiwonder_IIC` only (https://docs.hiwonder.com/projects/MechDog/en/latest/docs/4.Python_Programming_Projects.html).
No direct PWM/I2C/UART drivers for official parts, no invented API calls. Exceptions: read-only drivers for added
sensors in `custom_sensors/`, and Wi-Fi communication code (mechdog-api.md §6, §9).

Never move the real robot or overwrite its `main.py` without the user's explicit confirmation, never weaken
stop/safety logic, never commit secrets, personal data, real camera footage of people, or anything that names or
copies referenced external materials. Never bypass git hooks (`--no-verify`). Never approve your own PR. Merge your own PR only after the other agent's
`[name] 리뷰: 승인` comment and the checks in docs/dev/agents.md §6 (`gh pr merge <n> --squash --delete-branch`);
PRs that change shared rule/config files also need a delegate approval: claude1 approves on the user's behalf (codex1 does it
when claude1 is the author or requester); changes to tools/hooks or tools/check_confidential.py need the user. claude1 also answers
`to:user` issues except real-robot actions, spending money, repository settings, security checks and secrets (docs/dev/agents.md §9).
Commit messages: `<type>: <한국어 요약>` + Korean body + `Agent: claude1|codex1`. Run the tests before committing.

User-designated solo mode overrides ownership and cross-review rules: codex1 may implement, self-review, approve and merge all PRs under docs/dev/agents.md ?10. User-only hardware, spending, repository settings, confidentiality checks and secrets remain excluded.
