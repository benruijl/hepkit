#!/usr/bin/env python3
"""Build HEPkit's release-local search using the upstream reference extractor."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ICONS = {"search": "search", "x-circle": "circle-x", "x-lg": "x",
         "plus-lg": "plus", "dash-lg": "minus", "code": "code", "chevron-right": "chevron-right"}


def extractor(source):
    spec = importlib.util.spec_from_file_location("symbolica_search", source / "scripts/build_search.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Content(module.Content):
        # Standalone docs promote the class heading to H1, preserving its ID.
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if {"docs-breadcrumb", "docs-source"}.intersection(attrs.get("class", "").split()):
                attrs["aria-hidden"] = "true"
            attrs = list(attrs.items())
            super().handle_starttag("h2" if self.api and tag == "h1" else tag, attrs)

        def handle_endtag(self, tag):
            super().handle_endtag("h2" if self.api and tag == "h1" else tag)

    module.Content = Content
    return module


def records_for_page(module, html, relative, symbols):
    upstream = "docs/python_api/community/" + relative
    namespace = ""
    if Path(relative).name == "index.html":
        namespace = "symbolica.community." + ".".join(Path(relative).parent.parts)
        symbols = {**symbols, namespace: namespace.rsplit(".", 1)[0], "reference-title": namespace}
    records = module.page_records(html, upstream, symbols)
    for record in records:
        record["url"] = record["url"].replace("/docs/python_api/community/", "/docs/", 1)
        meta = record["meta"]
        meta["page_url"] = "/docs/" + relative
        meta["page_title"] = meta["page_title"].removesuffix(" — HEPkit documentation")
        meta["title"] = meta["title"].replace(" — HEPkit documentation", "")
        if namespace and meta["symbol"] in {namespace, "reference-title"}:
            meta.update(symbol="", module="", title=meta["page_title"], heading=meta["page_title"])
    overview = next((record for record in records if record["meta"]["title"] == record["meta"]["page_title"]), None)
    if overview:
        passages = json.loads(overview["meta"]["passages"])
        summary = next((passage["html"] for passage in passages if passage["kind"] == "prose" and not passage["label"]), "")
        for record in records:
            record["meta"]["page_summary"] = overview["meta"]["summary"]
            record["meta"]["page_summary_html"] = summary
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Symbolica website checkout")
    args = parser.parse_args()
    if not (ROOT / "scripts/search/node_modules/lucide-static").is_dir():
        raise SystemExit("Install the pinned search builder: npm ci --prefix scripts/search")
    module = extractor(args.source.resolve())
    symbols = module.shipped_symbols()
    manifest = json.loads((DIST / "docs/sync-manifest.json").read_text())
    records = []
    for page in manifest["pages"]:
        relative = page["relative"]
        records.extend(records_for_page(module, (DIST / "docs" / relative).read_text(), relative, symbols))
    for relative in ("index.html", "docs/index.html"):
        records.extend(module.page_records((DIST / relative).read_text(), relative, {}))
    with tempfile.TemporaryDirectory(prefix="hepkit-search-") as temporary:
        path = Path(temporary) / "records.json"
        path.write_text(json.dumps(records))
        subprocess.run(["node", str(ROOT / "scripts/search/build.mjs"), str(path),
                        str(DIST / "search/pagefind")], check=True)
    icons = DIST / "search/icons"
    icons.mkdir(exist_ok=True)
    library = ROOT / "scripts/search/node_modules/lucide-static"
    for name, icon in ICONS.items():
        shutil.copyfile(library / "icons" / f"{icon}.svg", icons / f"{name}.svg")
    shutil.copyfile(library / "LICENSE", icons / "LICENSE")
    # Retired indexes and compressed text must not shadow the new release.
    for relative in ("docs/search-index.json", "docs.js", "docs.css", "index.html"):
        path = DIST / relative
        for suffix in (".br", ".gz", ".zst"):
            path.with_name(path.name + suffix).unlink(missing_ok=True)
    (DIST / "docs/search-index.json").unlink(missing_ok=True)
    print(f"Built HEPkit search for {len(manifest['pages'])} reference pages.")


if __name__ == "__main__":
    main()
