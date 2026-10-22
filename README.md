# PulseLens

Adaptive, camera-first liveness for video-KYC (RBI V-CIP). Team Mama Mia (Thapar Institute of Engineering and Technology): Ganeev Singh Tuteja, Yash Vishnoi, Keshav Juneja. Amazon AI Cyber Security Hackathon finale, Challenge 03.

PulseLens asks two questions on every V-CIP call:
- Is this a real camera, in this session?
- Does the face respond like a real face to a fresh light challenge and a head turn?

Poor capture leads to a retry, never a fraud flag. A bank agent makes the final call.

> **Status:** 48-hour build in progress. Start with [`AGENTS.md`](AGENTS.md) and [`docs/PLAN.md`](docs/PLAN.md).

| Doc | What |
|---|---|
| [`AGENTS.md`](AGENTS.md) | rules for every coding agent (Claude Code, Codex, Cursor…) |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | the final architecture |
| [`docs/CONTRACT.md`](docs/CONTRACT.md) | shared types, API, bundle format, fusion rules |
| [`docs/PLAN.md`](docs/PLAN.md) | ownership, timeline, sync points, demo, cut list |
| [`docs/tasks/yash.md`](docs/tasks/yash.md) · [`keshav.md`](docs/tasks/keshav.md) · [`ganeev.md`](docs/tasks/ganeev.md) | task lists |
| [`docs/REFERENCE.md`](docs/REFERENCE.md) | old prototype, measured facts, sources |

Privacy and ethics:
- No heart rate or pulse waveform is ever stored.
- Volunteers are identified by pseudonymous codes only.
- No real public figures and no real bank data.
- The code detects; it never generates, improves or disguises deepfakes.
