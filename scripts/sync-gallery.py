#!/usr/bin/env python3
"""Import HEPkit notebooks, with shared assets served by Symbolica's CDN."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import html
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CDN = "https://cdn.symbolica.io"
TEXT_SUFFIXES = {".html", ".css", ".js", ".mjs", ".json"}
SIDECARS = {".gz", ".br", ".zst"}


def local_run_links(markup):
    """Give the standalone site's local instructions a visible secondary action."""
    def relabel(match):
        opening = re.sub(r'''\s+(?:aria-label|title)=(["']).*?\1''', "", match[1])
        opening = opening[:-1] + ' title="Download notebook to run locally">'
        return opening + "Run locally</a>"
    return re.sub(
        r'''(<a\b[^>]*\bclass=(["'])[^"']*\bgallery-download\b[^"']*\2[^>]*>).*?</a>''',
        relabel, markup, flags=re.S,
    )


def gallery_config(source, manifest):
    """The full notebook wheel is pinned separately from lightweight snippets."""
    path = source / "scripts/gallery/live-python-config.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["liveConfigSha256"]:
        raise ValueError("Gallery runtime configuration changed; rebuild the Symbolica gallery before syncing")
    config = json.loads(path.read_text())
    if Path(config["wheel"]).name != Path(manifest["symbolicaNative"]["wheel"]).name:
        raise ValueError("Gallery wheel does not match its native WASM manifest")
    return config


