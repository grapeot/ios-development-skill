# Real Device UI Automation

## Metadata

- Type: Workflow
- When to use: Drive, inspect, and interact with the user interface of installed or App Store applications on a paired physical iOS device using a development-signed WebDriverAgent runner, without requiring target app source code, custom deep-link handlers, or container file access.
- Related skills:
  - [iOS Development](./ios_development.md): Root skill covering toolchain setup, serial builds, DerivedData, and the [signing model](./ios_development.md#signing).
  - [Real Device Development and Testing](./real_device.md): Building, installing, container file transfer, deep-link triggers, and on-device benchmarks for apps with source code.
  - [Simulator Testing](./simulator_testing.md): Fast simulator UI automation and XCTest verification loops.
- Last reviewed: 2026-10-15. Verified on a physical iPhone running iOS 27.2 with Xcode 27.0 and WebDriverAgent v16.15.0 (upstream commit `e7e2665a00633dc174d7fc579f7e606bc9ba782a`).

## Goal and Boundaries

Drive automated UI workflows—inspecting element hierarchies, clicking, typing, tapping screen points, swiping, and capturing screenshots—on existing applications installed on a paired physical device.

Boundaries:
- Target app independence: Controls existing App Store or system apps in place without app source code, container file access, reinstallation, jailbreaking, or re-signing the target app.
- Device prerequisites: Physical device must be paired, trusted, unlocked, and have Developer Mode enabled. CLI automation cannot unlock a device or answer system permission prompts.
- Security and authorization: Automated UI driving does not bypass iOS security barriers. Human authorization is strictly required for device passcode/biometrics, system permission dialogs, account sign-outs, or sensitive external transactions.
- Runner separation: WebDriverAgent (WDA) runs as an independent development-signed XCTest runner. It does not provide access to the target app's sandbox, keychain, or local cookies.
- Network isolation: WDA exposes unauthenticated HTTP JSON endpoints. Communicate only over local endpoints (such as the CoreDevice tunnel); never bind or forward the WDA port to public networks.
- Data hygiene: Hierarchy trees, screenshots, and session files may contain sensitive application data or credentials. Save all artifacts to private scratch locations outside tracked repositories.

## Acceptance Criteria

An agent can independently verify:
- WDA runner builds via `build-for-testing` with valid development signing; cached wildcard signing without account login worked in the verified environment.
- WDA runner launches via `test-without-building`, and `GET /status` returns `"ready": true` within a bounded 60-second polling window.
- The endpoint demonstrably reaches the selected device. CoreDevice IPv6 tunnel access worked in the verified environment; other transport setups need their own verification.
- A session opens against the target bundle ID with `shouldTerminateApp: false` and `forceAppLaunch: false`, attaching to the app without resetting state.
- UI elements are located via accessibility identifiers, predicate strings, or class chains, asserting single matches.
- Actions (clicks, typing, taps, swipes) complete, and UI state change is confirmed by re-reading accessibility hierarchy or screenshots rather than inferring success from HTTP status.
- Closing the WDA session preserves target-app data. Shutdown halts the service; verify the owned xcodebuild process exits, cleaning it up if necessary.

## Upstream Runner and Environment

WebDriverAgent is maintained upstream at [appium/WebDriverAgent](https://github.com/appium/WebDriverAgent). Verified using tag `v16.15.0` (commit `e7e2665a00633dc174d7fc579f7e606bc9ba782a`).
- Pin the WDA checkout to a fixed tag or commit; toolchain or WDA version updates require rebuilding the runner. Older iOS versions have not been verified. Consult the Appium [run-preinstalled documentation](https://appium.github.io/appium-xcuitest-driver/latest/guides/run-preinstalled-wda/) for version caveats.
- On iOS 27, launching a preinstalled runner via `devicectl` alone has known limitations; the verified operational path is `xcodebuild ... test-without-building`.

## Bootstrap: Build the Runner Once

Build the runner once per toolchain or WDA checkout using automatic offline signing and a cached wildcard profile:

First clone the pinned upstream tag into a private work directory. Set `WDA_SOURCE_DIR`, `WDA_DERIVED_DATA`, `IOS_DEVICE_ID`, and a unique `WDA_BUNDLE_ID` (for example `com.example.AutomationRunner`) locally. Set and validate `DEVELOPER_DIR` as described in the root skill. Do not commit their machine-specific values. Create the output/log directories before running commands.

```bash
TEAM_ID="$("<skill-repo>/scripts/team_from_profile.sh")"
xcodebuild -project "$WDA_SOURCE_DIR/WebDriverAgent.xcodeproj" \
  -scheme WebDriverAgentRunner \
  -configuration Debug \
  -destination "id=$IOS_DEVICE_ID" \
  -derivedDataPath "$WDA_DERIVED_DATA" \
  CODE_SIGN_STYLE=Automatic \
  DEVELOPMENT_TEAM="$TEAM_ID" \
  PRODUCT_BUNDLE_IDENTIFIER="$WDA_BUNDLE_ID" \
   build-for-testing > "$PRIVATE_BUILD_LOG" 2>&1
```

The resulting runner bundle ID on device gains the `.xctrunner` suffix (e.g. `$WDA_BUNDLE_ID.xctrunner`). The target app remains unmodified.

Build logs can disclose signing/team/device identifiers. Keep them private and inspect errors locally. If pairing, Developer Mode, UI Automation permissions, or signing trust is missing, ask the user to complete the relevant on-device prompt; do not bypass it.

## Recurring Run: Launch and Verify Service

Launch the prebuilt runner without rebuilding, log output to a private file, and retain the process ID:

```bash
xcodebuild -project "$WDA_SOURCE_DIR/WebDriverAgent.xcodeproj" \
  -scheme WebDriverAgentRunner \
  -configuration Debug \
  -destination "id=$IOS_DEVICE_ID" \
  -derivedDataPath "$WDA_DERIVED_DATA" \
  test-without-building > "$PRIVATE_LOG_PATH" 2>&1 &
WDA_PID=$!
```

### Tunnel Discovery and Readiness Check

1. Query device network details:
   ```bash
   xcrun devicectl device info details --device "$IOS_DEVICE_ID"
   ```
2. Locate the active CoreDevice tunnel IPv6 address and format the URL with brackets:
   ```bash
   export WDA_URL="http://[$TUNNEL_IPV6]:8100"
   ```
   Do not hardcode device IP addresses or assume stability across reconnects.
3. Poll `/status` in a bounded loop (up to 60 seconds). A healthy runner returns `"ready": true`. If the timeout expires or the process terminates, inspect `$PRIVATE_LOG_PATH`.

An already-paired, Developer-Mode-enabled phone can still request its passcode to **Enable UI Automation** for XCTest, including on a later runner launch. In the observed case, leaving that prompt unanswered caused `Timed out while enabling automation mode`. Inspect the device screen and let the user approve it; do not reinstall the target app or repeatedly restart the runner. Device pairing and the ordinary lock-state query alone do not prove UI-automation consent.

## Driving the UI with the Helper Client

Use the standard-library client [`scripts/wda_client.py`](../scripts/wda_client.py) to manage sessions and dispatch commands. The client bypasses ambient HTTP proxies to keep device traffic local.

### Session Lifecycle

Manage the active session with an external session state file:

```bash
# Open session attaching to target app without termination
python3 "<skill-repo>/scripts/wda_client.py" --url "$WDA_URL" \
  --session-file "$SESSION_FILE" open --bundle-id "com.example.app"

# Close session and remove session file
python3 "<skill-repo>/scripts/wda_client.py" --url "$WDA_URL" \
  --session-file "$SESSION_FILE" close

# Stop WDA service completely and clean up
python3 "<skill-repo>/scripts/wda_client.py" --url "$WDA_URL" \
  --session-file "$SESSION_FILE" shutdown
# After shutdown, verify /status no longer responds and wait for the owned
# xcodebuild process to exit. Only terminate this recorded PID if still alive.
```

Opening a new session supersedes the prior WDA session. Confirm exclusive device ownership first; this behavior can interrupt another operator and is not a coordination lock.

### Inspecting Hierarchy and Capturing State

Write hierarchy dumps and screenshots with restricted permissions (0600) to pre-existing private directories:

```bash
# Capture full accessibility JSON tree
python3 "<skill-repo>/scripts/wda_client.py" --url "$WDA_URL" \
  --session-file "$SESSION_FILE" source --output "$PRIVATE_SCRATCH/tree.json"

# Capture screen image
python3 "<skill-repo>/scripts/wda_client.py" --url "$WDA_URL" \
  --session-file "$SESSION_FILE" screenshot --output "$PRIVATE_SCRATCH/screen.png"
```

### Finding Elements and Synthesizing Input

Target elements using accessibility identifiers first. Pass sensitive text via files to keep credentials out of process tables:

```bash
# Locate element by accessibility id (or: predicate string, class chain, class name, xpath)
python3 "<skill-repo>/scripts/wda_client.py" --url "$WDA_URL" \
  --session-file "$SESSION_FILE" find --using "accessibility id" --value "login_button"

# Click element
python3 "<skill-repo>/scripts/wda_client.py" --url "$WDA_URL" \
  --session-file "$SESSION_FILE" click --element "$ELEMENT_ID"

# Type text into focused element without logging contents
python3 "<skill-repo>/scripts/wda_client.py" --url "$WDA_URL" \
  --session-file "$SESSION_FILE" type --element "$ELEMENT_ID" --text-file "$INPUT_FILE"

# Coordinate tap (points, not raw image pixels)
python3 "<skill-repo>/scripts/wda_client.py" --url "$WDA_URL" \
  --session-file "$SESSION_FILE" tap --x 195 --y 420

# Synthesize keyboard input into active responder
python3 "<skill-repo>/scripts/wda_client.py" --url "$WDA_URL" \
  --session-file "$SESSION_FILE" keys --text-file "$INPUT_FILE"

# Swipe gesture
python3 "<skill-repo>/scripts/wda_client.py" --url "$WDA_URL" \
  --session-file "$SESSION_FILE" swipe --direction up

# Re-activate target app if backgrounded
python3 "<skill-repo>/scripts/wda_client.py" --url "$WDA_URL" \
  --session-file "$SESSION_FILE" activate --bundle-id "com.example.app"
```

## Traps and Verification

| Observed Symptom | Underlying Cause | Verified Remedy |
|---|---|---|
| HTTP 200 returned, but text field is empty | `typed: true` is a protocol delivery ACK, not a guarantee that the UI retained input (e.g. WebView OTP fields or custom controls). | Focus the element explicitly before typing; for split OTP fields, enter digits into individual elements or use coordinate tap followed by `keys`. Always re-read the hierarchy or screen to verify state. Never log OTPs or passwords. |
| Click command times out, but page advanced | Network latency or animation quiescence delay caused WDA to exceed timeout after triggering event. | Do not blindly retry clicks (risk of duplicate payments or actions). Inspect a fresh screenshot or element tree to determine if navigation already succeeded. |
| Runner log reports sandbox denial for preferences | Upstream WDA setup attempts to disable keyboard autocorrection/prediction. This device rejected those writes. | Do not generalize the denial to other OS versions or claim WDA never changes keyboard preferences. Record existing settings and review upstream setup behavior before use. |
| Coordinate tap hits wrong UI element | High-density Retina displays (e.g. 3x display scale) differ between image pixel dimensions and logical screen points. | Calculate tap coordinates in logical screen points (`points = pixels / scale`) using fresh viewport dimensions. |
| Ambiguous element matching | Generic selectors match multiple off-screen or duplicate elements. | Use strict single-match assertions. If zero or multiple elements match, dump the tree and refine with predicate strings or class chains. |
| App data and cookies inaccessible | WDA controls the accessibility layer; it has no entitlement to inspect target app container files. | Do not promise container file dumps for third-party apps. Use in-app deep links and container tools ([Real Device](./real_device.md)) only when building source apps. |
| Session close leaves WDA reachable | Closing a WebDriver session is different from stopping the XCTest server. | Use `/wda/shutdown` and verify the endpoint and owned process stop. Its response is plain text `Shutting down`, not WebDriver JSON. |
| Runner restart times out enabling automation mode | XCTest may be waiting for an on-device passcode/Enable UI Automation prompt, even though the device is connected. | Capture or inspect the screen, ask the user to approve locally, then retry the owned runner once; do not record or ask for the passcode. |
