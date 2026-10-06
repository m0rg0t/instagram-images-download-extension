# Offline maintenance checks

This owned fork uses Manifest V3. The popup text/layout and profile collection
purpose are preserved. The empty background registration was removed; it had no
logic or messaging. API permissions remain exactly `storage` and `downloads`;
the sole content-script match remains `https://www.instagram.com/*`. No optional
or additional host permissions were added. There are no popup/options messages
to migrate: the popup is informational and the existing options page is empty.

The content script uses native DOM APIs and string Set deduplication instead of
jQuery 1.9.1. Each Collect click takes a fresh snapshot, preventing stale URL
accumulation. It handles images without IDs and CSS-special IDs, skips empty and
non-HTTP(S) sources, avoids implicit globals, and cleans up temporary links.
Popup fading uses the browser animation API. Unused vendored jQuery/Bootstrap
JavaScript is removed; existing static Bootstrap CSS and visual content remain.

## Run

```sh
python -m pip install -r tests/requirements.txt
python -m playwright install --with-deps chromium
python tests/browser_test.py
```

Optional `CHROMIUM_PATH` selects an existing Chromium executable. Tests launch an
isolated temporary browser profile, load this unpacked extension, inspect its
actual manifest/runtime ID, and capture its popup and blank options page.
A localhost synthetic page exercises the checked-in content script, including
repeat collection, changing/empty DOM, special IDs, keyboard input, home
exclusion, and back navigation. Download anchors are intercepted before clicking;
no real photos are fetched or saved. Page requests outside localhost and the
extension are blocked. Screenshots, a trace, and JSON evidence are in
`test-results/` and uploaded by CI.

Localhost is deliberately **not** added to the manifest. The fixture injects the
same script locally, so DOM coverage is separate from the real unpacked-extension
load test. This does not certify live Instagram markup or automatic injection
on Instagram. No sign-in, Instagram page, user cookies/profile, real downloads,
store submission or installation in a user's browser is involved. Existing
cross-origin anchor-download restrictions remain browser-controlled.

## Platform references

- https://developer.chrome.com/docs/extensions/develop/migrate/manifest
- https://developer.chrome.com/docs/extensions/develop/migrate/mv2-deprecation-timeline

The historical README's store link describes the original upstream release,
not a newly published release of this fork.
