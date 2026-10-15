# Working notes

## Changelog

### 2026-09-30

- Scaffolded the repository: PRD, RFC, test strategy, AGENTS.md, README, license, CI, and the check script.
- Planned the consolidation of four skills (simulator UI automation, test acceleration, real-device automation, App Store Connect release) into one root skill and three focused skills.
- Verified new real-device flows on a paired iPhone with Xcode 26.6: signing without an Xcode account session, `devicectl device copy to` for a 785 MB file, payload-URL triggering with result polling, and cold versus warm on-device benchmarks.
- Added the root skill `skills/ios_development.md` (drafted with Antigravity, reviewed and edited). Trimmed test-loop details that belong in the simulator skill, fixed the team-ID command to use the repository path, and kept device addressing to what was verified.
- Added `skills/simulator_testing.md`, merging simulator UI automation and test acceleration (drafted with Antigravity, reviewed). Kept every observed trap, including the XCUITest gesture notes. Dropped one item about `gh pr merge` with a dirty working tree, which is about git, not simulator testing.
- Added `skills/real_device.md` (drafted with Antigravity, reviewed): signing and installing, files in and out of the container, triggers, the result contract with polling, benchmarking, recovery, and a HealthKit and TCC section. Removed a generalized "reinstalling causes registration issues" claim; the one observed case stays in the HealthKit section with its original caveat.
- Added `skills/app_store_release.md`, translated from the Chinese release skill and reorganized (drafted with Antigravity, reviewed). The archive command now takes the team ID from a variable.
- Added the final README (drafted with Antigravity, reviewed).
- CI ran `check_skills.py --allow-pending` while the focused skills landed one PR at a time. With all four skills in place, CI is back to the strict check.

- Extended `skills/real_device.md` with controlling a running app and reading its state: URL commands to a running process, a status heartbeat file, WKWebView bridges, and options not yet verified (an in-app control server, Safari Web Inspector). Added the tailnet observation and the observed file-copy speed range. Drafted with Antigravity, reviewed; the latency difference through a bridge is no longer attributed to the bridge alone.

### 2026-10-12

- Added `skills/watch_development.md` (drafted with Antigravity, reviewed): reaching the watch through its paired iPhone (not USB), explicit pairing via Device Hub ("+" → Pair Nearby Device) or the watch's Developer Mode screen, the missing Developer Mode toggle and its restart remedy, `connected (no DDI)` state and DDI symbol preparation, the `-destination-timeout` fix for `xcodebuild`, watch scheme/destination selection, HealthKit needing an explicit profile that includes the watch UDID (`0xe8008012`), and CLI install via `devicectl`. Wired it into the root skill's routing table, related skills, and install note, and into `AGENTS.md`. Observed during a first-time physical Apple Watch setup.
- Added a "Background location" section and a Traps row to `skills/watch_development.md` for an observed runtime crash: setting `CLLocationManager.allowsBackgroundLocationUpdates = true` on watchOS trips a CoreLocation assertion (`CLClientIsBackgroundable`), and declaring `WKBackgroundModes = [workout-processing]` does not permit the flag. The remedy is to rely on the active `HKWorkoutSession` and not set the flag. Drafted with Antigravity, reviewed.

### 2026-10-15

- Added `skills/real_device_ui.md` (drafted with Antigravity, reviewed): automated UI control for installed/App Store applications on a paired physical iPhone via an upstream WebDriverAgent runner (`v16.15.0`, commit `e7e2665a00633dc174d7fc579f7e606bc9ba782a`).
- Verified offline development signing with a cached wildcard profile via `xcodebuild ... build-for-testing` without `-allowProvisioningUpdates`. The runner bundle ID on device gains the `.xctrunner` suffix while the target app remains unchanged.
- Verified background launch via `test-without-building` with an owned PID and CoreDevice IPv6 network tunnel communication on port 8100 (read via `xcrun devicectl device info details`), bypassing ambient HTTP proxies and eliminating third-party tunnel proxies.
- Added `scripts/wda_client.py` (standard-library HTTP client) and offline unit tests with synthetic localhost servers for session non-termination, Unicode text dispatch, private file permissions, symlink refusal, error preservation, and the upstream plain-text shutdown response; no external network or devices required.
- Live verification on physical iPhone running iOS 27.2 with Xcode 27.0: confirmed session open without app termination (`shouldTerminateApp=false`, `forceAppLaunch=false`), accessibility hierarchy dump, element search, click, text entry from file, coordinate tap, keys input, screenshot, swipe, app activation, and clean service shutdown.
- HTTP 200 delivery ACK did not guarantee retained input: WebView OTP required explicit focus and per-digit typing, while a native hidden OTP used tap plus keyboard input. Re-read the UI after input; keep secret text out of logs.
- A click timed out after the page advanced; inspect state before retrying. Coordinate fallback uses points rather than screenshot pixels.
- Upstream keyboard preference writes were denied by the current iOS sandbox; this does not guarantee other versions leave preferences unchanged.
- Session close preserves the runner; `/wda/shutdown` returns plain text and stops it. Preinstalled-runner launch via `devicectl` alone has known iOS 27 caveats; the tested route uses `xcodebuild test-without-building`.
- Updated root skill `skills/ios_development.md` with routing for device UI, clarified target app boundaries in `skills/real_device.md`, updated `README.md`, `docs/prd.md`, `docs/rfc.md`, and `docs/test.md`.
- A later runner launch timed out while enabling automation mode; a device screenshot showed an XCTest passcode authorization prompt. Recorded the human-consent recovery boundary rather than treating pairing/Developer Mode as sufficient. No passcode was captured or requested in chat.
- After local user approval, repeated `test-without-building` reached readiness; opening an installed-app session, reading the tree, navigating to search and back home passed. The helper handled upstream plain-text shutdown, the endpoint became unavailable, and the owned xcodebuild process exited. The initial timeout remains documented as an observed consent requirement, not an unresolved relaunch failure.

## Lessons Learned

- Test acceleration and simulator UI automation describe the same `xcodebuild test` loop. Keeping them as separate skills duplicated it.
- Automatic signing without `-allowProvisioningUpdates` works offline with a cached wildcard development profile. With the flag and no signed-in account, the build fails. Manual signing rejects Xcode-managed profiles.
- Controlling existing App Store apps does not require app source, reinstallation, resigning, or container access; it can be driven via a separate development-signed WDA XCTest runner over the CoreDevice network tunnel.
- An HTTP 200 delivery ACK from an automation endpoint does not prove the application UI accepted or retained the input; verifying UI state changes requires re-reading the accessibility hierarchy or capturing a fresh screenshot.
