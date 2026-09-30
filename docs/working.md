# Working notes

## Changelog

### 2026-09-30

- Scaffolded the repository: PRD, RFC, test strategy, AGENTS.md, README, license, CI, and the check script.
- Planned the consolidation of four skills (simulator UI automation, test acceleration, real-device automation, App Store Connect release) into one root skill and three focused skills.
- Verified new real-device flows on a paired iPhone with Xcode 26.6: signing without an Xcode account session, `devicectl device copy to` for a 785 MB file, payload-URL triggering with result polling, and cold versus warm on-device benchmarks.

## Lessons Learned

- Test acceleration and simulator UI automation describe the same `xcodebuild test` loop. Keeping them as separate skills duplicated it.
- Automatic signing without `-allowProvisioningUpdates` works offline with a cached wildcard development profile. With the flag and no signed-in account, the build fails. Manual signing rejects Xcode-managed profiles.
