# App Store Release

## Metadata

- **Type**: Deployment
- **When to use**: Creating an archive, exporting an App Store distribution IPA with cloud-managed or manual signing, verifying IPA metadata, and uploading to App Store Connect via official Apple command-line tools.
- **Related skills**: [iOS Development](./ios_development.md), [Simulator Testing](./simulator_testing.md), [Real Device](./real_device.md)
- **Last reviewed**: 2026-09-30. Translated and reorganized from the earlier release skill, whose commands and traps were verified on real App Store Connect releases (most recently 2026-09-29).

## Goals and Boundaries

### Goals
- Use only Apple's official command-line tools shipped with Xcode to convert a release-ready Xcode scheme into an App Store Connect accepted build.
- Maintain an unbroken chain of evidence from source repository revision and build settings to code signing identity, artifact metadata, and remote processing status.

### Boundaries
- Does not create custom CLI wrappers or scripts that hide raw tool output.
- Does not manage App Store metadata, marketing assets, screenshots, descriptions, pricing, or store reviews.
- Does not treat "Upload succeeded" as "Released to the App Store" or submitted for App Review.

## Authorization Boundary

- **Autonomous execution**: Local pre-flight checks, build, unit/UI tests, archive creation, and local IPA export (`destination=export`) may proceed autonomously.
- **Explicit authorization required**: Uploading to App Store Connect (`destination=upload` or `altool --upload-*`) mutates remote store state and transmits binaries to Apple; **never upload without explicit user authorization**.
- **Post-upload restraint**: After upload, do not automatically submit the build for App Review, distribute to external TestFlight groups, or alter store metadata without explicit user authorization.
- **Credential hygiene**: Never write Apple ID passwords, app-specific passwords, API private keys, Issuer IDs, Team IDs, or provisioning profile UUIDs into command lines, shell history, logs, or repositories. Read sensitive values from a secret manager, project configuration, or cached profiles. See [signing model](./ios_development.md#signing).

## Acceptance Criteria

A release run is complete only when all of the following criteria are satisfied:

- **Pinned stable Xcode**: `DEVELOPER_DIR` points to the designated stable Xcode release, and `xcodebuild -version` matches the recorded toolchain version (see [toolchain selection](./ios_development.md#toolchain)).
- **Shared scheme and destination**: The target scheme is shared and builds cleanly in Release configuration for `generic/platform=iOS`.
- **Pre-release test verification**: Build and test suites pass according to repository rules; any known non-blocking failures are explicitly documented and acknowledged before archiving.
- **Valid `.xcarchive`**: The archive generates successfully with expected bundle identifier, marketing version, build number, development team, and minimum OS deployment target.
- **App Store export verification**: Export with `method=app-store-connect` succeeds, and `DistributionSummary.plist` confirms signing by `Apple Distribution` or `Cloud Managed Apple Distribution`, a valid App Store profile, and `get-task-allow = false`.
- **Final IPA metadata verification**: Direct inspection of `Info.plist` extracted from the final `.ipa` confirms `CFBundleShortVersionString`, `CFBundleVersion`, and `MinimumOSVersion`.
- **Upload confirmation**: Upload command returns `Upload succeeded` or an equivalent remote acceptance confirmation, and App Store Connect acknowledges that package processing has started.
- **Processing completion (when required)**: If the task requires reaching an actionable TestFlight or release state, build processing status is monitored until processing succeeds; seeing `Uploaded package is processing` does not constitute completion.

## Tools and Artifacts

### Apple Official Tools
- `xcode-select`: Inspect or set the active developer directory.
- `xcodebuild`: List schemes, build, test, archive, export, and upload.
- `xcrun altool`: Validate, upload, and query status with App Store Connect API keys or app-specific passwords. Prefer `xcodebuild -exportArchive` when an authenticated Xcode account session is present to keep signing and upload within one toolchain flow.
- `codesign`, `plutil`, `unzip`: Inspect signatures and package metadata.

### Artifact Locations
- **Archive**: `<output>/<App>.xcarchive` in a local scratch directory outside version control.
- **Export directory**: `<output>/export/` containing `<App>.ipa` and `DistributionSummary.plist`.
- **Upload directory**: `<output>/upload/` containing upload receipts and logs.
- **Distribution logs**: `<output>/*.xcdistributionlogs` containing `IDEDistribution.standard.log`.

## Release Workflow

### 1. Toolchain and Signing Inspection

Pin the stable toolchain and verify active build settings:

```bash
export DEVELOPER_DIR="/Applications/Xcode.app/Contents/Developer"
xcode-select -p
xcodebuild -version
```

Inspect schemes, build configurations, and code signing identities:

```bash
xcodebuild -project <project.xcodeproj> -list
xcodebuild \
  -project <project.xcodeproj> \
  -scheme <scheme> \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -showBuildSettings
security find-identity -v -p codesigning
```

Verify `PRODUCT_BUNDLE_IDENTIFIER`, `MARKETING_VERSION`, `CURRENT_PROJECT_VERSION`, `IPHONEOS_DEPLOYMENT_TARGET`, `DEVELOPMENT_TEAM`, and `CODE_SIGN_STYLE`.
Automatic signing can leverage cloud-managed distribution certificates during export; the absence of a local `Apple Distribution` certificate in the macOS keychain does not block distribution. See [signing model](./ios_development.md#signing).

### 2. Create the Archive

Run archive after repository build and test validations pass:

```bash
xcodebuild archive \
  -project <project.xcodeproj> \
  -scheme <scheme> \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath <output/App.xcarchive> \
  -allowProvisioningUpdates \
  CODE_SIGN_STYLE=Automatic \
  DEVELOPMENT_TEAM="$team"
```

Read `team` from the project, a controlled configuration, or a cached profile ([`scripts/team_from_profile.sh`](../scripts/team_from_profile.sh)) so the value never appears in the command.

Always use a distinct archive path on retries or clean up only after verifying the previous archive is not required for audit. Do not overwrite existing archives.

### 3. App Store Export

Export an IPA locally to verify packaging and distribution signing before initiating any upload. Prepare a temporary `ExportOptions.plist` in scratch storage (never committed to version control):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>destination</key>
  <string>export</string>
  <key>method</key>
  <string>app-store-connect</string>
  <key>signingStyle</key>
  <string>automatic</string>
  <key>teamID</key>
  <string><team-id></string>
  <key>uploadSymbols</key>
  <true/>
</dict>
</plist>
```

Execute export:

```bash
xcodebuild -exportArchive \
  -archivePath <output/App.xcarchive> \
  -exportPath <output/export> \
  -exportOptionsPlist <output/ExportOptions.plist> \
  -allowProvisioningUpdates
```

By default, Xcode managed versioning may adjust the build number during export to match App Store Connect expectations. Always verify the resulting `DistributionSummary.plist` and IPA. When strict version parity with repository source is required, explicitly add `<key>manageAppVersionAndBuildNumber</key><false/>` to the export options plist and update the build number in project source beforehand.

### 4. Verify Final IPA Metadata

Inspect the generated IPA directly to confirm version numbers and deployment target:

```bash
unzip -p <output/export/App.ipa> Payload/<AppName>.app/Info.plist \
  | plutil -extract CFBundleShortVersionString raw -
unzip -p <output/export/App.ipa> Payload/<AppName>.app/Info.plist \
  | plutil -extract CFBundleVersion raw -
unzip -p <output/export/App.ipa> Payload/<AppName>.app/Info.plist \
  | plutil -extract MinimumOSVersion raw -
```

Inspect `<output/export>/DistributionSummary.plist` to confirm:
- The signing certificate is `Apple Distribution` or `Cloud Managed Apple Distribution`.
- Entitlements contain `<key>get-task-allow</key><false/>`.
- The attached provisioning profile is a valid App Store profile.

If metadata or entitlements do not match expectations, fix the project configuration and re-execute build, test, archive, and export. Never upload an invalid artifact.

### 5. Upload to App Store Connect

Upload only after receiving explicit user authorization.

#### Option A: Direct Upload via `xcodebuild -exportArchive` (Recommended)

Create `UploadOptions.plist` identical to `ExportOptions.plist`, changing `destination` to `upload`:

```xml
<key>destination</key>
<string>upload</string>
```

Execute upload:

```bash
xcodebuild -exportArchive \
  -archivePath <output/App.xcarchive> \
  -exportPath <output/upload> \
  -exportOptionsPlist <output/UploadOptions.plist> \
  -allowProvisioningUpdates
```

#### Option B: Upload via `xcrun altool` (API Key)

When using an App Store Connect API Key (`.p8` private key stored in `~/.appstoreconnect/private_keys/AuthKey_<key-id>.p8` or provided by a controlled configuration):

```bash
xcrun altool --validate-app \
  -f <output/export/App.ipa> \
  --api-key <key-id> \
  --api-issuer <issuer-id>

xcrun altool --upload-app \
  -f <output/export/App.ipa> \
  --api-key <key-id> \
  --api-issuer <issuer-id>
```

Never output raw private key contents into logs or terminal commands.

#### Option C: Read-only Queries via `altool` (App-Specific Password)

When authenticating with an app-specific password:
- Retrieve the password dynamically from a secret manager; do not hardcode passwords.
- If the Apple ID belongs to multiple provider teams, pass `--provider-public-id <provider-public-id>` (running without this flag lists available provider Names and Public IDs on first run).
- **Note**: An app-specific password cannot query the processing status of individual builds; that status requires an App Store Connect API key or the App Store Connect web interface.

## Known Traps (Observed Failures)

### 1. Defaulting to Latest OS in Project Settings
New projects or target definitions often default `IPHONEOS_DEPLOYMENT_TARGET` to the newest SDK version, even when application code and dependencies support earlier versions. Archiving succeeds, but user compatibility is unintentionally restricted. Always cross-check the project build setting against `MinimumOSVersion` in the exported IPA.

### 2. Archive Success Does Not Guarantee Upload Readiness
`xcodebuild archive` frequently signs binaries with an `Apple Development` identity. The App Store export step performs the actual distribution re-signing using `Apple Distribution` or `Cloud Managed Apple Distribution` and attaches the App Store provisioning profile. Always run and verify local export before treating an archive as ready for release.

### 3. Missing Local Distribution Certificate Does Not Prevent Export
With Automatic Signing, Xcode leverages its logged-in Apple account session and cloud-managed certificates to sign distribution builds. Do not abort just because `security find-identity -v -p codesigning` lacks a local `Apple Distribution` certificate. Run `destination=export` to test actual signing feasibility.

### 4. Source Build Number May Differ from Exported IPA Build Number
Xcode's managed versioning (`manageAppVersionAndBuildNumber`) queries App Store Connect during export and may automatically increment the build number to the next acceptable value. Always inspect `CFBundleVersion` from the final IPA and `DistributionSummary.plist`. Do not assume `CURRENT_PROJECT_VERSION` represents the uploaded build number.

### 5. New Build Appears "Missing" Due to ASC Build Sorting and Per-Platform Versioning
In App Store Connect and TestFlight, the build list is sorted by **build number in descending order**, not by upload time. If an application previously uploaded builds with higher build numbers (for example, iOS build 9), a newly uploaded build with a lower number will appear below older builds, looking as if the upload failed or disappeared.
Additionally, automatic versioning via `manageAppVersionAndBuildNumber` (default `true`) calculates version sequences **independently per platform**. A newly supported platform (such as visionOS) starts its own sequence from low numbers, ignoring source `CURRENT_PROJECT_VERSION` (observed: iOS sequence reached 9, while visionOS uploads were assigned 4 and 5). Because build number uniqueness is scoped per platform, visionOS 5 does not collide with iOS 5 and Apple accepts it.
When a newly uploaded build must appear at the top of the build list:
1. Update `CURRENT_PROJECT_VERSION` in the project to a value greater than the global maximum build number across all platforms of the app (for example, if iOS maximum is 9, set it to 10).
2. In **both** the export and upload plist files, explicitly set `manageAppVersionAndBuildNumber` to `<false/>`. Modifying only the export options plist is ineffective because the upload step performs export again with its own options.
3. Verify that `DistributionSummary.plist` and `CFBundleVersion` in the IPA reflect the expected number prior to uploading.

### 6. Cloud Signing Session Silently Expires
Errors such as `No Accounts` or `No signing certificate "iOS Distribution" found` do not necessarily indicate that an account was never added. Even with Xcode open and after earlier successful exports, cloud signing sessions can silently expire within tens of minutes.
**Fix**: Open Xcode → Settings → Accounts, re-authenticate the Apple ID (complete two-factor authentication), and retry the command. Do not alter `signingStyle` or `teamID`.

### 7. "Upload Succeeded" Does Not Mean Processing Succeeded
The message `Upload succeeded` confirms only that Apple's ingestion endpoint accepted the package file. Validation or processing errors may still emerge during asynchronous processing in App Store Connect. If the task boundary is uploading, report that the package has been uploaded and entered processing. If the goal requires an actionable build for TestFlight or release, poll build processing status until it is marked valid.

### 8. Team Store Profile Does Not Include Cloud-Managed Distribution Certificate
When using `method=app-store-connect` and `signingStyle=automatic`, Apple automatically rotates cloud-managed distribution certificates roughly 90 days before expiration. If the cached "iOS Team Store Provisioning Profile" references the expired or pre-rotation certificate, export fails during qualification with:
`Provisioning profile "iOS Team Store Provisioning Profile: <bundle-id>" doesn't include signing certificate "Apple Distribution: <team>"`
or `failed qualification checks`.
Xcode does not refresh this profile automatically unless `-allowProvisioningUpdates` is included on the command line.
**Fix**:
1. Ensure `-allowProvisioningUpdates` is passed to both `archive` and `-exportArchive`.
2. Do not attempt to delete the profile in the Apple Developer portal; Xcode-managed store profiles typically do not appear in the web list.
3. If errors persist, delete cached provisioning profiles from both local cache directories:
   - `~/Library/Developer/Xcode/UserData/Provisioning Profiles/` (Xcode 16+)
   - `~/Library/MobileDevice/Provisioning Profiles/` (legacy)
   Use `security cms -D -i <profile-file>` to match the profile `Name` and target bundle ID before deleting.

## Diagnostics and Troubleshooting

When an export or upload command fails, do not rely solely on the last line of terminal output. `xcodebuild -exportArchive` generates a `.xcdistributionlogs` directory (printed in stdout). Inspect `IDEDistribution.standard.log` inside that bundle to identify the exact step failure:

- **Hangs or fails at `IDEDistributionUploadAccountStep` with `Failed to find an account with App Store Connect access for team ...`**: Xcode lacks a signed-in Apple ID holding App Store Connect permissions for the designated team. Cloud signing requires this session. Re-authenticate in Xcode → Settings → Accounts. Inspect session state via:
  ```bash
  plutil -p ~/Library/Preferences/com.apple.dt.Xcode.plist | grep -A6 DVTDeveloperAccountManagerAppleIDLists
  ```
  This preference file is shared between stable and beta Xcode installations.
- **Fails profile qualification (`failed qualification checks` / `doesn't include signing certificate`)**: The cached profile does not contain the current distribution certificate. Add `-allowProvisioningUpdates` or clear cached profiles as described in the traps section.
- **Fails with `No signing certificate "iOS Distribution" found`**: Almost always indicates an expired or missing account session rather than a missing local certificate in the keychain. Address Xcode account authentication first.

## Output Specifications

Every release report or artifact summary must record:

- **Toolchain**: Xcode application path, version number, and build identifier (`xcodebuild -version`).
- **Source revision**: Git commit hash and workspace cleanliness state.
- **Build parameters**: Project/workspace, scheme name, configuration (`Release`), and destination platform (`generic/platform=iOS`).
- **Package identity**: Bundle identifier, marketing version (`CFBundleShortVersionString`), final build number (`CFBundleVersion`), and minimum OS deployment version (`MinimumOSVersion`).
- **Artifact paths**: Absolute paths to the generated `.xcarchive` and `.ipa`.
- **Signing audit**: Certificate type (`Apple Distribution` or `Cloud Managed Apple Distribution`) and profile type, without logging UUIDs or private credentials.
- **Workflow statuses**: Build, test, archive, export, and upload status for each phase.
- **App Store Connect status**: One of `Not uploaded`, `Uploaded and processing`, `Processing succeeded`, or `Processing failed`.
- **Pending manual actions**: Explicitly note unperformed actions (such as TestFlight external release, App Review submission, or version release).
