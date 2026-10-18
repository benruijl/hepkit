"""Keep notebook documents and workers local while sharing the editor on the CDN."""

from __future__ import annotations

import html
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit, urlunsplit


TEXT_SUFFIXES = {".js", ".mjs", ".css"}
ASSET_NAME = re.compile(
    r"(?<![A-Za-z0-9_.-])([A-Za-z0-9_.-]+\.(?:js|mjs|css|wasm|woff2|woff|ttf|png|svg))"
    r"(?![A-Za-z0-9_.-])"
)
TAG = re.compile(r"<(?:script|link)\b[^>]*>", re.I)
ATTRIBUTE = re.compile(r'''\b([\w-]+)\s*=\s*(["'])(.*?)\2''', re.S)
WORKER = re.compile(r"\bnew\s+Worker\s*\(")
QUOTED_JS = re.compile(r'''(["'`])([^"'`\n]+\.m?js(?:\?[^"'`\n]*)?)\1''')


def _attributes(tag: str) -> dict[str, str]:
    return {match[1].lower(): html.unescape(match[3]) for match in ATTRIBUTE.finditer(tag)}


def _worker_literals(text: str):
    """Read the URL literals in generated direct/nested-URL Worker constructors.

    Dynamic workers, including Plotly's blob workers, are deliberately excluded.
    Those remain unchanged by the browser adapter.
    """
    for match in WORKER.finditer(text):
        argument = text[match.end():match.end() + 600].lstrip()
        if not re.match(r'''(?:new\s+URL\s*\(|["'`])''', argument):
            continue
        literal = QUOTED_JS.search(argument)
        if literal:
            yield literal[2]
    # Marimo also stores URL objects before passing them to its worker helper.
    for match in re.finditer(r"\bnew\s+URL\s*\(", text):
        literal = QUOTED_JS.match(text[match.end():].lstrip())
        if literal and re.fullmatch(r"(?:save-)?worker-[\w-]+\.js", Path(urlsplit(literal[2]).path).name):
            yield literal[2]


def _adapter(cdn: str, paths: dict[str, str]) -> str:
    origin = urlsplit(cdn)
    origin = urlunsplit((origin.scheme, origin.netloc, "", "", ""))
    # This runs before the notebook's warm worker and before any module script.
    # URL parameters and Worker options survive mapping; blob/local URLs do too.
    return """<script data-hepkit-cdn-workers>
(() => {
  const NativeWorker = window.Worker;
  if (!NativeWorker) return;
  const cdnOrigin = CDN_ORIGIN;
  const localWorkers = WORKER_PATHS;
  // Map worker URL objects before Marimo chooses its cross-origin blob helper.
  const NativeURL = window.URL;
  window.URL = class HEPkitURL extends NativeURL {
    constructor(input, base) {
      super(input, base);
      const local = this.origin === cdnOrigin && localWorkers[this.pathname];
      if (local) this.href = new NativeURL(local + this.search + this.hash, window.location.origin).href;
    }
  };
  window.Worker = class HEPkitWorker extends NativeWorker {
    constructor(scriptURL, options) {
      const url = new NativeURL(String(scriptURL), document.baseURI);
      let target = scriptURL;
      if (url.protocol !== 'blob:' && url.origin === cdnOrigin) {
        const local = localWorkers[url.pathname];
        if (!local) {
          throw new DOMException(
            'HEPkit has no local adapter for CDN worker ' + url.pathname +
            '. Refresh this page or update the notebook export.', 'SecurityError');
        }
        target = new NativeURL(local + url.search + url.hash, window.location.origin).href;
      }
      super(target, options);
    }
  };
})();
</script>""".replace("CDN_ORIGIN", json.dumps(origin)).replace("WORKER_PATHS", json.dumps(paths, sort_keys=True))


