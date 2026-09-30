# Working notes

## Changelog

### 2026-09-30

- Scaffolded the repository: PRD, RFC, test strategy, AGENTS.md, README, license, CI, and the check script.
- Planned the consolidation of four skills (simulator UI automation, test acceleration, real-device automation, App Store Connect release) into one root skill and three focused skills.
- Verified new real-device flows on a paired iPhone with Xcode 26.6: signing without an Xcode account session, `devicectl device copy to` for a 785 MB file, payload-URL triggering with result polling, and cold versus warm on-device benchmarks.

- Added the root skill `skills/ios_development.md` (drafted with Antigravity, reviewed and edited). Trimmed test-loop details that belong in the simulator skill, fixed the team-ID command to use the repository path, and kept device addressing to what was verified.
- CI runs `check_skills.py --allow-pending` while the focused skills land one PR at a time; the last skill PR removes the flag.

## Lessons Learned

- Test acceleration and simulator UI automation describe the same `xcodebuild test` loop. Keeping them as separate skills duplicated it.
- Automatic signing without `-allowProvisioningUpdates` works offline with a cached wildcard development profile. With the flag and no signed-in account, the build fails. Manual signing rejects Xcode-managed profiles.
