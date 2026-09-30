# AGENTS.md

This repository is an agent skill for iOS development from the command line. It holds one root skill and three focused skills. Read `docs/prd.md` and `docs/rfc.md` before changing the structure.

## Structure

- `skills/ios_development.md`: the root skill. It routes tasks and owns shared knowledge. It is the only file a workspace should index.
- `skills/simulator_testing.md`, `skills/real_device.md`, `skills/app_store_release.md`: focused skills, loaded through the root.
- `scripts/check_skills.py`: offline structure, link, and privacy check. CI runs it.
- `scripts/team_from_profile.sh`: reads a team ID from a cached provisioning profile.
- `docs/`: PRD, RFC, test strategy, and `working.md`. Update `working.md` at the end of every session.

## Rules

- Write skills for results, not procedures: goal, boundaries, acceptance criteria, resources, and traps. Record a trap only after it was observed in a real run.
- Keep each fact in one place. Shared knowledge belongs in the root skill, and focused skills link to it.
- Public repository: no team IDs, device names, private bundle IDs, private hosts, personal paths, or credential locations in any tracked file, including commit messages. Use placeholders. Private details belong in the installing workspace's overlay.
- Run `python3 scripts/check_skills.py` before every commit.
- Prose that people read (skills, README) is drafted with Antigravity and then reviewed by the main agent. Code identifiers and test text do not need this.
- Default branch is `master`. It is protected, so changes land through PRs. Commit, push, or open PRs only when the user asks.