def prepare_cdn_editor(stage: Path, manifest: dict, cdn: str) -> set[str]:
    """Prepare a staged gallery and return every reachable shared asset URL.

    Call after the Symbolica URL rewriter and CSS font rewrite. The only files
    removed belong to the temporary stage's imported assets directory.
    """
    stage = Path(stage)
    notebooks = stage / "gallery/notebooks"
    assets = notebooks / "assets"
    pages = sorted(notebooks.glob("*.html"))
    files = {path.name: path for path in assets.iterdir() if path.is_file()}
    texts = {name: path.read_text() for name, path in files.items() if path.suffix in TEXT_SUFFIXES}
    names = set(files)
    references = {name: set(ASSET_NAME.findall(text)) & names for name, text in texts.items()}
    entry = manifest["frontend"]["entry"]
    roots = set(manifest["frontend"]["files"])
    if entry not in roots or not roots <= names:
        raise ValueError("The current editor manifest has missing assets")
    page_texts = {page: page.read_text() for page in pages}
    for text in page_texts.values():
        roots.update(set(ASSET_NAME.findall(text)) & names)

    reachable: set[str] = set()
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(references.get(name, set()) - reachable)

    cdn_base = cdn.rstrip("/") + "/"
    cdn_origin = urlsplit(cdn_base).netloc
    asset_base = urljoin(cdn_base, "gallery/notebooks/assets/")
    worker_paths: dict[str, str] = {}
    local_worker_names: set[str] = set()
    for name in sorted(reachable):
        if files[name].suffix not in {".js", ".mjs"}:
            continue
        for literal in _worker_literals(texts[name]):
            url = urlsplit(urljoin(asset_base + name, literal))
            if url.netloc != cdn_origin:
                continue
            local = stage / url.path.lstrip("/")
            if not local.is_file():
                raise ValueError(f"Missing local worker adapter target: {url.path}")
            worker_paths[url.path] = "/" + local.relative_to(stage).as_posix()
            if local.parent == assets:
                local_worker_names.add(local.name)
    if not worker_paths or not local_worker_names:
        raise ValueError("No editor workers found; review the current Worker constructors")

    # The execution/save workers import the local bootstrap. Walk their entire
    # literal dependency graph so a later worker build cannot lose a helper.
    local_names = set(local_worker_names)
    pending = list(local_worker_names)
    while pending:
        found = references.get(pending.pop(), set()) - local_names
        local_names.update(found)
        pending.extend(found)
    styles = {name for name in reachable if files[name].suffix == ".css"}
    local_names.update(styles)
    adapter = _adapter(cdn, worker_paths)

    for page, text in page_texts.items():
        if "data-hepkit-cdn-workers" in text:
            raise ValueError(f"Notebook already has a CDN Worker adapter: {page.name}")
        stylesheet_tags = []
        present_styles = set()
        module_tags = []
        for match in TAG.finditer(text):
            attrs = _attributes(match[0])
            path = Path(urlsplit(attrs.get("href", "")).path)
            if "stylesheet" in attrs.get("rel", "").split() and path.name in styles:
                stylesheet_tags.append(match[0])
                present_styles.add(path.name)
            src = attrs.get("src", "")
            if attrs.get("type") == "module" and Path(urlsplit(src).path).name == entry:
                module_tags.append((match[0], src))
        if len(module_tags) != 1:
            raise ValueError(f"Expected one current editor module in {page.name}")
        module_tag, src = module_tags[0]
        parsed = urlsplit(src)
        remote_src = urlunsplit((*urlsplit(asset_base + entry)[:3], parsed.query, parsed.fragment))
        remote_tag = re.sub(
            r'''(\bsrc\s*=\s*)(["'])(.*?)\2''',
            lambda match: match[1] + match[2] + html.escape(remote_src, quote=True) + match[2],
            module_tag, count=1, flags=re.S,
        )
        # Keep the original stylesheet order, then add lazy feature styles. All
        # precede the deferred module, making them available to shadow roots.
        for tag in stylesheet_tags:
            text = text.replace(tag, "", 1)
        stylesheet_tags.extend(
            f'<link rel="stylesheet" href="/gallery/notebooks/assets/{name}">'
            for name in sorted(styles - present_styles)
        )
        text = text.replace(module_tag, "\n".join(stylesheet_tags) + "\n" + remote_tag, 1)
        text, count = re.subn(r"<head(?:\s[^>]*)?>", lambda match: match[0] + "\n" + adapter, text, count=1)
        if count != 1:
            raise ValueError(f"Expected a head element in {page.name}")
        page.write_text(text)

    # The complete unchanged frontend graph lives at one CDN origin, preserving
    # module identity even when a lazy chunk imports back into the entry module.
    # Some worker helpers also occur in the editor's CDN import graph. Validate
    # the complete reachable set, including modules retained for local workers.
    urls = {
        asset_base + name + ("?v=" + manifest["version"] if files[name].suffix in {".js", ".mjs"} else "")
        for name in reachable
    }
    # The CDN type client carries its own pinned WASM/stub URLs. It is about to
    # be removed locally, so collect those references before the caller scans
    # the much smaller remaining stage.
    absolute_cdn = re.compile(re.escape(cdn_base) + r'''[^\s"'<>`)]+''')
    for name in reachable:
        for url in absolute_cdn.findall(texts.get(name, "")):
            if not url.endswith("/"):
                urls.add(html.unescape(url))
    # Lazy module preload maps can still request CDN copies of these styles;
    # local copies exist specifically for marimo's same-origin shadow styling.
    urls.update(asset_base + name for name in styles)
    for name, path in files.items():
        if name not in local_names:
            path.unlink()
    return urls
