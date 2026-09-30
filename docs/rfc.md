# RFC: Structure and key decisions

## Layout

```
skills/
  ios_development.md      root skill: routing plus shared foundations
  simulator_testing.md    simulator UI automation and fast test loops
  real_device.md          paired-device install, files, triggers, results, benchmarks
  app_store_release.md    archive, export, verify, upload
scripts/
  check_skills.py         offline structure, link, and privacy check (CI)
  team_from_profile.sh    read a team ID from a cached provisioning profile
docs/                     PRD, RFC, test strategy, working log
```

## Decisions

### 1. One root skill plus focused skills

A workspace exposes only `skills/ios_development.md`. The root skill has two jobs. It routes along the development lifecycle: change code, verify on a simulator, speed up the loop, run on a device, release. And it holds the knowledge that more than one focused skill needs. Focused skills link back to the root for that shared knowledge instead of repeating it. This matches how other multi-skill repositories are installed: one entry in the index, focused files loaded on demand.

### 2. Three focused skills, not four

Test acceleration and simulator UI automation both describe the `xcodebuild test` loop on simulators: serial runs, one DerivedData path, `build-for-testing` then `test-without-building`, pinned simulator UUIDs, `-only-testing`, and `.xcresult` inspection. Keeping them apart duplicated that loop. They merge into `simulator_testing.md`. Real-device work and App Store release stay separate, because their tools, failure modes, and authorization boundaries differ.

### 3. What the root skill owns

- Choosing and pinning the Xcode toolchain (`DEVELOPER_DIR`, `xcodebuild -version`).
- Serial `xcodebuild` on one DerivedData path per project.
- The signing model: development signing (simulator needs none, a device needs a development profile) against distribution signing (App Store export). The rule that team IDs, profile UUIDs, and credentials never appear in commands, logs, or repositories, and how to read them from controlled sources instead.
- The device toolchain split: `xcrun simctl` is simulator-only, and `xcrun devicectl` handles physical devices.
- What a calling project must supply: project or workspace, scheme, bundle ID, destinations, and its definition of success.
- Where artifacts go: ignored local scratch, never the repository.

### 4. Real device gains the newly verified flows

These were verified on a paired iPhone on 2026-09-30:

- Install without an Xcode account session. Automatic signing without `-allowProvisioningUpdates` picks the team's cached wildcard development profile. With the flag and no signed-in account, the build fails with "No Account for Team". Manual signing rejects an Xcode-managed profile. The team ID can be read from the profile itself (`scripts/team_from_profile.sh`), which keeps it out of commands. A wildcard profile cannot carry entitlements such as HealthKit or push, so apps that need them still need their explicit profile.
- Push files into the app container with `devicectl device copy to` (785 MB in 34 s). For automated runs this replaces an in-app download, which would need a reachable server and could raise the local-network permission prompt.
- Trigger a one-shot run by `--payload-url`, then poll `devicectl device copy from` until the result file for that run ID appears.
- Benchmark on device. The first run can include one-time costs, such as GPU shader compilation (17 s on first model load, 0.37 s after). Report cold and warm runs separately, and warm up before timing.

HealthKit and TCC notes move into their own section of `real_device.md`, unchanged in substance.

### 5. Writing process

Each skill is drafted by Antigravity (Gemini) from the original skill text plus a short packet of new, verified facts. The main agent then reviews the draft for accuracy, scope, and duplication and edits it in place. Content that is specific to one private app or machine stays in the installing workspace's private overlay, not in this repository.

### 6. No CLI

The skills drive Apple's own tools. A wrapper would hide the raw error output that agents need, and it would drift from Xcode releases. The two scripts are small helpers: one validates this repository, and one reads a value that must stay out of commands.

## Validation

`scripts/check_skills.py` runs in CI. It checks that every relative Markdown link resolves, that the root skill links every file in `skills/`, that each skill has a metadata block, a goal or boundaries section, and acceptance criteria, and that no text matches the private patterns list (team-ID-shaped strings in signing settings, 1Password secret references, device-name placeholders left unfilled, and personal paths).

## Migration

- In the private workspace, the four old skill files become one-line redirects to this repository, so existing links keep working. The skill index lists only the root skill. Private details live in a small workspace overlay.
- The public context-infrastructure repositories (Chinese and English) drop their copies of the old iOS skills and link this repository from their skill ecosystem pages.
- The skills registry replaces the `ios-ui-automation` entry with an entry for this repository.
