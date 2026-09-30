# iOS Development

## Metadata

- Type: Root Workflow
- When to use: Entry point for iOS development tasks across the app lifecycle: code iteration, simulator testing, physical-device validation, and App Store release.
- Related skills:
  - [`./simulator_testing.md`](./simulator_testing.md)
  - [`./real_device.md`](./real_device.md)
  - [`./app_store_release.md`](./app_store_release.md)
- Last reviewed: 2026-09-30. Consolidated from four earlier skills whose content was verified on real projects. Device signing without an Xcode account session and container file transfer were verified that day with Xcode 26.6 on a paired iPhone.

## Goal and Boundaries

Provide a unified entry point and routing table for iOS development, establishing shared toolchain, signing, build, device, and privacy conventions across all focused skills.

This root skill does not execute tests, device operations, or release uploads directly; it delegates execution to the corresponding focused skills.

## Acceptance Criteria

Routing and shared foundations are satisfied when:
- The task lifecycle stage is identified and dispatched to the correct focused skill.
- Shared build discipline, toolchain pinning, signing rules, and privacy practices are enforced without duplicating them in focused skills.
- No secrets, credentials, team IDs, or private device/account identifiers appear in commands, logs, or repositories.
- The task completes when the delegated focused skill's acceptance criteria are met.

## Lifecycle Routing

| Lifecycle Stage | Task Description | Focused Skill |
|---|---|---|
| Change code | Modify UI or feature logic, build, and check layout | [`./simulator_testing.md`](./simulator_testing.md) |
| Verify on simulator | Validate UI flows, capture screenshots, run XCTest suites | [`./simulator_testing.md`](./simulator_testing.md) |
| Speed up the loop | Fast `test-without-building` cycles, targeted `-only-testing`, inspect `.xcresult` | [`./simulator_testing.md`](./simulator_testing.md) |
| Run on a device | Physical-device install, container file copy, URL triggers, on-device benchmarks, HealthKit/TCC | [`./real_device.md`](./real_device.md) |
| Release | Archive, App Store export, IPA metadata inspection, upload to App Store Connect | [`./app_store_release.md`](./app_store_release.md) |

## Toolchain

- Explicitly pin Xcode via `DEVELOPER_DIR` and verify with `xcodebuild -version` and `xcode-select -p`. Stable and beta Xcode may coexist; never rely on implicit global defaults or remove beta installations.
- Primary command-line tools:
  - `xcodebuild`: compile, test (`test`, `build-for-testing`, `test-without-building`), archive (`archive`), and export (`-exportArchive`).
  - `xcrun simctl`: simulator lifecycle, app installation, launches, and screenshots (`xcrun simctl io <device-uuid> screenshot <path>`).
  - `xcrun devicectl`: physical-device discovery, installation, container file transfer, and process launch.
  - `xcrun altool`: App Store Connect package validation and upload.
  - `codesign`, `security`, `plutil`: signature inspection and property list parsing.

```bash
export DEVELOPER_DIR="/Applications/Xcode.app/Contents/Developer"
xcode-select -p
xcodebuild -version
```

## Build discipline

- Run `xcodebuild` sequentially against a single `-derivedDataPath` per project. Parallel builds against the same project or DerivedData fail with `build.db: database is locked`.
- Test loops (build once, run focused tests, inspect `.xcresult`) are in [`./simulator_testing.md`](./simulator_testing.md).
- Use distinct output paths for archives and exports so previous artifacts are not overwritten during retries.

## Signing

- **Development vs. distribution**:
  - Simulators require no code signing or provisioning profiles.
  - Physical devices require development signing (`Apple Development` identity, development profile, `get-task-allow=true`).
  - App Store export re-signs the archive with distribution signing (`Apple Distribution` or `Cloud Managed Apple Distribution`, App Store profile, `get-task-allow=false`). An archive cannot be uploaded directly without distribution export.
- **Credential hygiene**:
  - Never write team IDs, profile UUIDs, Apple ID passwords, app-specific passwords, API private keys (`.p8`), or issuer IDs in commands, logs, or repositories.
  - Read credentials dynamically from a controlled configuration or secret manager.
- **Reading the team ID**:
  - Read it from a cached provisioning profile with [`scripts/team_from_profile.sh`](../scripts/team_from_profile.sh) in this skill's repository, captured into a variable so the value never appears in a command or log. The script prints only the team ID. Pass a profile name as the first argument to choose a profile other than the team wildcard.
    ```bash
    team="$("<skill-repo>/scripts/team_from_profile.sh")"
    xcodebuild ... CODE_SIGN_STYLE=Automatic DEVELOPMENT_TEAM="$team" build
    ```
- **Device-install signing summary**:
  - Device install uses automatic signing with a cached wildcard profile without `-allowProvisioningUpdates` when no Xcode account session is active. See [`./real_device.md`](./real_device.md) for full mechanics, capability limits (wildcards cannot carry HealthKit/push), and error diagnosis (`No Account for Team`, manual profile errors).

## Simulators and devices

- `xcrun simctl` is strictly simulator-only; `xcrun devicectl` drives physical devices only.
- Destination addressing:
  - Simulator: `-destination 'platform=iOS Simulator,name=<device>,OS=<version>'` or `'id=<simulator-uuid>'`.
  - Physical device in `xcodebuild`: `-destination 'platform=iOS,name=<device-name>'` (verified) or `'platform=iOS,id=<device-udid>'`.
  - Physical device in `devicectl`: `--device <device-identifier>`, using the Identifier column of `xcrun devicectl list devices`.
- Physical devices must be paired, trusted, and unlocked. CLI automation cannot bypass device passcode locks or grant TCC/HealthKit permissions.

## Inputs from the calling project

Calling projects remain decoupled from this skill and must supply:
- Xcode project or workspace path (`-project <App.xcodeproj>` or `-workspace <App.xcworkspace>`)
- Target scheme (`<scheme>`) and configuration (`Debug` / `Release`)
- Bundle identifier (`<bundle-id>`)
- Destination: simulator name/UUID or physical device name/identifier
- Deterministic launch arguments, environment flags, or payload URL routes
- Definition of success: passing test suites, screenshot visual criteria, result schemas, or upload confirmation

## Artifacts and privacy

- Store intermediate artifacts (build logs, DerivedData, `.xcresult`, screenshots, downloaded container payloads, archives, IPAs) in ignored local scratch directories (e.g. `tmp/`, `.derivedData/`, `build/`). Never commit QA artifacts.
- Use synthetic fixture data for UI tests and screenshots; never commit or share images showing private user data, accounts, tokens, or backend URLs.
- For physical device diagnostics, collect bounded aggregate metrics (counts, status codes, percentiles) rather than dumping raw personal data.

## Installing this skill

Add only this root file (`ios_development.md`) to the workspace skill index. Focused skills (`./simulator_testing.md`, `./real_device.md`, `./app_store_release.md`) sit alongside it and load on demand based on lifecycle routing.
