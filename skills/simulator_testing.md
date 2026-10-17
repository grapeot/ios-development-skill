# Simulator Testing Skill

## Metadata

- Type: Focused workflow
- When to use: Validating an iOS app's UI, user flows, and behavior on an iOS simulator using Xcode — building, running accelerated test loops (`test-without-building`), capturing screenshots, executing XCTest/XCUITest interactions, inspecting `.xcresult` test failures, and performing read-and-verify visual checks.
- Related skills:
  - [iOS Development](./ios_development.md) — Root skill covering toolchain setup, build discipline, simulator vs. device routing, caller input requirements, and artifact privacy policies.
  - [Real Device](./real_device.md) — Hardware installation, file transfer, URL triggers, result retrieval, and on-device performance profiling.
  - [App Store Release](./app_store_release.md) — Archiving, signing, exporting, validating, and uploading distribution builds.
- Last reviewed: 2026-09-30. Merged from the simulator UI automation and test acceleration skills. Their commands and traps were verified on real projects with Xcode 26.x and iPhone simulators; the XCUITest gesture notes were checked against the SDK headers and swiftc probes.

## Goal and Boundaries

### Goal
Produce reproducible, automated evidence that an iOS app renders correctly and behaves as expected on an iOS simulator, without exposing private data (credentials, endpoint URLs, auth tokens, account names, or local configurations). A successful run validates the target flow through automated tests, targeted simulator interaction, screenshots, and an explicit read-and-verify inspection of the captured UI state.

This skill supports two complementary verification workflows:
- **Behavioral testing**: Running unit tests and XCTest/XCUITest suites using accelerated test loops.
- **Visual-only verification**: Checking layout, typography, and visual styling ("did this change render as intended?") via a deterministic launch, screenshot capture, and visual inspection without requiring full XCTest assertion scripts.

