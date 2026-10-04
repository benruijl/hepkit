# HEPkit website

Standalone static website prepared for **hepkit.org**. Publish the contents of
`dist/` as the web root. The site does not require Quarto, Node.js, a backend,
or access to the adjacent Symbolica checkout after the files have been synced.
The notebook editor, shared runtimes, and dependencies load from
[Symbolica's CDN](https://cdn.symbolica.io/).

## Preview

```sh
python3 scripts/serve.py
```

Open http://localhost:8766/. Use `--port 8080` to choose another port.
The preview server serves the provided Brotli or gzip sidecars when supported
by the browser. It is a development server, not a production server.

## Contents

- `dist/index.html`: introduction, four live HEPkit examples, ten contributing
  projects with authors and citations, optional backend credits, and links to
  the local documentation. Page content works without JavaScript.
- `dist/styles.css`: responsive layout and notebook dialog styles.
- `dist/theme.js`: persistent light/dark preference with a system default.
- `dist/gallery.js`: Symbolica gallery's lazy-loading notebook dialog, source
  draft preservation, keyboard dismissal, and focus restoration.
- `dist/assets/`: existing HEPkit branding from the Symbolica website.
- `dist/gallery/notebooks/`: original Python notebook sources, generated
  notebook HTML, local editor CSS, execution/save workers and their bootstrap,
  and the pinned package lockfile. Editor JavaScript loads from the CDN.
  `cdn-assets.json` records the shared assets served by Symbolica's CDN.
- `dist/docs/`: 117 HEPkit and tensor reference pages, an overview, and a
  page/method search index, styled in the same light/dark theme as the homepage.
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

Keep the `GALLERY:START` and `GALLERY:END` comments in `dist/index.html` when
editing the page. The rest of the page, including project credits, is edited
directly and is not overwritten by the sync script.

## Sync the documentation

From this directory, run:

```sh
python3 scripts/sync-docs.py ../website
```

This imports `docs/python_api/community/hepkit/` and `tensor/` from the
Symbolica website's QMD sources. Quarto's bundled Pandoc renders the Markdown
without running Python examples or invoking the Symbolica website build.
Quarto is required only for this sync step; the generated site remains static.

The script regenerates all reference pages, navigation, the search index, and
`dist/docs/sync-manifest.json` with source paths and SHA-256 hashes. Local API
links and original method anchors are retained; references to the broader
Symbolica API point to symbolica.io. Previously imported pages removed upstream
are removed on the next sync, while notebook support files are preserved.
Native-only APIs remain documented even though the homepage showcases only
browser-capable notebooks.

To change the presentation, edit `dist/docs.css`, `dist/docs.js`, and
`scripts/docs-overview.html`. The shared header and theme come from the
homepage and `dist/theme.js`. Do not hand-edit generated reference HTML;
update its source in the Symbolica checkout and rerun the sync command.
This is an on-demand sync, not a scheduled job.

## Hosting

The prepared site is about **5.6 MB** (about 6 MB of filesystem space), including
all 117 reference pages. Local notebook support assets account for about 665 KB;
editor bundles, chunks, fonts, images, Python packages and WASM load from the CDN.

Copy the **contents of `dist/`** into hepkit.org's web root, preserving the
directory structure. You can also copy the entire `hepkit` folder and configure
the server's document root to point to `hepkit/dist`. No build step, backend,
Python installation, or source checkout is needed on the server.

Serve the site over HTTPS at the domain root. Paths such as `/docs/` assume
this location; publishing it under a `/hepkit/` URL prefix is not supported.
Serve `.wasm` files with `Content-Type: application/wasm` and `.mjs` files as
JavaScript. Compression is useful for the local JavaScript and CSS. If serving
precompressed `.br`, `.gz`, or `.zst` sidecars, negotiate them for the original
URL with the correct `Content-Encoding` and `Vary: Accept-Encoding` headers.

Editor JavaScript and the large Python, Symbolica, and type-checker runtimes
are served by Symbolica's CDN with its compression and caching; visitors need
access to that CDN to run notebooks. Optional Python imports may also fetch
packages from the Pyodide CDN or PyPI.

Metadata uses `https://hepkit.org/` as the canonical origin. This checkout does
not configure DNS or deploy the domain. Preserve upstream license notices and
the relevant software licensing terms when publishing the site.

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
