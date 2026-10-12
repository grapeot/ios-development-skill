# Apple Watch Development and Testing

## Metadata

- Type: Focused Workflow
- When to use: Developing, building, signing, and installing watchOS applications on a physical Apple Watch via a paired iPhone and Xcode / devicectl command-line tooling.
- Related skills:
  - [iOS Development](./ios_development.md): Root skill covering the Xcode toolchain, serial builds, DerivedData, and the [signing model](./ios_development.md#signing).
  - [Real Device Development and Testing](./real_device.md): Physical iPhone/iPad device development, container access, URL triggers, and on-device benchmarks.
- Last reviewed: 2026-10-12

## Goal and Boundaries

Enable an agent to prepare, build, sign, and install watchOS applications on a physical Apple Watch from the command line using official Apple tooling.

Boundaries:
- The Apple Watch is not a direct USB target for the Mac. It is reached exclusively through its paired iPhone.
- CLI automation cannot bypass device passcode locks or grant on-device permissions (including HealthKit prompts). The watch must be unlocked and awake, and permissions must be granted directly on the watch.
- Wildcard provisioning profiles cannot carry HealthKit; an explicit App ID and provisioning profile are required.
- Physical Apple Watch testing complements but does not replace simulator testing (see [`./simulator_testing.md`](./simulator_testing.md)) or iPhone physical device workflows (see [`./real_device.md`](./real_device.md)).
- Calling projects must supply the project path (`<App.xcodeproj>`), watch scheme (`<watch-scheme>`), bundle ID (`<bundle-id>`), destination watch UDID (`<watch-udid>`), and timeout parameters.

## Acceptance Criteria

An agent can independently verify:
- The Apple Watch is paired with the Mac via Device Hub and paired iPhone connectivity.
- Developer Mode is active on the watch (visible under *Settings > Privacy & Security > Developer Mode*).
- The watch appears in `xcrun devicectl list devices` with identifier `<watch-udid>` and transitions from `connected (no DDI)` to `connected` after DDI preparation.
- Automatic signing with `-allowProvisioningUpdates` and an active Xcode account session generates an explicit provisioning profile with HealthKit capabilities that includes the `<watch-udid>`.
- `xcodebuild` builds the watchOS scheme for the watch destination (`platform=watchOS,id=<watch-udid>`) with `-destination-timeout <seconds>`.
- The application installs on the physical watch via `xcrun devicectl device install app --device <watch-udid> <path>/<Watch>.app`, outputting `App installed: <bundle-id>`.
- First-launch HealthKit prompts are surfaced for manual operator interaction on the watch.

## Prerequisites and pairing

### Device management UI (Device Hub)
In recent Xcode releases, the legacy "Devices and Simulators" window is replaced by **Device Hub**. Access Device Hub via:
- *Xcode > Open Developer Tool > Device Hub*, or
- The run-destination menu > *Manage Devices…*

Device Hub lists simulators, connected physical devices, and paired Apple Watches.

### Network and host routing through paired iPhone
The Apple Watch does not act as a direct USB development target. Connecting the watch's magnetic charging cable to the Mac provides power only; it establishes no data link or developer connection.

The watch is reached entirely **through the paired iPhone**:
- The iPhone must be paired and trusted with the Mac (connected by USB or accessible on the same local network).
- Both the iPhone and Apple Watch must have Bluetooth and Wi-Fi enabled.

### Explicit pairing
Xcode does not auto-discover the watch. Pairing between the Mac and the watch must be initiated explicitly through either of two entry points:
- **Device Hub**: Click **"+" → "Pair Nearby Device"**.
- **On the watch**: Open **Settings → Privacy & Security → Developer Mode** to access the pairing control.

When prompted, a numeric pairing code appears on the watch face; confirm the pairing code on the watch to establish trust.

## Developer Mode on the watch

Physical watchOS devices require Developer Mode enabled before installing development builds:
- Navigate to **Settings → Privacy & Security → Developer Mode** on the watch and toggle Developer Mode on.
- When prompted by watchOS, restart the Apple Watch to apply the change.

### Missing Developer Mode toggle
If *Settings > Privacy & Security* on the watch lacks a Developer Mode entry:
1. Ensure the watch has been paired with the Mac in Device Hub at least once.
2. **Restart the Apple Watch**.
3. After rebooting, open *Settings > Privacy & Security*; the Developer Mode toggle will appear. Toggle it on and restart the watch when prompted.

## DDI preparation

Before a freshly paired watch can accept application installs, Xcode must mount the Developer Disk Image (DDI) and transfer debug symbols:
- Xcode reports this operation as `"Preparing <watch>"`.
- The command line reports `"copy OS library symbols from <watch>"`.

### Preparation requirements
Keep all of the following conditions met throughout DDI preparation:
- The watch rests on its charger.
- The watch is unlocked and kept awake.
- The watch is physically near the paired iPhone.
- The paired iPhone is connected to the Mac.
- Bluetooth and Wi-Fi remain active on both the iPhone and the watch.

### Device state verification
Track preparation progress with `devicectl`:
```bash
xcrun devicectl list devices
```
- A newly paired watch awaiting symbol copy appears with state `connected (no DDI)`.
- Once DDI preparation finishes, the state advances to `connected`.

### Destination timeout in xcodebuild
By default, `xcodebuild` uses a short destination availability timeout. If DDI preparation is still underway, `xcodebuild` aborts with:
`Timed out waiting for all destinations matching the provided destination specifier to become available … error: Preparing <watch> Xcode will continue when the operation completes`

To prevent premature build failures while the Mac copies OS symbols, pass `-destination-timeout <seconds>` (allocating sufficient time for preparation to finish).

## Scheme and destination

When an Xcode scheme targets a watchOS app, Xcode restricts available destinations to watchOS targets:
- Select the specific **watchOS scheme** (`<watch-scheme>`).
- Specify the destination using the watch's platform and UDID:
  `-destination 'platform=watchOS,id=<watch-udid>'`

## Background location

A recording app gets background runtime from the active `HKWorkoutSession`; while the session
runs, CoreLocation keeps delivering updates, so the app does not need — and must not set —
`allowsBackgroundLocationUpdates` on watchOS (see Traps). It may still declare
`WKBackgroundModes = [workout-processing]` in its Info.plist, but that declaration does not by
itself permit the flag.

## Signing

### Explicit App ID and profile for HealthKit
Wildcard development provisioning profiles cannot carry the HealthKit capability (nor push notifications or App Groups). Any watchOS app utilizing HealthKit requires:
- An **explicit App ID**.
- A provisioning profile specifically configured with the HealthKit entitlement.
- Building with `CODE_SIGN_STYLE=Automatic` and `-allowProvisioningUpdates` while an active Xcode account session is present to create or refresh the profile on Apple developer servers.

### Device registration in profile
An existing provisioning profile generated prior to pairing the watch lacks the watch's UDID. Attempting to install with an outdated profile fails with:
`Failed to install embedded profile for <bundle-id> : 0xe8008012 (This provisioning profile cannot be installed on this device.)`

Building specifically for the watch destination (`platform=watchOS,id=<watch-udid>`) with automatic signing (`CODE_SIGN_STYLE=Automatic -allowProvisioningUpdates`) prompts Xcode to update the provisioning profile on the developer portal, adding the watch UDID to the embedded profile device list.

## Install from the CLI

Read the development team dynamically from a cached profile using the repository helper script to keep team IDs out of command strings and logs (see [signing model](./ios_development.md#signing)).

### Build and installation workflow
```bash
# 1. Resolve team ID without hardcoding
team="$("<skill-repo>/scripts/team_from_profile.sh")"

# 2. Build watchOS scheme for physical watch destination
xcodebuild -project <App.xcodeproj> -scheme <watch-scheme> -configuration Debug \
  -destination 'platform=watchOS,id=<watch-udid>' -destination-timeout <seconds> \
  CODE_SIGN_STYLE=Automatic DEVELOPMENT_TEAM="$team" -allowProvisioningUpdates build

# 3. Install built .app bundle onto the watch
xcrun devicectl device install app --device <watch-udid> <path>/<Watch>.app
```

On successful installation, `devicectl` outputs:
`App installed: <bundle-id>`

### First run and HealthKit authorization
Upon initial launch on the Apple Watch, any app requiring HealthKit displays a system authorization sheet on the watch display:
- CLI tooling cannot automate or bypass watchOS permission dialogs.
- An operator must manually view and confirm the requested HealthKit read/write permissions on the Apple Watch screen.

## Traps

| Symptom | Cause | Remedy |
|---|---|---|
| *Settings > Privacy & Security* on the watch shows no Developer Mode toggle | Watch has not established initial pairing with Mac or watchOS has not surfaced the setting | Ensure watch is paired via Device Hub at least once. Restart the Apple Watch; the Developer Mode toggle will appear. Enable it and reboot when prompted. |
| Watch does not appear in `devicectl` or Device Hub when plugged into Mac via charging cable | Apple Watch magnetic charging cable connects to Mac for power only; watch has no direct USB data interface | Connect and trust the paired iPhone to the Mac over USB or Wi-Fi. The Mac communicates with the watch solely via the paired iPhone. |
| `xcodebuild` fails with `Timed out waiting for all destinations ... error: Preparing <watch>` | DDI symbol copy ("copy OS library symbols from <watch>") is ongoing and exceeds default timeout | Keep watch on charger, unlocked/awake, near paired iPhone connected to Mac with Bluetooth/Wi-Fi active. Pass `-destination-timeout <seconds>` to `xcodebuild`. |
| `devicectl list devices` shows watch state as `connected (no DDI)` | Symbol preparation and Developer Disk Image mount have not completed | Maintain watch on charger near iPhone; wait for DDI symbol transfer to finish until state becomes `connected`. |
| App installation fails with `Failed to install embedded profile for <bundle-id> : 0xe8008012 (This provisioning profile cannot be installed on this device.)` | Embedded provisioning profile predates watch registration and omits `<watch-udid>` | Build for the target watch (`platform=watchOS,id=<watch-udid>`) with `CODE_SIGN_STYLE=Automatic` and `-allowProvisioningUpdates` under an active Xcode account session to regenerate the profile with the watch included. |
| Signing failure or missing capability when configuring HealthKit | Wildcard development profiles cannot carry HealthKit entitlements | Use an explicit App ID and provisioning profile with HealthKit enabled. Generate via automatic signing with `-allowProvisioningUpdates`. |
| App blocks or returns empty health queries on first launch | HealthKit permission prompt requires interactive consent | Operator must manually grant HealthKit authorization directly on the Apple Watch screen. CLI automation cannot dismiss system permission sheets. |
| Watch app terminates at runtime the moment recording starts: `*** Assertion failure in -[CLLocationManager setAllowsBackgroundLocationUpdates:], reason: 'Invalid parameter not satisfying: !stayUp \|\| CLClientIsBackgroundable(internal->fClient) \|\| _CFMZEnabled()'` | The code sets `CLLocationManager.allowsBackgroundLocationUpdates = true` on watchOS, which has no iOS-style location background mode that satisfies CoreLocation's backgroundability check. Declaring `WKBackgroundModes = [workout-processing]` is not sufficient. | Do not set `allowsBackgroundLocationUpdates` on watchOS. Background runtime already comes from the active `HKWorkoutSession`, so updates keep flowing while recording. You may still declare `WKBackgroundModes = [workout-processing]`, but the flag must not be set. |
