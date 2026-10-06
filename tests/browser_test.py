"""Offline fixtures only; never navigate to Instagram or download real images."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test-results"
OUT.mkdir(exist_ok=True)
manifest = json.loads((ROOT / "manifest.json").read_text())
assert manifest["manifest_version"] == 3
assert manifest["permissions"] == ["storage", "downloads"]
assert manifest["content_scripts"] == [{
    "js": ["js/instagram.js"], "matches": ["https://www.instagram.com/*"]
}]
for forbidden in ["background", "browser_action", "host_permissions",
                  "optional_permissions", "optional_host_permissions"]:
    assert forbidden not in manifest, forbidden
assert manifest["action"]["default_popup"] == "html/main.html"
for page in ["main", "options"]:
    html = (ROOT / f"html/{page}.html").read_text()
    assert "jquery" not in html.lower() and "bootstrap.min.js" not in html
assert (ROOT / "js/background.js").exists() is False or not (ROOT / "js/background.js").read_text()
# Deterministic unpacked-extension ID derived from its absolute local path.
digest = hashlib.sha256(str(ROOT).encode()).hexdigest()[:32]
extension_id = "".join(chr(ord("a") + int(n, 16)) for n in digest)

class QuietHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ["/one.png", "/two.png", "/three.png"]:
            color = {"/one.png": "#e2ba7b", "/two.png": "#7baee2", "/three.png": "#7be2ad"}[self.path]
            body = f'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" fill="{color}"/></svg>'.encode()
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_port}"
checks = []
blocked = []
errors = []
try:
    with tempfile.TemporaryDirectory(prefix="offline-extension-") as profile, sync_playwright() as pw:
        options = {
            "headless": True,
            "channel": "chromium",
            "args": [f"--disable-extensions-except={ROOT}", f"--load-extension={ROOT}",
                     "--disable-background-networking", "--disable-component-update",
                     "--disable-sync", "--no-first-run"],
        }
        if os.getenv("CHROMIUM_PATH"):
            options["executable_path"] = os.environ["CHROMIUM_PATH"]
        context = pw.chromium.launch_persistent_context(profile, **options)
        context.tracing.start(screenshots=True, snapshots=True)
        def route(request):
            url = urlsplit(request.request.url)
            if url.hostname == "127.0.0.1" or url.scheme in ("chrome-extension", "chrome", "data"):
                request.continue_()
            else:
                blocked.append(request.request.url)
                request.abort()
        context.route("**/*", route)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"chrome-extension://{extension_id}/html/main.html")
        assert page.locator("#main-title").inner_text() == "Instagram Images Download Extension"
        assert page.evaluate("chrome.runtime.id") == extension_id
        assert page.evaluate("chrome.runtime.getManifest().manifest_version") == 3
        assert page.evaluate("chrome.runtime.getManifest().content_scripts[0].matches") == [
            "https://www.instagram.com/*"]
        page.screenshot(path=str(OUT / "popup.png"))
        checks.append("actual unpacked MV3 load and unchanged popup")
        page.goto(f"chrome-extension://{extension_id}/html/options.html")
        assert page.evaluate("chrome.runtime.id") == extension_id
        checks.append("existing empty options page loads without legacy JS")

        page.goto(base + "/tests/fixture.html")
        # The manifest intentionally does not match localhost. Inject the same
        # checked-in content script into this isolated synthetic page for DOM tests.
        page.add_script_tag(path=str(ROOT / "js/instagram.js"))
        page.add_script_tag(path=str(ROOT / "js/instagram.js"))
        assert page.locator(".instagram-extension-box").count() == 1
        checks.append("repeat initialization does not duplicate UI")
        page.evaluate("""() => {
            window.downloadRequests = [];
            HTMLAnchorElement.prototype.click = function () {
                window.downloadRequests.push({href: this.href, name: this.download});
            };
        }""")
        collect = page.locator("#instagram-extension-box-button-collect")
        download = page.locator("#instagram-extension-box-button-download")
        download.click()
        assert page.evaluate("downloadRequests") == []
        collect.click()
        assert download.inner_text() == "Download 2 photos"
        assert page.locator(".instagram-extension-marker").count() == 3
        assert page.locator('[id="photo:one"]').evaluate("(img) => img.style.opacity") == "0.2"
        collect.click()
        assert download.inner_text() == "Download 2 photos"
        assert page.locator(".instagram-extension-marker").count() == 3
        download.click()
        assert page.evaluate("downloadRequests") == [
            {"href": base + "/one.png", "name": "Fixture Profile.jpg"},
            {"href": base + "/two.png", "name": "Fixture Profile.jpg"}]
        assert page.locator("a[download]").count() == 0
        checks.append("deduplication, repeated collect, special/no IDs, safe schemes and link cleanup")
        page.screenshot(path=str(OUT / "collected.png"))
        page.evaluate("""() => {
            document.querySelectorAll("img").forEach(img => img.remove());
            const img = document.createElement("img"); img.src = "/three.png";
            document.body.append(img); window.downloadRequests = [];
        }""")
        collect.press("Enter")
        assert download.inner_text() == "Download 1 photos"
        download.press("Space")
        assert page.evaluate("downloadRequests") == [
            {"href": base + "/three.png", "name": "Fixture Profile.jpg"}]
        checks.append("changed DOM replaces stale collection and keyboard activation")
        page.evaluate("""() => {
            document.querySelectorAll("img").forEach(img => img.remove());
            window.downloadRequests = [];
        }""")
        collect.click()
        assert download.inner_text() == "Download 0 photos"
        assert "faded" in download.get_attribute("class")
        download.click()
        assert page.evaluate("downloadRequests") == []
        checks.append("empty collection clears download state")
        # Back/forward creates fresh DOM state; do not retain a previous page's URLs.
        page.goto(base + "/")
        page.add_script_tag(path=str(ROOT / "js/instagram.js"))
        assert page.locator(".instagram-extension-box").count() == 0
        page.go_back()
        page.add_script_tag(path=str(ROOT / "js/instagram.js"))
        assert page.locator(".instagram-extension-box").count() == 1
        checks.append("home exclusion and back navigation reinitialization")
        assert not errors, errors
        assert not blocked, blocked
        result = {"browser": context.browser.version, "extension_id": extension_id,
                  "checks": checks, "page_errors": errors, "external_requests": blocked,
                  "limits": "Synthetic DOM only; no Instagram access or real downloads. Local injection tests DOM logic, not live-site automatic injection."}
        (OUT / "result.json").write_text(json.dumps(result, indent=2))
        context.tracing.stop(path=str(OUT / "trace.zip"))
        context.close()
        print(json.dumps(result, indent=2))
finally:
    server.shutdown()
    server.server_close()
