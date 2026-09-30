#!/usr/bin/env bash
# Prints the team ID from a cached provisioning profile, so it can be passed to
# xcodebuild without appearing in commands, logs, or the repository:
#   DEVELOPMENT_TEAM="$(scripts/team_from_profile.sh)" xcodebuild ... DEVELOPMENT_TEAM="$DEVELOPMENT_TEAM"
# The profile is chosen by name; the default is the team's wildcard development profile.
set -euo pipefail
name="${1:-iOS Team Provisioning Profile: *}"
for dir in "$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles" "$HOME/Library/MobileDevice/Provisioning Profiles"; do
  for f in "$dir"/*; do
    [[ -f "$f" ]] || continue
    plist="$(security cms -D -i "$f" 2>/dev/null)" || continue
    [[ "$(/usr/libexec/PlistBuddy -c 'Print :Name' /dev/stdin <<<"$plist" 2>/dev/null || true)" == "$name" ]] || continue
    expires="$(/usr/libexec/PlistBuddy -c 'Print :ExpirationDate' /dev/stdin <<<"$plist" 2>/dev/null || true)"
    if [[ -n "$expires" ]] && [[ "$(date -j -f '%a %b %d %T %Z %Y' "$expires" +%s 2>/dev/null || echo 9999999999)" -lt "$(date +%s)" ]]; then
      continue
    fi
    /usr/libexec/PlistBuddy -c 'Print :TeamIdentifier:0' /dev/stdin <<<"$plist"
    exit 0
  done
done
echo "no unexpired provisioning profile named '$name' found" >&2
exit 1
