#!/usr/bin/env python3
"""Render HEPkit and tensor reference sources into the standalone HEPkit theme."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import importlib.util
from html import escape
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
GROUPS = {
    "hepkit": "HEPkit",
    "tensor": "Tensor algebra",
    "graph": "Graph presentation",
    "hepkit/oneloop": "One-loop integrals",
    "hepkit/ibp": "Integration by parts",
    "hepkit/vakint": "Vacuum integrals",
    "hepkit/integration": "Exact integration",
    "hepkit/sector_decomposition": "Sector decomposition",
    "hepkit/rustred": "RustRed",
    "hep": "Numerical HEP tools",
    "hep/integration": "Numerical loop integration",
}


def plain(value):
    if isinstance(value, list):
        return "".join(map(plain, value))
    if not isinstance(value, dict):
        return ""
    kind, content = value.get("t"), value.get("c", [])
    if kind == "Str":
        return content
    if kind in {"Space", "SoftBreak", "LineBreak"}:
        return " "
    if kind in {"Code", "CodeBlock"}:
        return content[-1]
    if kind in {"Link", "Image"}:
        return plain(content[1])
    return plain(content)


def pandoc(text, source_format, output_format):
    result = subprocess.run(
        (["quarto", "pandoc"] if shutil.which("quarto") else ["pandoc"]) +
        ["--from=" + source_format, "--to=" + output_format,
         "--wrap=none", "--syntax-highlighting=pygments"],
        input=text, text=True, capture_output=True, check=True,
    )
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Symbolica website checkout")
    args = parser.parse_args()
    if not shutil.which("quarto") and not shutil.which("pandoc"):
        raise SystemExit("Syncing requires Quarto or Pandoc. Serving dist/ does not.")
    if not (ROOT / "scripts/search/node_modules/lucide-static").is_dir():
        raise SystemExit("Install the pinned search builder: npm ci --prefix scripts/search")
    source = args.source.resolve()
    manifest_path = DIST / "docs/sync-manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"pages": []}
    community = source / "docs/python_api/community"
    spec = importlib.util.spec_from_file_location("hepkit_search_builder", ROOT / "scripts/build-search.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    public_symbols = builder.extractor(source).shipped_symbols()
    files = sorted([*(community / "hepkit").rglob("*.qmd"),
                    *(community / "tensor").rglob("*.qmd"),
                    *(community / "graph").rglob("*.qmd"),
                    *(community / "hep").rglob("*.qmd")])
    files = [path for path in files if path.stem == "index" or
             "symbolica.community." + ".".join(path.relative_to(community).with_suffix("").parts) in public_symbols]
    if not files:
        raise SystemExit("No HEPkit or tensor documentation found")
    destinations = {path: path.relative_to(community).with_suffix(".html").as_posix() for path in files}
    classes = {path.stem: relative for path, relative in destinations.items() if path.stem != "index"}

    def convert(path):
        text = path.read_text()
        ast = json.loads(pandoc(text, "markdown+fenced_divs+header_attributes+pipe_tables+raw_html", "json"))
        relative = destinations[path]
        group = str(Path(relative).parent)
        title = GROUPS.get(group, group) if path.stem == "index" else plain(ast["meta"].get("title", {})) or path.stem
        summary = next((plain(block) for block in ast["blocks"] if block["t"] == "Para"), "")
        headings = []

        def walk(node):
            if isinstance(node, list):
                # Some upstream docstrings retain Sphinx roles. Render those
                # as code or local class links without touching code blocks.
                for i, inline in enumerate(node[:-1]):
                    following = node[i + 1]
                    if (isinstance(inline, dict) and inline.get("t") == "Str"
                            and re.search(r':(?:class|meth|attr):$', inline["c"])
                            and isinstance(following, dict) and following.get("t") == "Code"):
                        label = following["c"][1]
                        class_role = inline["c"].endswith(":class:")
                        inline["c"] = re.sub(r':(?:class|meth|attr):$', '', inline["c"])
                        if class_role and label in classes:
                            node[i + 1] = {"t": "Link", "c": [["", [], []], [following], ["/docs/" + classes[label], ""]]}
                for child in node:
                    walk(child)
            elif isinstance(node, dict):
                if node.get("t") == "Link":
                    target = urlsplit(node["c"][2][0])
                    if not target.scheme and not target.netloc and target.path.endswith(".qmd"):
                        resolved = (path.parent / target.path).resolve()
                        if resolved in destinations:
                            url = "/docs/" + destinations[resolved]
                        else:
                            url = "https://symbolica.io/" + resolved.relative_to(source).with_suffix(".html").as_posix()
                        node["c"][2][0] = url + ("?" + target.query if target.query else "") + ("#" + target.fragment if target.fragment else "")
                for child in node.values():
                    walk(child)

        walk(ast)
        # Preserve the upstream API anchor as the page heading.
        if ast["blocks"] and ast["blocks"][0]["t"] == "Header":
            ast["blocks"][0]["c"][0] = 1
            ast["blocks"][0]["c"][2] = [{"t": "Str", "c": title}]
        else:
            ast["blocks"].insert(0, {"t": "Header", "c": [1, ["reference-title", [], []], [{"t": "Str", "c": title}]]})
        for i, block in enumerate(ast["blocks"]):
            if block["t"] == "Header" and block["c"][0] == 2:
                label, anchor = plain(block["c"][2]), block["c"][1][0]
                excerpt = next((plain(b) for b in ast["blocks"][i+1:i+4] if b["t"] == "Para"), "")
                headings.append({"title": label, "id": anchor, "summary": excerpt[:200]})
        return {"title": title, "group": group, "relative": relative,
                "url": "/docs/" + relative, "summary": summary,
                "body": pandoc(json.dumps(ast), "json", "html5"), "headings": headings,
                "source": path.relative_to(source).as_posix(),
                "sha256": hashlib.sha256(text.encode()).hexdigest()}

    with ThreadPoolExecutor(max_workers=4) as pool:
        pages = list(pool.map(convert, files))

    home = (DIST / "index.html").read_text()
    header = re.search(r'<header class="site-header">.*?</header>', home, re.S).group()
    header = header.replace('href="./"', 'href="/"').replace('src="assets/', 'src="/assets/').replace('href="#', 'href="/#')
    header = header.replace('class="nav-docs"', 'class="nav-docs" aria-current="page"')

    def sidebar(current):
        links = '<a class="docs-home" href="/docs/"' + (' aria-current="page"' if current == "index.html" else '') + '>Documentation overview</a>'
        for group, label in GROUPS.items():
            items = sorted([p for p in pages if p["group"] == group], key=lambda p: (Path(p["relative"]).stem != "index", p["title"].lower()))
            opened = ' open' if current.startswith(group + "/") and str(Path(current).parent) == group else ''
            links += f'<details class="docs-nav-group"{opened}><summary>{escape(label)} <span>{len(items)}</span></summary><ul>'
            for page in items:
                selected = ' aria-current="page"' if page["relative"] == current else ''
                name = "Overview" if Path(page["relative"]).stem == "index" else page["title"]
                links += f'<li><a href="{page["url"]}"{selected}>{escape(name)}</a></li>'
            links += '</ul></details>'
        return f'''<aside class="docs-sidebar" aria-label="Documentation navigation">
<button class="docs-search-open" type="button" data-site-search title="Search reference"><i class="bi bi-search" aria-hidden="true"></i><span>Search reference</span></button>
<details class="docs-menu" open><summary>Browse documentation</summary><nav aria-label="API reference">{links}</nav></details>
</aside>'''

    def render(title, relative, body, summary, group="", headings=()):
        toc = ''.join(f'<li><a href="#{escape(h["id"], quote=True)}">{escape(h["title"])}</a></li>' for h in headings)
        onpage = f'<aside class="docs-toc" aria-label="On this page"><p>On this page</p><ul>{toc}</ul></aside>' if toc else ''
        crumb = f'<span aria-hidden="true">/</span> <a href="/docs/{group}/">{escape(GROUPS.get(group, group))}</a>' if group else ''
        return f'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} — HEPkit documentation</title>
<meta name="description" content="{escape(summary[:240], quote=True)}">
<meta name="theme-color" content="#176f5e"><meta name="color-scheme" content="light dark">
<link rel="canonical" href="https://hepkit.org/docs/{relative}">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<script src="/theme.js"></script><link rel="stylesheet" href="/styles.css"><link rel="stylesheet" href="/docs.css"><link rel="stylesheet" href="/search/search.css">
</head><body class="docs-page"><a class="skip-link" href="#main">Skip to content</a>{header}
<div class="docs-layout">{sidebar(relative)}<main id="main" class="docs-main">
<div class="docs-breadcrumb"><a href="/docs/">Documentation</a>{crumb}</div>
<article class="docs-content">{body}</article>
</main>{onpage}</div><script src="/docs.js" defer></script><script type="module" src="/search/search.js"></script></body></html>'''

    # Finish rendering before replacing any previously generated pages.
    output = {}
    for page in pages:
        output[page["relative"]] = render(page["title"], page["relative"], page["body"], page["summary"], page["group"], page["headings"])

    landing = (ROOT / "scripts/docs-overview.html").read_text().replace("{{PAGE_COUNT}}", str(len(pages)))
    output["index.html"] = render("Documentation", "index.html", landing, "HEPkit Python API: models, Feynman diagrams, tensors, loop amplitudes, and integral reduction.")
    for relative, html in output.items():
        path = DIST / "docs" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)
        for suffix in (".br", ".gz", ".zst"):
            path.with_name(path.name + suffix).unlink(missing_ok=True)
    # Remove only obsolete reference pages owned by the previous import.
    # Runtime assets under docs/live-python are never managed by this sync.
    for page in previous["pages"]:
        relative = Path(page["relative"])
        if (not relative.is_absolute() and ".." not in relative.parts
                and relative.parts[0] in {"hepkit", "tensor", "hep", "graph"}
                and relative.suffix == ".html" and relative.as_posix() not in output):
            (DIST / "docs" / relative).unlink(missing_ok=True)
    manifest = {"synced_at": datetime.now(timezone.utc).isoformat(), "pages": [{k: p[k] for k in ["relative", "source", "sha256"]} for p in pages]}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    subprocess.run([sys.executable, str(ROOT / "scripts/build-search.py"), str(source)], check=True)
    print(f"Synced {len(pages)} reference pages and their full-text search into {DIST / 'docs'}")


if __name__ == "__main__":
    main()
