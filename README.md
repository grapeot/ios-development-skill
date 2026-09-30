# iOS Development Skill

This skill equips AI coding agents—such as Claude Code, Codex, Cursor, and OpenCode—to handle iOS development workflows end-to-end: running simulator testing, deploying to a paired iPhone and bringing back results, and preparing App Store Connect releases. It directly drives Apple's own tools (`xcodebuild`, `simctl`, `devicectl`) with no wrapper CLI.

## What is inside

- [`skills/ios_development.md`](skills/ios_development.md) — Root skill: lifecycle routing, toolchain setup, serial builds, and the shared signing model.
- [`skills/simulator_testing.md`](skills/simulator_testing.md) — Simulator UI automation and fast test loops (`build-for-testing` / `test-without-building`).
- [`skills/real_device.md`](skills/real_device.md) — Paired-device installation, file transfer, URL payload triggers, result retrieval, and benchmarks.
- [`skills/app_store_release.md`](skills/app_store_release.md) — App Store Connect releases: archive, export, verification, and upload.

## Install

Hand the repository URL to your coding agent and ask it to install the skill. The agent starts from the workspace's `AGENTS.md` or `CLAUDE.md`, follows any routing file, and adds only the root skill to the workspace's skill index (for example `rules/skills/INDEX.md` or `skills/INDEX.md`), or adds a short pointer in `AGENTS.md` or `CLAUDE.md` if there is no index.

Example prompt:
```
Install the iOS development skill from https://github.com/grapeot/ios-development-skill. Check our AGENTS.md or CLAUDE.md, follow any routing file, and add only the root skill to our skill index.
```

## Requirements

- macOS with Xcode.
- For devices: a paired device with Developer Mode on and a development team's signing identity.

## What the agent cannot do for you

- Unlock a device.
- Answer system permission prompts.
- Sign in to accounts.

## License

MIT
