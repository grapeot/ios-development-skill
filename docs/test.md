# Test strategy

This repository is documentation plus two small scripts, so testing checks the documents.

## Automated (CI, offline)

`python3 scripts/check_skills.py` must pass. It checks that:

- every relative Markdown link in `README.md`, `AGENTS.md`, `docs/`, and `skills/` resolves to an existing file,
- the root skill `skills/ios_development.md` links every other file in `skills/`,
- every skill has a metadata block, a goal or boundaries section, and an acceptance criteria section,
- no tracked text matches the private patterns: 1Password secret references, personal home paths, a filled-in `DEVELOPMENT_TEAM=` value, or a provisioning profile UUID.

`bash -n scripts/team_from_profile.sh` must pass.

## Manual review before merging a skill

- Every command shape uses placeholders (`<scheme>`, `<bundle-id>`, `<device>`), not a real project's values.
- Every "known trap" was observed in a real run. Nothing is predicted.
- Facts appear in exactly one skill. Shared ones live in the root skill, and focused skills link to them.
- Content carried over from the original four skills is still present unless it was deliberately dropped, and each deliberate drop is recorded in `docs/working.md`.

## Live verification

Commands in the skills were verified on real projects before they were written down. When a skill changes a command shape or a claim about Apple tool behavior, record the verification (tool version, what was run, what was observed) in `docs/working.md` or in the skill's "last reviewed" metadata.
