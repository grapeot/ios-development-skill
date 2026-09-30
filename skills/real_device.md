# Real Device Development and Testing

## Metadata

- Type: Workflow
- When to use: An agent must build, sign, install, trigger (via payload URL or openURL), benchmark, transfer container files, or retrieve diagnostics on a paired physical iOS device.
- Related skills:
  - [iOS Development](./ios_development.md): Root skill covering the Xcode toolchain, serial builds, DerivedData, and the [signing model](./ios_development.md#signing).
  - [Simulator Testing](./simulator_testing.md): Simulator UI automation, test acceleration, synthetic fixtures, and XCTest assertions.
  - [App Store Release](./app_store_release.md): Archive, export, verification, and distribution upload.
- Last reviewed: 2026-09-30. Signing without an Xcode account session, `devicectl device copy to`, payload-URL runs with result polling, cold versus warm benchmarks, and running app control and state channels (URL commands, status heartbeat file, and WKWebView bridges) were verified on 2026-09-30 with Xcode 26.6 on a paired iPhone. The HealthKit, TCC, and console notes come from earlier verified runs.

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
- App liveness and progression are confirmed by reading an atomic status heartbeat file from the container with advancing counters or timestamps via `xcrun devicectl device copy from`.
- A structured result artifact tagged with the matching `run_id` is polled and retrieved from the container via `xcrun devicectl device copy from`, confirming a terminal `completed` status.
- Benchmarks distinguish cold and warm runs, incorporate warmup cycles, report p50/p90 percentiles, measure through the path the app actually uses, and compare numerical results against Mac-computed references.
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
- Speed varies: Copying the same 785 MB file into a development-signed container took 34 s in one run and 85 s in another on the same Wi-Fi.
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

## Controlling a running app and reading its state

When an app is already active, choose a control and inspection channel based on direction, latency requirements, and system permissions:

| Channel | Direction | Latency | Needs | Verified |
|---|---|---|---|---|
| URL commands (`process openURL`) | Host → App | Discrete (~1–2 s per command invocation overhead) | URL scheme with action allowlist in app; no network permissions or in-app server | Yes |
| Status heartbeat file (`copy from`) | App → Host | Polling cadence (~5 s write cadence; ~1–2 s copy) | Container access, atomic file write (`.atomic`); no network permissions | Yes (recommended for liveness) |
| WKWebView message handlers | Page ↔ Native (internal) | Adds tens of milliseconds per call (see [Benchmarking](#benchmarking-on-a-device)) | `WKScriptMessageHandler` (fire-and-forget) or `WKScriptMessageHandlerWithReply` (reply); `WKURLSchemeHandler` for ES modules | Yes |
| In-app debug control server (WebSocket/HTTP) | Host ↔ App (bidirectional) | Real-time / streaming | `Network.framework`, local-network permission prompt, app in foreground, access token | No (not yet verified) |
| Safari Web Inspector | Host ↔ Web page (bidirectional) | Interactive / real-time | `isInspectable = true` (iOS 16.4+), Safari developer tools | No (not yet verified) |

The status heartbeat file is the recommended way to prove an app is alive and progressing. A `devicectl` launch success status in `--json-output` only proves that a process started, not that it is executing tasks or advancing state.

### URL commands to a running app
Deliver commands to an already-running app process using `devicectl`:
```bash
xcrun devicectl device process openURL --device "<device-identifier>" \
  "<scheme>://<allowlisted-action>?run_id=<run-id>"
```
- Process preservation: The process ID is identical before and after invocation; the application process is not restarted.
- Verified execution: In verified testing, delivering a URL action triggered a 60-decision benchmark, which executed and wrote `Documents/bench_<id>.json` to the container. Polling `devicectl device copy from` retrieved the artifact. Total round-trip was 29 s, almost all of it spent on the benchmark action itself.
- App requirements: The application must implement an allowlist of permitted URL actions.
- Channel characteristics: Requires no network permissions, no embedded HTTP/WebSocket server in the app, and no manual human taps.
- Invocation overhead: Each command dispatch and container file retrieval costs a separate `devicectl` invocation (roughly 1–2 s). This makes URL commands well-suited for discrete operations (such as running a benchmark, pausing, restarting, or updating a configuration setting), rather than real-time interactive control. (Only running a benchmark was verified; other actions are examples of discrete command shapes).

### Status heartbeat file
The status heartbeat file is the recommended mechanism for an agent to confirm that an app is alive and actively progressing:
- Liveness proof: An exit code 0 or success status from `devicectl device process launch` only confirms that a process was spawned. Reading a heartbeat file with advancing counters or timestamps proves the app is actively functioning rather than hung or crashed.
- Cadence and atomic writes: The application writes a small JSON state snapshot into its container on a fixed cadence (every 5 s in verified testing), using an atomic write (`Data.write(to:options:.atomic)`) that continuously overwrites the same file (`Documents/<status-file>.json`).
- Polling for progress: An agent copies the heartbeat file using `devicectl device copy from` whenever it needs to inspect state:
  ```bash
  xcrun devicectl device copy from --device "<device-identifier>" \
    --domain-type appDataContainer --domain-identifier "<bundle-id>" \
    --source "Documents/<status-file>.json" \
    --destination "<ignored-local-path>/<status-file>.json"
  ```
  In verified runs, reading the heartbeat twice 20 s apart confirmed state progression (game ticks advanced from 1499 to 2250, and decision counts from 79 to 129).
- Recommended schema: Include a monotonically increasing counter or timestamp (to detect stale files), the current execution phase or screen, and the specific metrics the task monitors. Report bounded aggregates only; never include private personal data.
- Web view integration: In WKWebView-based apps, state snapshots can originate from the web context: the page posts state data to native code via a message handler, and native code writes the file atomically into the container.

### Bridges inside a WKWebView-based app
When automating or benchmarking an application containing a WKWebView, communicate between web content and native code using verified bridge mechanisms:
- Page → Native (fire-and-forget): Register a `WKScriptMessageHandler` using `userContentController.add(_:name:)`. The web page dispatches messages with `window.webkit.messageHandlers.<name>.postMessage(obj)`. Verified for transmitting status heartbeat snapshots from web content to native file-writing routines.
- Page → Native (with reply): Register a `WKScriptMessageHandlerWithReply` using `addScriptMessageHandler(_:contentWorld:name:)`. In JavaScript, `window.webkit.messageHandlers.<name>.postMessage(obj)` returns a `Promise` that resolves to the native reply. Verified for executing model inference decisions requested by web logic.
- Bundle assets via custom URL scheme: Serving local bundle files through a custom URL scheme handler (`WKURLSchemeHandler`, such as `<custom-scheme>://local/index.html`) allows ES modules to load correctly on physical devices.
- Bridge cost: calls that cross the script bridge were measurably slower than direct native calls; see [Benchmarking on a device](#benchmarking-on-a-device). Benchmark through the path the app actually uses.

### Options not yet verified
The following mechanisms are theoretical alternatives that have not yet been verified on a physical device. Do not present or rely on them as working without verification:
- Embedded debug control server (WebSocket or HTTP via `Network.framework`): Could provide real-time, bidirectional control and streaming state telemetry. Because it operates over standard IP, it might function over a tailnet where `devicectl` fails. Anticipated constraints and costs to confirm: triggers the iOS local-network permission dialog on first LAN connection (requiring a human tap), requires the app to remain actively in the foreground (iOS suspends execution when the device is locked or the app is backgrounded), and requires an access token to secure control endpoints.
- Safari Web Inspector: Attaching the desktop Safari Web Inspector to an inspectable web view (`isInspectable = true`, iOS 16.4+) to evaluate JavaScript directly inside web content from the host Mac.

## Result contract

### Heartbeat versus one-shot result files
Distinguish between ongoing status telemetry and final execution artifacts:
- **Status heartbeat file**: Overwritten continuously on a fixed cadence (e.g. every 5 s) with current state snapshots, advancing counters, or timestamps to prove ongoing liveness and progress.
- **One-shot result file**: Tagged with a unique `run_id` and written once when an execution, benchmark, or diagnostic action reaches a terminal status (`completed`, `error`, or `pending_permission`).

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
- Measure through the path the app actually uses: If an application interacts through an internal bridge (such as a WKWebView message handler to native code), benchmark end-to-end latency through that bridge rather than calling native code directly. In verified testing, a decision passing through `page -> native bridge -> model` had p50 latency of about 420–440 ms, compared to about 380 ms when the same model was called directly by native code. The 40–60 ms difference includes the bridge and time spent waiting behind other requests, and possibly GPU contention with page rendering; these were not measured separately.
- Correctness check: Compare the device's numerical outputs against reference values computed on the Mac for the exact same inputs. A latency benchmark is invalid if the computation produces incorrect output.

## Verification and recovery

Generic observed failure modes when operating on physical devices:
- `localhost` in an iPhone app resolves to the **iPhone itself**, not the host Mac. Use an authorized reachable IP address or hostname for live backends; never publish private network addresses in skill files.
- Reaching the device over a tailnet: With the iPhone and the Mac on the same Tailscale tailnet but on different physical networks (phone on cellular), `tailscale ping` reached the phone directly (66 ms), yet `xcrun devicectl list devices` showed the phone as `unavailable`, and browsing Bonjour on the Mac (`dns-sd -B _remotepairing._tcp local.`) did not show the phone's pairing service. CoreDevice discovers devices over Bonjour, which the tailnet did not carry. Install, file copy, launch, and openURL were therefore unavailable until the phone was back on the same LAN; then it showed `available (paired)` again.
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
