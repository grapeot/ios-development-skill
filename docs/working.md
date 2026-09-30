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

## Lessons Learned

- Test acceleration and simulator UI automation describe the same `xcodebuild test` loop. Keeping them as separate skills duplicated it.
- Automatic signing without `-allowProvisioningUpdates` works offline with a cached wildcard development profile. With the flag and no signed-in account, the build fails. Manual signing rejects Xcode-managed profiles.
