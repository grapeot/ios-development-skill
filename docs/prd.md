# PRD: iOS Development Skill

## Goal

Give coding agents one entry point for iOS app work driven from the command line: building and testing on simulators, installing and exercising apps on a paired physical device, and releasing to App Store Connect. The agent should reach a verified result without asking a person to open Xcode, tap through the app, or paste logs, except where iOS requires a human (unlocking a device, answering a system permission prompt, signing in to an account).

## Background

This repository consolidates four separate skills that grew out of real projects:

- simulator UI automation (build, launch, screenshot, XCTest click-through),
- iOS test acceleration (fast `xcodebuild test` loops),
- physical-device automation (install, trigger a deep link, retrieve a result file),
- App Store Connect release (archive, export, verify, upload).

They shared knowledge that was either duplicated or missing where it was needed: pinning the Xcode version, serializing `xcodebuild` on one DerivedData path, the difference between development and distribution signing, keeping the team ID out of commands, and choosing between `simctl` and `devicectl`. Newly verified device work also fits none of the four files by itself: installing to a device without an Xcode account session, pushing large files into an app container, and on-device benchmarking.

## Users

- **Coding agents** (Claude Code, Codex, Cursor, OpenCode, and others) working on an iOS project, loaded through a workspace's skill index.
- **Developers** who install the skill into their agent's workspace and read it to understand what the agent will do.

## Requirements

- One root skill that routes a task to the right focused skill and holds the knowledge all of them share.
- Three focused skills:
  - **Simulator testing**: UI automation plus test acceleration, which are the same `xcodebuild test` loop.
  - **Real device**: signing and installing for a paired device, moving files in and out of the app container, triggering one-shot runs by URL, retrieving results, and benchmarking on device. Framework-specific permission notes (HealthKit, TCC) go in their own section.
  - **App Store release**: archive, export, IPA verification, and upload.
- Each skill states its goal, boundaries, acceptance criteria, resources, and only traps that were observed in real runs, following result-over-process skill design.
- No private identifiers in any tracked file: no team IDs, device names, bundle IDs of private apps, private hosts, or credential locations. Placeholders only.
- Installation works by handing the repository URL to a coding agent. The agent adds the root skill to the workspace's skill index. Only the root skill is exposed at the workspace level.
- An offline check (`scripts/check_skills.py`) verifies the structure, and CI runs it.

## Non-goals

- A CLI or wrapper around `xcodebuild`, `simctl`, or `devicectl`. The skills describe results and constraints, and the agent calls Apple's tools directly.
- macOS, watchOS, tvOS, or visionOS specifics beyond what the iOS flows need.
- Replacing Xcode for interactive development.
- Android or cross-platform frameworks.

## Success criteria

1. An agent that loads only the root skill can pick the right focused skill for: "verify this UI change on a simulator", "why are my tests slow", "run this on my iPhone and bring back the result", and "upload this build".
2. Everything in the four original skills that was verified in practice survives the rewrite, and each item appears in exactly one place.
3. `scripts/check_skills.py` passes: every relative link resolves, the root links every focused skill, every skill has the required sections, and no private pattern appears.
4. The workspace skill index and the public skill directories point to this repository instead of the four old skills.
