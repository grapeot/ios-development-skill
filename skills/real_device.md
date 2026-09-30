# Real Device Development and Testing

## Metadata

- Type: Workflow
- When to use: An agent must build, sign, install, trigger (via payload URL or openURL), benchmark, transfer container files, or retrieve diagnostics on a paired physical iOS device.
- Related skills:
  - [iOS Development](./ios_development.md): Root skill covering the Xcode toolchain, serial builds, DerivedData, and the [signing model](./ios_development.md#signing).
  - [Simulator Testing](./simulator_testing.md): Simulator UI automation, test acceleration, synthetic fixtures, and XCTest assertions.
  - [App Store Release](./app_store_release.md): Archive, export, verification, and distribution upload.
- Last reviewed: 2026-09-30. Signing without an Xcode account session, `devicectl device copy to`, payload-URL runs with result polling, and cold versus warm benchmarks were verified that day with Xcode 26.6 on a paired iPhone. The HealthKit, TCC, `openURL`, and console notes come from earlier verified runs.

## Goal and Boundaries

Enable an agent to execute automated workflows on a paired physical device—building, installing, passing files into the app container, triggering runs with deep links, benchmarking, and retrieving structured results—without requiring a user to open Xcode, manually tap buttons, or copy logs.

Boundaries:
- CLI automation cannot unlock an iPhone or answer permission prompts (including HealthKit and TCC dialogs). The device must be paired, trusted, and unlocked.
- Read-only diagnostics/benchmarks and live backend uploads are separate scopes. Never transmit data to a remote backend without explicit authorization.
- Deep links must use a narrow action allowlist and a unique `run_id`; automated entry points must not execute unconditionally during normal app launches.
- Physical device testing does not substitute for simulator testing (which validates synthetic UI flows and assertions), nor does a simulator run prove physical hardware behavior or real HealthKit access.
- Build logs, `.xcresult` bundles, screenshots, console dumps, and output artifacts belong in ignored local scratch. Never commit private user records, device identifiers, or credentials.
- The calling project must supply its project path, scheme, bundle ID, supported URL routes, signing parameters, result schemas, and pass/fail criteria.

## Acceptance Criteria

An agent can independently verify:
- Build and code signing succeed for the physical device, including when no Apple account is signed in to Xcode.
- The target device appears in `xcrun devicectl list devices` with a known `<device-identifier>`.
- The application installs in place via `xcrun devicectl device install app` and container access is confirmed with `xcrun devicectl device info apps --require-container-access`.
- Test input files transfer successfully into the app container via `xcrun devicectl device copy to`.
- The run executes via `--payload-url` (or `process openURL` for a warm process) with an allowlisted route and unique `run_id`.
- A structured result artifact tagged with the matching `run_id` is polled and retrieved from the container via `xcrun devicectl device copy from`, confirming a terminal `completed` status.
- Benchmarks distinguish cold and warm runs, incorporate warmup cycles, report p50/p90 percentiles, and compare numerical results against Mac-computed references.
- For authorized network uploads, backend reachability from the iPhone and backend readback are validated.

## Signing and installing

For the general signing architecture, credential handling, and single DerivedData rules, refer to the [signing model](./ios_development.md#signing).

### Offline development signing without an Xcode account session
Building for a physical device without an active Apple ID session in Xcode reveals two common failure modes:
- Passing `-allowProvisioningUpdates` without an account signed in fails with:
  `No Account for Team "<team-id>"` and `No profiles for '<bundle-id>' were found`.
- Setting `CODE_SIGN_STYLE=Manual` with `PROVISIONING_PROFILE_SPECIFIER` pointing to an Xcode-managed wildcard profile fails with:
  `Provisioning profile "iOS Team Provisioning Profile: *" is Xcode managed, but signing settings require a manually managed profile.`

What works:
- Use `CODE_SIGN_STYLE=Automatic` combined with `DEVELOPMENT_TEAM=<team-id>`, but omit `-allowProvisioningUpdates`.
- Xcode resolves the cached wildcard development profile (`iOS Team Provisioning Profile: *`) offline, provided the connected device is registered in that profile's device list.

Wildcard profile limits:
- A wildcard (`*`) profile cannot support specialized capabilities such as HealthKit, push notifications, or App Groups. Applications requiring these capabilities require an explicit App ID provisioning profile.

Reading team ID from a cached profile:
- To avoid hardcoding or manually typing team IDs in commands, extract the team ID from a cached provisioning profile:
  `security cms -D -i <path-to-profile>` then `PlistBuddy -c 'Print :TeamIdentifier:0'`
- The repository helper [`scripts/team_from_profile.sh`](../scripts/team_from_profile.sh) prints only the team ID, so it can be captured into a variable without appearing in a command or log.
- Profiles are cached in `~/Library/Developer/Xcode/UserData/Provisioning Profiles` (Xcode 16+) and `~/Library/MobileDevice/Provisioning Profiles` (legacy).

### Device addressing, build, and installation
- Address the physical device by name during build: `-destination 'platform=iOS,name=<device-name>'`.
- `devicectl` commands require the identifier displayed in the `Identifier` column of `xcrun devicectl list devices` (not the device name).
- Build outputs are placed in `<derived-data>/Build/Products/<Configuration>-iphoneos/<App>.app`.
- Install the application using `devicectl`:
  ```bash
  # Resolve team ID
  TEAM_ID="$("<skill-repo>/scripts/team_from_profile.sh")"

  # Build app for device
  xcodebuild -project "<project.xcodeproj>" -scheme "<scheme>" \
    -configuration Debug \
    -destination 'platform=iOS,name=<device-name>' \
    -derivedDataPath "<ignored-derived-data>" \
    CODE_SIGN_STYLE=Automatic DEVELOPMENT_TEAM="$TEAM_ID" \
    build

  # Install in place on device
  APP_PATH="<ignored-derived-data>/Build/Products/Debug-iphoneos/<App>.app"
  xcrun devicectl device install app --device "<device-identifier>" "$APP_PATH"
  ```
- Always install in place with the same bundle ID and development team rather than deleting and reinstalling the app.

## Files in and out of the app container

Before relying on container file operations, confirm that the application container is accessible:
```bash
xcrun devicectl device info apps --device "<device-identifier>" \
  --bundle-id "<bundle-id>" --require-container-access
```

### Copying files into the container
Push local data or model weights directly into the app sandbox:
```bash
xcrun devicectl device copy to --device "<device-identifier>" \
  --domain-type appDataContainer --domain-identifier "<bundle-id>" \
  --source "<local-file>" --destination "Documents/<name>"
```
- Speed: Verified copying 785 MB in 34 seconds into a development-signed container.
- Automated testing benefit: pushing files directly replaces an in-app download. No server has to be reachable from the phone, and the iOS local-network permission prompt, which needs a human tap, does not come up. The prompt was avoided in the verified run, not observed.
- File sharing keys: the app in the verified run set `UIFileSharingEnabled` and `LSSupportsOpeningDocumentsInPlace` in its `Info.plist`, which let a person add files through Finder. Whether `devicectl device copy to` requires these keys was not tested.

### Copying files from the container
Retrieve generated results, preference plists, or diagnostic dumps from the app sandbox:
```bash
xcrun devicectl device copy from --device "<device-identifier>" \
  --domain-type appDataContainer --domain-identifier "<bundle-id>" \
  --source "Documents/<result-file>" \
  --destination "<ignored-local-path>/<result-file>"
```
- Verified retrieving both standard app Preferences plists and one-shot JSON diagnostic/benchmark artifacts.
- The app must write the target file atomically; `devicectl` cannot invent files.

## Triggering a run

### Cold launch via payload URL
Launch the app process and deliver a deep link URL in a single step:
```bash
xcrun devicectl device process launch --device "<device-identifier>" \
  --terminate-existing \
  --payload-url "<scheme>://<allowlisted-action>?run_id=<run-id>" \
  "<bundle-id>"
```
- `--terminate-existing` terminates any currently running process before launching.
- The application's URL handler must parse the parameters, execute the requested action, and atomically write results to its container.

### Warm process execution via openURL
To trigger a new run on an already-running process without terminating or reinstalling:
```bash
xcrun devicectl device process openURL --device "<device-identifier>" \
  "<scheme>://<allowlisted-action>?run_id=<run-id>"
```
- Verified with an unchanged application PID across multiple physical-device diagnostic runs.
- Note: This is a verified capability on one app; it is not a guarantee that any arbitrary app correctly handles URLs while active.

### Console output caveats
- `xcrun devicectl device process launch --console` attaches stdout for a freshly launched process, but it blocks waiting for app exit and can mix system log noise with app output.
- Console scraping cannot attach to or capture stdout from an already-running process triggered via `process openURL`.
- Prefer writing a `run_id`-tagged artifact to the container as the definitive result channel.
- A debug-only launch argument can serve as a fallback if payload URL routing is unavailable in the app; never enable automated diagnostic execution on every normal app launch.
- Use `--json-output <ignored-path>` with `devicectl` commands to obtain machine-readable command status instead of parsing human-readable tables. A success status in `--json-output` records process launch, not that the app successfully parsed the URL or completed execution.

## Result contract

### Artifact schema and validation
Structured diagnostic and benchmark artifacts must adhere to a predictable contract:
- Include an ephemeral `run_id`, `schema_version`, and terminal status (`completed`, `error`, or `pending_permission`).
- Output bounded aggregate statistics and typed error messages rather than unbounded raw samples.
- Verify that the retrieved artifact's `run_id` and schema match the current request, and ensure the file is complete rather than a remnant of a previous execution.
- A successful run must report meaningful counts/metrics or an explicit no-data status. Zero samples or missing records alone do not prove permission denial.
- Delete stale cached artifacts after retrieval or maintain a short local retention policy.

### Polling pattern
Poll for artifact completion by repeating `devicectl device copy from` at ~10-second intervals until the file is retrieved or a timeout expires:
```bash
until xcrun devicectl device copy from --device "<device-identifier>" \
  --domain-type appDataContainer --domain-identifier "<bundle-id>" \
  --source "Documents/<result-file>.json" \
  --destination "<ignored-local-path>/<result-file>.json" 2>/dev/null; do
  sleep 10
  # check overall timeout and break on expiration
done
```

### Network write validation
For explicitly authorized remote uploads:
- Verify that the target backend is reachable from **the iPhone**. Checking reachability from Mac `localhost` does not confirm device connectivity.
- Compare backend readback records against expected payload data.
- Do not place live uploads on the same URL route as local diagnostics by default.

## Benchmarking on a device

Physical device benchmarks require accounting for device-specific initialization characteristics:
- Initial execution overhead: The first run often includes one-time initialization costs, such as GPU shader compilation. In verified tests, loading a model on first launch took 17.4 s, whereas subsequent warm launches loaded in 0.37 s.
- Separate cold and warm runs: Report cold-start and warm-state latencies separately.
- Warmup cycles: Always perform warmup iterations before timing steady-state execution.
- Distribution metrics: Measure many iterations and report distribution metrics (such as p50 and p90) rather than a single average.
- Correctness check: Compare the device's numerical outputs against reference values computed on the Mac for the exact same inputs. A latency benchmark is invalid if the computation produces incorrect output.

## Verification and recovery

Generic observed failure modes when operating on physical devices:
- `localhost` in an iPhone app resolves to the **iPhone itself**, not the host Mac. Use an authorized reachable IP address or hostname for live backends; never publish private network addresses in skill files.
- Device console streams frequently contain unrelated system warnings and private identifiers. Avoid unbounded console dumps and screenshots.
- In-place installations may report `launchServicesIdentifier: unknown`, but launching by bundle ID still functions.
- A `devicectl --json-output` success status records process launch, not URL dispatch or successful execution; verify app-owned artifacts or backend timestamps.
- Device state: If the device is disconnected, locked, or untrusted, stop execution. Do not fall back to a simulator and claim physical device success.
- CLI exit code 0 alone does not prove app dispatch or data ingestion.
- Inaccessible container: If container access fails, verify the provisioning profile and signing settings; fall back to a narrowly scoped console capture only if privacy permits.
- Missing result artifact: Inspect URL scheme parsing and app-side error logs before retrying.
- Backend configuration: If the backend configuration lacks an updated schema or allowlist, halt testing before transmitting real samples.
- Project-specific configuration: Specific routes, schemes, and test fixtures belong in project-level configuration. Record newly observed `devicectl` traps after verified runs rather than inventing hypothetical issues.

## HealthKit and TCC

This section consolidates all HealthKit and Transparency, Consent, and Control (TCC) constraints:
- CLI limitations: CLI automation cannot silently grant HealthKit or TCC system prompts, nor can it unlock an iPhone. An operator must unlock the device and interact with any required initial permission dialogs.
- Simulator vs. physical device: A simulator XCTest run only verifies fixture routes and UI elements; it does not prove access to physical HealthKit stores or real TCC authorizations.
- Scope separation: Read-only diagnostics and live uploads are distinct scopes. Obtain explicit authorization before querying additional health categories or transmitting samples to a backend.
- Narrow URL triggers: A deep link must use a strict action allowlist and a unique `run_id`. Never allow a deep link to turn every ordinary app launch into a health-data query.
- Profile entitlement limits: A wildcard (`*`) development profile cannot carry the HealthKit capability. Applications that query HealthKit must use an explicit App ID provisioning profile with the HealthKit capability enabled.
- Authorization status semantics: `HKHealthStore.authorizationStatus(for:)` reflects **write** permission only. An authorization status of `.sharingDenied` in a read-only app does not establish that reading was refused.
- Request authorization completion: Completion of `requestAuthorization` indicates only that the prompt sequence completed, not that each requested read type was granted. Use actual sample queries and treat zero samples as ambiguous.
- Install-in-place reliability: Deleting and reinstalling a development app once produced `No source with bundle identifier` during HealthKit authorization. Prefer in-place installation; do not generalize this observation to all iOS releases.
- Permission retention: Narrowing the list of requested HealthKit types in application code does not revoke read permissions previously recorded by the OS. Review existing device permissions if an earlier build requested a broader scope.
- Artifact status: Use `pending_permission` when required authorizations are missing. Treat zero returned samples as ambiguous rather than proof of denied read authorization.
