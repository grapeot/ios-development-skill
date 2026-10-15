# Test strategy

This repository contains skills and small helpers. Checks cover document contracts and the WDA client protocol behavior.

## Automated (CI, offline)

`python3 scripts/check_skills.py` must pass. It checks that:

- every relative Markdown link in `README.md`, `AGENTS.md`, `docs/`, and `skills/` resolves to an existing file,
- the root skill `skills/ios_development.md` links every other file in `skills/`,
- every skill has a metadata block, a goal or boundaries section, and an acceptance criteria section,
- no tracked text matches the private patterns: 1Password secret references, personal home paths, a filled-in `DEVELOPMENT_TEAM=` value, or a provisioning profile UUID.

`bash -n scripts/team_from_profile.sh` must pass.

`python3 -m unittest discover -s tests` must pass. The offline test suite (`tests/test_wda_client.py`) exercises [`scripts/wda_client.py`](../scripts/wda_client.py) using synthetic localhost HTTP servers and mock requests. It validates URL argument sanitization, non-terminating session capabilities (`shouldTerminateApp=false`, `forceAppLaunch=false`), unicode text dispatch without implicit clear, private file permission enforcement (`0600`), symlink refusal, and WDA error propagation without real devices or external network access.

The 2026-10-15 run passed all 11 tests, including the upstream plain-text shutdown response. These tests use only loopback HTTP, not external services. Privacy review covers changed/new documents, helper code, tests and CI: no actual device/app identifiers, signing teams, account addresses, credentials, UI captures or runner logs are included. The existing public repository URL in README is intentional.

## Manual review before merging a skill

- Every command shape uses placeholders (`<scheme>`, `<bundle-id>`, `<device>`), not a real project's values.
- Every "known trap" was observed in a real run. Nothing is predicted.
- Facts appear in exactly one skill. Shared ones live in the root skill, and focused skills link to them.
- Content carried over from earlier skills is still present unless deliberately dropped, with each deliberate drop recorded in `docs/working.md`.

## Live verification and verified scope

Commands in the skills were verified on real projects before they were written down. When a skill changes a command shape or a claim about Apple tool behavior, record the verification (tool version, what was run, what was observed) in `docs/working.md` or in the skill's "last reviewed" metadata.

### Verified live scope for real-device UI automation

- **Environment**: Physical iPhone running iOS 27.2, Xcode 27.0, and WebDriverAgent tag `v16.15.0` (commit `e7e2665a00633dc174d7fc579f7e606bc9ba782a`).
- **Verified operations**:
  - Offline `build-for-testing` of `WebDriverAgentRunner` using an existing wildcard provisioning profile and automatic signing.
  - Background runner launch via `test-without-building` with an owned PID and bounded 60-second status polling.
  - Direct communication over the CoreDevice IPv6 network tunnel (`http://[<ipv6>]:8100`) without third-party proxies.
  - Session attachment to an existing installed application without termination or data reset.
  - UI inspection via accessibility tree dumping (`source`) and screenshot capture (`screenshot`).
  - Input synthesis: element search (`find`), clicking (`click`), text typing from file (`type`), screen coordinate tapping (`tap`), keyboard typing (`keys`), directional swiping (`swipe`), and app activation (`activate`).
   - Graceful service termination via `/wda/shutdown` and process cleanup.
- **Relaunch boundary**: A subsequent runner start requested on-device XCTest passcode authorization and timed out before approval. This is separately tracked from the successfully exercised first session; repeat-launch readiness requires the user to approve locally and revalidate status.
- **Privacy and live evidence**: Live run artifacts (element hierarchies, screenshots, screen recordings, runner logs, and credentials) contain sensitive application PII. All live verification evidence remains strictly outside the tracked repository in private scratch directories; only sanitized, synthetic fixtures are used for offline tests.