### Boundaries
- **Simulator only**: Drives iOS simulators using `xcodebuild` and `xcrun simctl`. For testing, profiling, or benchmarking on physical hardware via `xcrun devicectl`, see [Real Device](./real_device.md).
- **Backend state isolation**: Validates the iOS app surface. Do not mutate production backends; default to deterministic fixture mode with synthetic data.
- **Live API testing boundary**: Live testing against an external API is a separate mode requiring explicit authorization. When live testing is requested, use synthetic test accounts and fixtures. Never capture screens displaying real credentials or sensitive payloads. Assert HTTP status codes and IDs without dumping confidential bodies.
- **Shared foundations**: Toolchain pinning (`DEVELOPER_DIR`), serial build constraints, caller input requirements, and artifact privacy rules live in the root skill. Refer directly to:
  - [Toolchain selection](./ios_development.md#toolchain)
  - [Build discipline](./ios_development.md#build-discipline)
  - [Simulators and devices](./ios_development.md#simulators-and-devices)
  - [Inputs from the calling project](./ios_development.md#inputs-from-the-calling-project)
  - [Artifacts and privacy](./ios_development.md#artifacts-and-privacy)

## Acceptance Criteria

A simulator testing or UI automation run is complete when:
- `xcodebuild build` (for visual checks) or `xcodebuild test` / `test-without-building` (for behavioral checks) exits 0 for the designated simulator destination.
- For behavioral runs, the flow under test is validated with XCTest assertions or an equivalent deterministic click-through script.
- Any manual `simctl` launch uses deterministic fixture launch arguments unless live testing was explicitly requested.
- Screenshots covering the screens under review are captured and saved to an ignored local scratch path (such as `tmp/visual_qa/`).
- Each captured screenshot is reviewed for visual correctness, rendering glitches, and privacy leakage before reporting.
- On test failure, the failing test method, assertion message, and source line are extracted from the `.xcresult` bundle using `xcresulttool`.
- The agent reports the simulator destination, commands executed, screenshot paths, test/build status, and any residual risks.

## Per-App Inputs

Per-app inputs are supplied by the calling project or discovered from its workspace configuration (see [Inputs from the calling project](./ios_development.md#inputs-from-the-calling-project)):
- **Project or workspace path**: `<project.xcodeproj>` or `<workspace.xcworkspace>`
- **Scheme**: `<scheme>` (discoverable via `xcodebuild -list -project "<project.xcodeproj>"`)
- **Bundle identifier**: `<bundle-id>` (for `simctl launch` and `simctl terminate`)
- **Simulator destination**: A destination string `platform=iOS Simulator,name=<device-name>,OS=<version>` or a pinned `id=<simulator-uuid>` where OS meets or exceeds the app's deployment target (see [Simulators and devices](./ios_development.md#simulators-and-devices))
- **Deterministic launch arguments**: Flags that configure the app in a mock or fixture state with synthetic data (e.g. `["<FIXTURE_FLAG_1>", "<FIXTURE_FLAG_2>"]`)
- **Accessibility identifiers**: Semantic identifiers (`tab.<name>`, `<screen>.<control>`) used to locate and assert UI elements
- **Passing flow**: The minimal sequence of screens, actions, or assertions defining success

## Fast Test Loop and Escalation Order

### Serial Execution Rule
Build and test sequentially. Never run parallel `xcodebuild` jobs against the same project or DerivedData path; concurrent executions fail with `build.db: database is locked`. See [Build discipline](./ios_development.md#build-discipline).

### Fast Test Loop
To iterate quickly, run `build-for-testing` once, then execute repeated `test-without-building` runs:

```bash
# Build test bundles once
xcodebuild build-for-testing \
  -project "<project.xcodeproj>" \
  -scheme "<scheme>" \
  -destination 'id=<simulator-uuid>'

# Run targeted test without re-compiling
xcodebuild test-without-building \
  -project "<project.xcodeproj>" \
  -scheme "<scheme>" \
  -destination 'id=<simulator-uuid>' \
  -only-testing:<bundle>/<suite>/<test>
```

Pin the simulator by UUID (`id=<simulator-uuid>`) when one is available, so the build cache and test results stay stable across runs.

### Targeted Runs
Run the smallest stable target first to minimize feedback latency:

```bash
# Focused unit test suite
xcodebuild test-without-building \
  -project "<project.xcodeproj>" \
  -scheme "<scheme>" \
  -destination 'id=<simulator-uuid>' \
  -only-testing:<TestBundle>/<TestSuite>

# Single UI test
xcodebuild test-without-building \
  -project "<project.xcodeproj>" \
  -scheme "<scheme>" \
  -destination 'id=<simulator-uuid>' \
  -only-testing:<UITestBundle>/<UITestSuite>/<testMethod>

# Multiple focused suites in one invocation
xcodebuild test-without-building \
  -project "<project.xcodeproj>" \
  -scheme "<scheme>" \
  -destination 'id=<simulator-uuid>' \
  -only-testing:<TestBundle>/<SuiteA> \
  -only-testing:<TestBundle>/<SuiteB>
```

### Escalation Order
When fixing failures or iterating on code, escalate in this order:
1. Run the single failing test using `test-without-building`.
2. If source files changed, run `build-for-testing` once, then re-run the single test.
3. Run the focused suite covering the affected feature.
4. Run full `xcodebuild test` only after focused tests pass.

### Bounded Failure Recovery

When a simulator test run stalls, exceeds an outer caller deadline, or exits with incomplete output, recover through a bounded loop rather than polling indefinitely or rerunning the full suite blindly.

#### Pre-Run Contract and Status Separation

- Declare per-phase and end-to-end deadlines, expected verification evidence, and ownership of the target simulator destination and `-derivedDataPath` before starting a run.
- Exact time limits are chosen by the caller; do not rely on a global hard minute cap or invent vendor CLI timeout flags.
- Record build status, test assertion outcome, runner process state, and result bundle status separately.
- Never infer wrapper or script success from passing assertion lines in stdout, and treat missing completion evidence as incomplete/recoverable rather than passing.

#### Assertion Outcome vs. Teardown and Packaging

- Separate assertion execution from runner shutdown and `.xcresult` packaging.
- In an observed simulator UI test run, compilation took 8 s while the test phase ran 734 s (744 s total): assertion failures were already logged before the outer coding CLI deadline expired, while the owned test process remained active afterward.
- When an assertion fails in the log, preserve the first failure immediately and treat that test as failed; do not wait merely for the `xcodebuild` PID to disappear. Separately decide whether to let an owned run collect further evidence within its declared budget or stop it for recovery.
- Interrupted runs can leave partial logs or unreadable `.xcresult` bundles. A secondary pipeline exit such as `tee` status `141` is compatible with `SIGPIPE` when a reader closes early, not proof of the entire internal cause.
- If `.xcresult` is unavailable or unreadable, inspect the raw same-run build/test logs and exit statuses rather than triggering a blind full-suite rerun. Do not generalize slow completion to machine load or concurrent tests without same-run evidence.

#### Post-Timeout Inspection and Scoped Cleanup

- Do not assume an outer timeout canceled child `xcodebuild` processes or daemon-backed diagnostics; in the observed recovery, an owned `simctl diagnose --timeout=600` process remained active after its caller timed out.
- Before reusing `-derivedDataPath` or a simulator destination after a timeout, inspect the owned descendant process/group and the pinned destination.
- Stop only confirmed owned stale jobs using the caller's supported cleanup mechanism. Avoid global process kills and never shut down or erase another job's simulator.

#### Bounded Recovery Loop

1. Isolate the failing test case with `-only-testing:<Bundle>/<Suite>/<testMethod>`.
2. Make one evidence-backed change addressing the observed failure.
3. Run a targeted `test-without-building` retest (or `build-for-testing` first if source changed).
4. If the failure repeats unchanged or the deadline is reached, stop polling or resuming, preserve same-run artifacts, and report or hand off the explicit remaining blocker.

#### UI Geometry, Orientation, and Scroll Triage

- Verify the actual selected screen, app/container geometry, and viewport after rotation or re-layout rather than checking only `XCUIDevice.shared.orientation` or `element.exists`.
- For offscreen, tall, or clipped content, check visible viewport intersection and use bounded, direction-aware scrolling. Do not infer an application defect from `isHittable == false` alone.
- Do not generalize one failing frame predicate or swipe into a universal API limitation, and do not claim an unresolved rotation failure passed.
- Never weaken acceptance merely to make a failing test pass. Keep the [XCUITest gesture and orientation traps](#xcuitest-gesture-and-layout-gotchas-xcode-26x-iphone-simulators) in force.

#### Manual-Testing Deployment Boundary

- When the user explicitly requests deployment for manual testing despite a failing automated test, report the automated failure separately from signed build, install, and launch status.
- Never claim automated acceptance from a manual deployment, and do not treat that request as blanket authorization to skip tests.

## Visual Verification and Command Patterns

### Scheme Discovery and Full Test Run
Discover schemes in the project:
```bash
xcodebuild -list -project "<project.xcodeproj>"
```

Run the complete test suite on a simulator:
```bash
xcodebuild test \
  -project "<project.xcodeproj>" \
  -scheme "<scheme>" \
  -destination 'platform=iOS Simulator,name=<device-name>,OS=<version>'
```

### Visual-Only Check (Build, Install, Launch, Screenshot)
For visual design checks where full XCTest assertions are unnecessary:

```bash
# 1. Build the app binary for simulator
xcodebuild build \
  -project "<project.xcodeproj>" \
  -scheme "<scheme>" \
  -destination 'platform=iOS Simulator,name=<device-name>,OS=<version>'

# 2. Install the built app onto the target simulator
# Resolve the .app bundle inside DerivedData (prefer the newest build product; avoid unexpanded wildcards inside quotes)
xcrun simctl install "<simulator-uuid>" "<derived-data>/Build/Products/<Configuration>-iphonesimulator/<App>.app"

# 3. Launch the app in a deterministic fixture state
xcrun simctl launch "<simulator-uuid>" <bundle-id> <deterministic-launch-args>

# 4. Capture the screenshot
xcrun simctl io "<simulator-uuid>" screenshot "tmp/visual_qa/<screen>.png"
```

For full-page detail screens that exceed a single viewport, prefer an in-test scroll-and-stitch helper over a single `io screenshot`, and consider passing a launch argument that hides the tab bar.

## Read/Verify Loop

Inspect each captured screenshot before concluding that a flow passed:
- **Navigation state**: Did the app navigate to the expected screen, or did launch stall on a splash screen or error state?
- **Control visibility**: Are the required UI controls visible, correctly positioned, and in the expected enabled/disabled state?
- **Visual fidelity**: Does the specific UI styling, layout change, or bug fix render accurately?
- **Privacy compliance**: Does the screen contain only synthetic fixture data, free of real email addresses, URLs, or tokens?
- **System overlays**: Is any simulator dialog, permission alert, or keyboard overlay obscuring the interface?

If the rendered state is ambiguous, perform a deterministic action and take another screenshot rather than guessing from stale imagery.

## UI Test Stability and Fixtures

- **Semantic identifiers**: Anchor UI tests on app-owned accessibility identifiers (`tab.<name>`, `<screen>.<control>`). Never rely on system menus, paste popovers, raw screen coordinates, or fragile SwiftUI text layout hierarchies. Identifiers must be stable and semantic rather than positional.
- **Launch-argument fixtures**: Pass launch arguments to set up predictable test states:
  ```swift
  app.launchArguments = ["<FIXTURE_FLAG_1>", "<FIXTURE_FLAG_2>"]
  ```
  Use launch arguments for data prefilling instead of manipulating `UIPasteboard` or system Paste menus. System UI interactions introduce permission popups and timing flakiness that obscure application regressions.

## Failure Inspection with xcresulttool

When `xcodebuild` logs generic failures such as `TEST EXECUTE FAILED`, inspect the `.xcresult` bundle path printed near the end of the log output:

```bash
xcrun xcresulttool get test-results tests --path "<path>.xcresult"
```

This extracts the failing test case, error message, and source file line number directly, avoiding the need to sift through large build logs.

## Known Failure Modes and Traps

- `build.db: database is locked`: Concurrent `xcodebuild` processes ran against the same DerivedData or project directory. Enforce serial execution.
- `App installation failed: Requires a Newer Version of iOS`: The targeted simulator runtime OS is older than the app's `IPHONEOS_DEPLOYMENT_TARGET`. Select a simulator with an OS version at or above the deployment target. A booted simulator with an outdated OS fails during install *after* compilation has already succeeded.
- `simctl screenshot` fails or prints usage: Route screenshot commands through `xcrun simctl io <simulator-uuid> screenshot <path>`. Recent Xcode releases route capture operations through `io`.
- Screenshot shows stale UI: Terminate the running app (`xcrun simctl terminate "<simulator-uuid>" <bundle-id>`), reinstall the newly built `.app`, relaunch with deterministic fixture arguments, and pause briefly before capturing.
- UI test runner launch failure with `TEST SUCCEEDED`: Xcode occasionally fails to launch an xctrunner process during teardown while the overall test run succeeded. Trust the final `xcodebuild` exit status and test-case list, but re-run if the launch failure coincided with the flow under review.
- Standalone SourceKit diagnostic errors (`No such module Testing` / `No such module XCTest`): Standalone SourceKit lacks target build context. Use target-aware `xcodebuild test` as the source of truth for test compilation.
- Simulator clones: Xcode test parallelism can spawn clone simulators (e.g. `Clone 1 of <device-name>`). Treat clone creation as normal unless the runner fails before test execution begins. If runner launch fails but a test assertion failure is also logged, investigate the test assertion first.
- Privacy leaks in artifacts: Screenshots or test results containing personal data or real secrets must be deleted immediately. Re-run using synthetic fixture flags, and ensure local scratch paths (e.g. `tmp/visual_qa/`) are ignored by version control (see [Artifacts and privacy](./ios_development.md#artifacts-and-privacy)).

## XCUITest Gesture and Layout Gotchas (Xcode 26.x, iPhone Simulators)

Verified empirically against XCUITest SDK headers and swiftc probes:

- **No `drag` APIs on iPhone**: `XCUICoordinate.drag(by:duration:tapCount:)` and `XCUIElement.drag(from:to:)` do not exist in this SDK generation. Furthermore, `XCUICoordinate.scroll(byDeltaX:deltaY:)` is pointer-only and fails at runtime with `"Pointer events are not supported for this device"`. For controlled scrolling without fling momentum, use:
  ```swift
  coordinate.press(forDuration: 0.1, thenDragTo: otherCoordinate)
  ```
  A duration of 0.1 s stays below the system long-press threshold, functioning as a controlled drag.
- **Swipes fling lazy content out of the viewport**: Calling `app.swipeUp()` on a tall `List` or `LazyVGrid` imparts momentum; an element found during deceleration can un-materialize 1–2 s later. In scroll loops, poll with `element.waitForExistence(timeout:)` (a static `element.exists` check races the deceleration animation) and break on the first positive match.
- **Lazy grid cells only exist inside the viewport**: SwiftUI de-allocates off-screen cells in lazy containers. When asserting content in a long list or grid, assert visible sections while scrolling progressively (scroll, assert, scroll further, assert). Do not attempt to assert elements at opposite ends of a lazy container from a single static scroll position.
- **UI suites inherit previous suite's screen orientation**: A test suite that changes orientation (e.g. via `XCUIDevice.shared.orientation = .landscapeRight`) leaves the simulator in landscape, corrupting subsequent test suites executed within the same `xcodebuild` run. Explicitly reset `XCUIDevice.shared.orientation = .portrait` in the `setUp` of every suite expecting portrait layout.
- **State changes that trigger container re-layout un-materialize active elements**: Modifying a control that changes the view hierarchy (e.g. toggling a setting that inserts a tab into a `TabView`) causes SwiftUI to re-evaluate the container layout, often resetting scroll position to the top and un-materializing the active cell from the accessibility tree for several seconds. Assert the observable outcome (such as the presence of the new tab) rather than re-reading the triggering control.
