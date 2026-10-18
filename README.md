# HEPkit website

Standalone static website prepared for **hepkit.org**. Publish the contents of
`dist/` as the web root. The deployed site does not require Quarto, Node.js, a backend,
or access to the adjacent Symbolica checkout after the files have been synced.
The notebook editor, shared runtimes, and dependencies load from
[Symbolica's CDN](https://cdn.symbolica.io/).

## Preview

```sh
python3 scripts/serve.py
```

Open http://localhost:8766/. Use `--port 8080` to choose another port.
The preview server serves current text files directly, so retired compressed
loaders cannot mask an update. It supports Brotli or gzip sidecars for binary
archives and WASM. It is a development server, not a production server.

## Contents

- `dist/index.html`: introduction, five live HEPkit examples, ten contributing
  projects with authors and citations, optional backend credits, and links to
  the local documentation. Page content works without JavaScript.
- `dist/styles.css`: responsive layout and notebook dialog styles.
- `dist/theme.js`: persistent light/dark preference with a system default.
- `dist/gallery.js`: Symbolica gallery's lazy-loading notebook dialog, source
  draft preservation, keyboard dismissal, focus restoration, and per-notebook
  “Run locally” dialog with a copyable uv command and the notebook download. Direct
  `.py` downloads still work without JavaScript or with modified clicks.
- `dist/assets/`: existing HEPkit branding from the Symbolica website.
- `dist/gallery/notebooks/`: original Python notebook sources, generated
  notebook HTML, local editor CSS, execution/save workers and their bootstrap,
  and the pinned package lockfile. Editor JavaScript loads from the CDN.
  `cdn-assets.json` records the shared assets served by Symbolica's CDN.
- `dist/docs/`: HEPkit, numerical HEP, and tensor reference pages and an overview,
  styled in the same light/dark theme as the homepage.
- `dist/search/`: local Pagefind search, rich method previews, API autocomplete,
  and optional spelling suggestions. Search loads only when opened.
- `dist/docs/live-python/`: the local type-checker worker; its runtime and
  type information load from Symbolica's CDN.

The browser loads the notebook runtime only after a visitor opens an example.
Closing a notebook releases its workers and preserves source edits in memory
until the page is reloaded. Outputs and Python state are not preserved.
Native-only examples are excluded from the live gallery.

## Update the notebooks

After building the gallery in the adjacent Symbolica website checkout and
publishing its current editor frontend and shared assets to Symbolica's CDN:

```sh
python3 scripts/sync-gallery.py ../website
```

This stages the browser-capable HEPkit catalog (excluding examples marked
"Run locally"), generated notebooks, and frontend assets. The editor's current
JavaScript entry point and complete dependency graph load unchanged from
`cdn.symbolica.io`. Python runtimes, standard library, wheels, Symbolica WASM,
type-checker dependencies, fonts, images, and dynamically loaded editor assets
also use their pinned CDN URLs.

The sync checks imported frontend assets against the upstream SHA-256 manifest
and verifies every CDN URL's availability, CORS headers, and content type
before writing `dist/`. New asset versions must already be published on
Symbolica's CDN; the sync refuses unavailable or incompatible assets.

The full notebook wheel is pinned by the gallery's
`scripts/gallery/live-python-config.json`, independently of the lightweight
documentation snippets. The sync validates that pin against the notebook build
manifest. `cdn-assets.json` records the Symbolica version, wheel, native WASM,
and whether all CDN checks passed. The current gallery uses Symbolica 3.0.2.

Notebook HTML, execution/save worker entry points and their bootstrap, the
type-checker worker, editor CSS, and the package lockfile remain local. An
adapter installed before the editor loads routes its known worker URLs to the
local copies, preserving same-origin worker creation. The required editor CSS
is loaded locally up front so Marimo can copy it into widget shadow roots;
its fonts and images still load from the CDN.

The sync records CDN references in `dist/gallery/notebooks/cdn-assets.json`
and prunes previously imported frontend and runtime assets. The deployment
contains the current release's required local files without accumulating
duplicate editor bundles or local copies of CDN dependencies.

To prepare a review copy while a new CDN release is pending, run
`python3 scripts/sync-gallery.py ../website --stage /tmp/hepkit-review`.
This leaves `dist/` unchanged and marks the review manifest as unverified.
Rerun the ordinary sync after the assets are available on the CDN.

Keep the `GALLERY:START` and `GALLERY:END` comments in `dist/index.html` when
editing the page. The rest of the page, including project credits, is edited
directly and is not overwritten by the sync script.

## Sync the documentation

From this directory, run:

```sh
npm ci --prefix scripts/search
python3 scripts/sync-docs.py ../website
```

This imports the public API in `docs/python_api/community/hepkit/`, `hep/`,
`tensor/`, and the shared `graph/` presentation types from the
Symbolica website's QMD sources. Quarto's bundled Pandoc or standalone Pandoc renders the Markdown
without running Python examples or invoking the Symbolica website build.
Quarto or Pandoc and Node.js are required only for this sync step; the generated
site remains static.

The script regenerates all reference pages, navigation, the Pagefind index, and
`dist/docs/sync-manifest.json` with source paths and SHA-256 hashes. Local API
links and original method anchors are retained; references to the broader
Symbolica API point to symbolica.io. Previously imported pages removed upstream
are removed on the next sync, while notebook support files are preserved.
Canonical symbols are checked against the shipped type stubs. Retired API pages
are excluded, and re-exported graph types use their shared graph reference rather
than stale copies under HEPkit and tensor modules.
Native-only APIs remain documented even though the homepage showcases only
browser-capable notebooks.

To change the presentation, edit `dist/docs.css`, `dist/docs.js`, and
`scripts/docs-overview.html`. The shared header and theme come from the
homepage and `dist/theme.js`. Do not hand-edit generated reference HTML;
update its source in the Symbolica checkout and rerun the sync command.
This is an on-demand sync, not a scheduled job.

Search is adapted from Symbolica's structured search. It indexes complete public
API sections and examples against the shipped type stubs, not just names and
summaries. Results group methods under their class, keep signatures out of
previews, and retain local subsection anchors. API autocomplete and spelling
correction are separate; corrections require explicit acceptance. The standalone
sync uses the upstream reference extractor at build time, while its pinned
Pagefind/KaTeX and spelling builder modules live in `scripts/search/`. Lucide
icons are copied locally with their license, without loading an icon font.

To rebuild search without rerendering the reference:

```sh
python3 scripts/build-search.py ../website
```

Deploy the whole `dist/search/` directory together with the matching HTML.
Keep it same-origin with cache revalidation, not an immutable-cache rule. Search
does not use Algolia or a hosted service. Each build replaces the complete index
and removes the retired `docs/search-index.json` file.

Search regression tests:

```sh
python3 scripts/test-search.py
python3 scripts/test-search-browser.py
```

## Hosting

The prepared site includes the current public reference pages. Local notebook support
assets account for about 665 KB;
editor bundles, chunks, fonts, images, Python packages and WASM load from the CDN.

Copy the **contents of `dist/`** into hepkit.org's web root, preserving the
directory structure. You can also copy the entire `hepkit` folder and configure
the server's document root to point to `hepkit/dist`. No build step, backend,
Python installation, or source checkout is needed on the server.

Synchronize a deployment so retired files are removed, or use a fresh document
root. Merely overwriting existing files can leave old compressed loaders or
lockfiles that still request removed wheels. The sync removes text `.br`,
`.gz`, and `.zst` sidecars from `dist/`; use dynamic server compression for text.

Serve the site over HTTPS at the domain root. Paths such as `/docs/` assume
this location; publishing it under a `/hepkit/` URL prefix is not supported.
Serve `.wasm` files with `Content-Type: application/wasm` and `.mjs` files as
JavaScript. Compress local JavaScript, CSS, and JSON dynamically. Restrict
precompressed sidecars to maintained binary assets and negotiate them for the
original URL with the correct `Content-Encoding` and `Vary: Accept-Encoding`
headers.

Editor JavaScript and the large Python, Symbolica, and type-checker runtimes
are served by Symbolica's CDN with its compression and caching; visitors need
access to that CDN to run notebooks. Optional Python imports may also fetch
packages from the Pyodide CDN or PyPI.

Metadata uses `https://hepkit.org/` as the canonical origin. This checkout does
not configure DNS or deploy the domain. Preserve upstream license notices and
the relevant software licensing terms when publishing the site.

Runtime pin and compressed-loader regression tests:

```sh
python3 scripts/test-gallery-sync.py
```

## Content provenance

The gallery and HEPkit branding come from the Symbolica website checkout.
Project descriptions and credits were checked against the integrated
dependencies and upstream citation metadata on 3 October 2026:

- [Symbolica citation](https://zenodo.org/records/17054381)
- [FeynKit, Spenso, Idenso, Linnet, and Vakint product registry](https://github.com/alphal00p/gammaloop/blob/feynkit/docs/products/registry.toml)
- [Graphica package metadata](https://github.com/symbolica-dev/graphica/blob/main/Cargo.toml)
- [one-loop-reduce citations](https://github.com/lcnbr/one-loop-reduce/blob/main/crates/one-loop-reduce-python/src/lib.rs)
- [OneLoopMaster credits](https://github.com/alphal00p/oneloopmaster#credits-and-references)
- [RustRed citation](https://github.com/alphal00p/rustred/blob/main/CITATION.cff)
- [Vakint external backend citations](https://github.com/alphal00p/gammaloop/blob/feynkit/crates/vakint/src/citations.rs)

FeynKit and OneLoopMaster use collective attribution where their upstream
records do not name individual authors. OneLoopMaster separately credits the
original OneLOop work by Andreas van Hameren. FORM, MATAD, FMFT, and pySecDec
are listed as optional external tools rather than bundled HEPkit packages.