def prune_text_sidecars(directory):
    """Text is compressed by the server, so retired copies cannot mask updates."""
    for path in directory.rglob("*"):
        if path.is_file() and path.suffix in SIDECARS and path.with_suffix("").suffix in TEXT_SUFFIXES:
            path.unlink()


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def check_asset(url):
    """Refuse a sync whose pinned assets have not been published yet."""
    request = Request(url, method="HEAD", headers={
        "Origin": "https://hepkit.org", "User-Agent": "HEPkit-sync/1.0",
    })
    try:
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                return f"{url}: HTTP {response.status}"
            if response.headers.get("Access-Control-Allow-Origin") not in {"*", "https://hepkit.org"}:
                return f"{url}: missing cross-origin access for hepkit.org"
            mime = response.headers.get_content_type()
            suffix = Path(urlsplit(url).path).suffix
            if suffix == ".wasm" and mime != "application/wasm":
                return f"{url}: expected application/wasm, got {mime}"
            if suffix in {".js", ".mjs"} and mime not in {"text/javascript", "application/javascript"}:
                return f"{url}: expected JavaScript, got {mime}"
            if mime == "text/html":
                return f"{url}: received an HTML page instead of an asset"
    except Exception as error:
        return f"{url}: {error}"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Path to the Symbolica website checkout")
    parser.add_argument("--stage", type=Path,
                        help="Prepare a review copy without CDN checks or replacing dist")
    args = parser.parse_args()
    source = args.source.resolve()
    dist = ROOT / "dist"
    notebooks = source / "gallery/notebooks"
    manifest = json.loads((notebooks / "build.json").read_text())
    gallery = gallery_config(source, manifest)
    config_source = source / "docs/live-python/config.json"
    previous_path = dist / "gallery/notebooks/cdn-assets.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    catalog = (source / "gallery/index.qmd").read_text()
    section = catalog.split('<section class="gallery-category" data-category="hepkit"', 1)[1].split("</section>", 1)[0]
    section = re.sub(r'<article class="gallery-card">.*?</article>',
                     lambda match: "" if "<span>Run locally</span>" in match.group() else match.group(),
                     section, flags=re.S)
    slugs = re.findall(r'data-gallery-notebook="([\w-]+)"', section)
    if not slugs:
        raise ValueError("No HEPkit notebooks found in the gallery")

    # Reuse Symbolica's production URL rules, including its worker/CSS origin
    # exceptions. Only the imported gallery is staged here: HEPkit's own pages,
    # styles, branding and restyled documentation must never be CDN-rewritten.
    sys.path.insert(0, str(source / "scripts"))
    from rewrite_assets import AssetURLs, rewrite_site, write_changed

    grid = section[section.index('    <div class="gallery-grid">'):].strip()
    grid = grid.replace('href="notebooks/', 'href="gallery/notebooks/')
    grid = grid.replace(' <span aria-hidden="true">→</span>', '')
    grid = grid.replace('>Open notebook</a>', '>Run in browser</a>')
    grid = local_run_links(grid)
    index = dist / "index.html"
    page, count = re.subn(r'<!-- GALLERY:START -->.*?<!-- GALLERY:END -->',
                         lambda _: '<!-- GALLERY:START -->\n' + grid + '\n<!-- GALLERY:END -->',
                         index.read_text(), flags=re.S)
    if count != 1:
        raise ValueError("Expected exactly one gallery block in dist/index.html")
    page = re.sub(r'\d+ (?:LIVE )?NOTEBOOKS', f'{len(slugs):02d} LIVE NOTEBOOKS', page)

    with tempfile.TemporaryDirectory(prefix="hepkit-gallery-") as directory:
        stage = Path(directory)
        destination = stage / "gallery/notebooks"
        for slug in slugs:
            for extension in (".html", ".py"):
                copy(notebooks / (slug + extension), destination / (slug + extension))
        for name in ("pyodide-lock.json", "MARIMO-LICENSE", "build.json"):
            copy(notebooks / name, destination / name)
        # Keep executable chunks, worker entry points and editor CSS local.
        # Dynamic imports extend beyond the statically imported frontend.files.
        shutil.copytree(notebooks / "assets", destination / "assets")
        prune_text_sidecars(stage)
        for relative, expected in manifest["artifacts"].items():
            if relative.startswith("immutable/"):
                continue
            with (notebooks / relative).open("rb") as asset:
                if hashlib.file_digest(asset, "sha256").hexdigest() != expected:
                    raise ValueError(f"Source artifact checksum mismatch: {relative}")

        live_source = source / "docs/live-python"
        live_dest = stage / "docs/live-python"
        copy(live_source / "ty-worker.js", live_dest / "ty-worker.js")
        copy(live_source / "runtime/LICENSE", live_dest / "PYODIDE-LICENSE")
        copy(live_source / "ty/LICENSE", live_dest / "TY-LICENSE")
        # Supply the matching package configuration to the upstream rewriter.
        copy(config_source, live_dest / "config.json")
        rewrite_site(stage, CDN)
        # Escaped quotes in Tailwind selectors can confuse the upstream CSS
        # tokenizer. These generated, file-relative url() values are unambiguous.
        asset_urls = AssetURLs(CDN)
        for stylesheet in (destination / "assets").glob("*.css"):
            document = stylesheet.relative_to(stage).as_posix()
            content = re.sub(
                r'''url\(\s*(["']?)(\./[^()\s"']+)\1\s*\)''',
                lambda match: match.group().replace(match[2], asset_urls.rewrite(match[2], document), 1),
                stylesheet.read_text())
            write_changed(stylesheet, content)
        config = json.loads((live_dest / "config.json").read_text())
        (live_dest / "config.json").unlink()  # Gallery uses its pinned bootstrap.

        from cdn_editor import prepare_cdn_editor
        urls = prepare_cdn_editor(stage, manifest, CDN)
        for path in stage.rglob("*"):
            if path.suffix in {".html", ".css", ".js", ".mjs"}:
                urls.update(html.unescape(value) for value in re.findall(
                    r'https://cdn\.symbolica\.io/[^\s\"\'<>`)]+', path.read_text()))
        # A runtime directory and packageBaseUrl expand to these actual files.
        urls = {url for url in urls if not url.endswith("/")}
        urls.update(urljoin(config["runtime"], name) for name in (
            "pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"))
        lock = json.loads((destination / "pyodide-lock.json").read_text())
        urls.update(urljoin(CDN + "/gallery/notebooks/", package["file_name"])
                    for package in lock["packages"].values()
                    if not urlsplit(package["file_name"]).scheme)
        if args.stage:
            review = args.stage.resolve()
            if review == dist.resolve() or dist.resolve() in review.parents:
                raise ValueError("The review copy must be outside dist")
            shutil.copytree(dist, review, dirs_exist_ok=True)
            shutil.copytree(stage, review, dirs_exist_ok=True)
            (review / "index.html").write_text(page)
            (review / "gallery/notebooks/cdn-assets.json").write_text(json.dumps({
                "origin": CDN, "version": manifest["version"], "urls": sorted(urls),
                "notebooks": slugs, "cdnVerified": False,
                "symbolicaVersion": gallery["version"],
                "symbolicaWheel": urljoin(CDN + "/gallery/notebooks/", manifest["symbolicaNative"]["wheel"]),
                "symbolicaWasm": urljoin(CDN + "/gallery/notebooks/", manifest["symbolicaNative"]["url"]),
                "localAssets": sorted(p.name for p in (destination / "assets").iterdir()),
            }, indent=2) + "\n")
            for suffix in (".gz", ".br", ".zst"):
                Path(str(review / "index.html") + suffix).unlink(missing_ok=True)
            for path in stage.rglob("*"):
                if path.is_file() and path.suffix in {".html", ".css", ".js", ".mjs", ".json"}:
                    target = review / path.relative_to(stage)
                    for suffix in (".gz", ".br", ".zst"):
                        if not Path(str(path) + suffix).exists():
                            Path(str(target) + suffix).unlink(missing_ok=True)
            prune_text_sidecars(review)
            print(f"Prepared {len(slugs)} notebooks in {review}; CDN availability has not been verified.")
            return
        print(f"Checking {len(urls)} shared CDN assets before updating the site…", flush=True)
        with ThreadPoolExecutor(max_workers=8) as executor:
            failures = [error for error in executor.map(check_asset, sorted(urls)) if error]
        if failures:
            raise SystemExit("CDN assets are not ready; existing site left unchanged.\n" + "\n".join(failures))
        (destination / "cdn-assets.json").write_text(json.dumps({
            "origin": CDN, "version": manifest["version"], "urls": sorted(urls),
            "notebooks": slugs, "cdnVerified": True,
            "symbolicaVersion": gallery["version"],
            "symbolicaWheel": urljoin(CDN + "/gallery/notebooks/", manifest["symbolicaNative"]["wheel"]),
            "symbolicaWasm": urljoin(CDN + "/gallery/notebooks/", manifest["symbolicaNative"]["url"]),
            "localAssets": sorted(p.name for p in (destination / "assets").iterdir()),
        }, indent=2) + "\n")

        # Publish only after the complete staged release has passed its checks.
        shutil.copytree(stage, dist, dirs_exist_ok=True)
        index.write_text(page)
        for suffix in (".gz", ".br", ".zst"):
            Path(str(index) + suffix).unlink(missing_ok=True)
        # Large immutable binaries are now fetched from their verified CDN URLs.
        for relative in ("gallery/notebooks/immutable", "docs/live-python/immutable"):
            if (dist / relative).is_dir():
                shutil.rmtree(dist / relative)
        for slug in set(previous.get("notebooks", [])) - set(slugs):
            if re.fullmatch(r"[\w-]+", slug):
                for extension in (".html", ".py"):
                    (dist / "gallery/notebooks" / (slug + extension)).unlink(missing_ok=True)
        # Only prune assets previously imported by this script. On the first
        # CDN-editor migration, these are the upstream asset filenames copied
        # by the earlier sync script. Custom files in the directory stay intact.
        old_assets = previous.get("localAssets", [p.name for p in (notebooks / "assets").iterdir()])
        retained = {p.name for p in (destination / "assets").iterdir()}
        for name in set(old_assets) - retained:
            if Path(name).name == name:
                (dist / "gallery/notebooks/assets" / name).unlink(missing_ok=True)
        # Never let a pre-CDN compressed response mask the newly imported file.
        for path in stage.rglob("*"):
            if path.is_file() and path.suffix in {".html", ".css", ".js", ".mjs", ".json"}:
                target = dist / path.relative_to(stage)
                for suffix in (".gz", ".br", ".zst"):
                    if not Path(str(path) + suffix).exists():
                        Path(str(target) + suffix).unlink(missing_ok=True)

    prune_text_sidecars(dist)
    print(f"Imported {len(slugs)} live HEPkit notebooks with Symbolica {gallery['version']}; shared assets use {CDN}.")


if __name__ == "__main__":
    main()
