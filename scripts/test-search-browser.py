"""Verify HEPkit search, local links, keyboard controls, themes and lazy assets."""
import functools
import importlib.util
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import re
import threading
from urllib.parse import unquote, urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("serve", ROOT / "scripts/serve.py")
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)


class Quiet(serve.Handler):
    def log_message(self, *_):
        pass


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT / "dist")))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    screenshots = Path("/tmp/hepkit-search-screenshots")
    screenshots.mkdir(exist_ok=True)
    report = {"errors": [], "queries": []}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/usr/bin/brave")
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            requests, bad = [], []
            page.on("request", lambda request: requests.append(request.url))
            page.on("pageerror", lambda error: report["errors"].append(str(error)))
            page.on("response", lambda response: bad.append(response.url) if response.status >= 400 and response.url.startswith(origin) else None)
            page.goto(origin + "/", wait_until="networkidle")
            assert not any("/pagefind/" in url or ".wasm" in url or "pyodide" in url for url in requests)
            page.get_by_role("button", name="Search", exact=True).click()
            dialog = page.get_by_role("dialog", name="Search HEPkit")
            field = dialog.get_by_role("searchbox")
            expect(field).to_be_focused()

            def query(text):
                field.fill(text)
                expect(dialog.locator(".site-search-results")).to_have_attribute("data-query", text, timeout=20000)

            for text, expected in [
                ("IBPFamily.solve_parametric", "#symbolica.community.hepkit.IBPFamily.solve_parametric"),
                ("Model.qcd", "#symbolica.community.hepkit.Model.qcd"),
                ("TensorNetwork.render", "#symbolica.community.tensor.TensorNetwork.render"),
                ("RenderSettings", "/docs/graph/RenderSettings.html"),
                ("seed neighborhoods", "/docs/hepkit/IBPFamily.html"),
                ("sector decomposition", "/docs/hepkit/sector_decomposition/"),
                ("boundary cache", "/docs/hep/integration/"),
            ]:
                query(text)
                links = dialog.locator(".site-search-result-link").evaluate_all("nodes => nodes.map(node => node.getAttribute('href'))")
                for link in links:
                    url = urlsplit(link)
                    path = ROOT / "dist" / unquote(url.path).lstrip("/")
                    assert path.is_file(), link
                    if url.fragment:
                        assert f'id="{unquote(url.fragment)}"' in path.read_text(), link
                assert any(expected in link for link in links), (text, links)
                report["queries"].append(text)
            query("IBPFamily.so")
            completions = dialog.get_by_role("list", name="API suggestions")
            expect(completions.get_by_role("button", name="Search for IBPFamily.solve_parametric", exact=True)).to_be_visible()
            assert completions.locator("code").first.evaluate("node => getComputedStyle(node).backgroundColor === 'rgba(0, 0, 0, 0)'")
            field.press("Tab")
            expect(field).to_have_value("IBPFamily.solve_parametric")
            expect(completions).to_be_hidden()
            query("IBPFamliy.solve_parametric")
            correction = dialog.get_by_role("group", name="Spelling suggestions").get_by_role("button", name="Search for IBPFamily.solve_parametric", exact=True)
            expect(correction).to_be_visible()
            correction.click()
            expect(field).to_have_value("IBPFamily.solve_parametric")
            query("IBPFamily")
            expect(dialog.locator(".site-search-page-link").filter(has_text=re.compile("^IBPFamily$"))).to_have_count(1)
            load = dialog.get_by_role("button", name=re.compile("^Load more Python API matches"))
            if load.count() and load.is_visible():
                load.click()
            group = dialog.locator(".site-search-group").filter(has=page.locator('.site-search-page-link[href="/docs/hepkit/IBPFamily.html"]'))
            expand = group.get_by_role("button", name=re.compile("Show .* more matches in IBPFamily"))
            expect(expand).to_be_visible()
            expand.click()
            collapse = group.get_by_role("button", name="Show fewer matches", exact=True)
            expect(collapse).to_have_attribute("aria-expanded", "true")
            expect(collapse.locator(".bi-dash-lg")).to_have_count(1)
            collapse.click()
            page.screenshot(path=str(screenshots / "desktop.png"))
            query("IBPFamily.solve_parametric")
            dialog.get_by_role("list", name="Python API results").locator(".site-search-result-link").first.click()
            expect(page).to_have_url(re.compile(r"/docs/hepkit/IBPFamily.html#symbolica.community.hepkit.IBPFamily.solve_parametric$"))
            page.get_by_role("button", name="Search reference", exact=True).click()
            expect(dialog).to_be_visible()
            query("IBPFamily.solve_parametric")
            page.screenshot(path=str(screenshots / "docs-light.png"))
            field.press("Escape")
            page.get_by_role("button", name="Dark mode", exact=True).click()
            page.keyboard.press("Control+k")
            query("IBPFamily.so")
            page.screenshot(path=str(screenshots / "docs-dark.png"))
            field.press("Escape")
            for width, height in [(390, 844), (320, 568), (568, 320)]:
                page.set_viewport_size({"width": width, "height": height})
                page.keyboard.press("Control+k")
                query("IBPFamily.")
                expect(completions.get_by_role("button")).to_have_count(5)
                assert dialog.evaluate("node => node.scrollWidth <= node.clientWidth"), "Dialog overflow"
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Page overflow"
                assert dialog.locator(".site-search-panel").evaluate("node => node.scrollHeight <= node.clientHeight + 1"), "Clipped suggestions"
                page.screenshot(path=str(screenshots / f"mobile-{width}.png"))
                field.press("Escape")
            assert not any("/docs/search-index.json" in url for url in requests)
            assert not any("pyodide" in url or "/gallery/notebooks/" in url for url in requests)
            assert not bad, bad
            assert not report["errors"], report["errors"]
            browser.close()
        print(json.dumps(report, indent=2))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
