"""Guard gallery runtime pins and prevent stale encoded loaders in previews."""
import functools
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


sync = module("sync_gallery", ROOT / "scripts/sync-gallery.py")
serve = module("serve", ROOT / "scripts/serve.py")


class GallerySyncTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_full_gallery_pin_is_independent_of_lightweight_docs(self):
        path = self.root / "scripts/gallery/live-python-config.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"version": "3.0.2", "wheel": "wheels/symbolica-3.0.2.whl"}))
        docs = self.root / "docs/live-python/config.json"
        docs.parent.mkdir(parents=True)
        docs.write_text('{"wheel":"a-different-lightweight-wheel.whl"}')
        manifest = {"liveConfigSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "symbolicaNative": {"wheel": "immutable/hash/symbolica-3.0.2.whl"}}
        self.assertEqual(sync.gallery_config(self.root, manifest)["version"], "3.0.2")
        manifest["symbolicaNative"]["wheel"] = "immutable/hash/symbolica-3.0.0.whl"
        with self.assertRaisesRegex(ValueError, "does not match its native WASM"):
            sync.gallery_config(self.root, manifest)
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError, "configuration changed"):
            sync.gallery_config(self.root, manifest)

    def test_retired_variants_are_pruned_without_changing_source_files(self):
        for extension in (".js", ".mjs", ".json", ".css", ".html"):
            path = self.root / ("current" + extension)
            path.write_text("current release")
            for suffix in (".br", ".gz", ".zst"):
                path.with_name(path.name + suffix).write_bytes(b"obsolete")
        native = self.root / "native.wasm.br"
        native.write_bytes(b"maintained binary sidecar")
        sync.prune_text_sidecars(self.root)
        self.assertEqual(list(self.root.glob("*.br")), [native])
        self.assertFalse(list(self.root.glob("*.gz")))
        self.assertFalse(list(self.root.glob("*.zst")))
        self.assertEqual((self.root / "current.mjs").read_text(), "current release")

    def test_prepared_site_matches_the_current_full_gallery_runtime(self):
        source = ROOT.parent / "website"
        build = json.loads((source / "gallery/notebooks/build.json").read_text())
        config = sync.gallery_config(source, build)
        notebooks = ROOT / "dist/gallery/notebooks"
        published = json.loads((notebooks / "build.json").read_text())
        cdn = json.loads((notebooks / "cdn-assets.json").read_text())
        self.assertEqual(published["version"], build["version"], "Run scripts/sync-gallery.py ../website")
        self.assertEqual(published["symbolicaNative"], build["symbolicaNative"])
        self.assertEqual(cdn["symbolicaVersion"], config["version"])
        self.assertTrue(cdn["cdnVerified"])
        bootstrap = (notebooks / "assets/symbolica-bootstrap.mjs").read_text()
        for key, field in (("symbolicaWheel", "wheel"), ("symbolicaWasm", "url")):
            expected = sync.CDN + "/gallery/notebooks/" + build["symbolicaNative"][field]
            self.assertEqual(cdn[key], expected)
            self.assertIn(expected, bootstrap)
            self.assertIn(expected, cdn["urls"])

    def test_preview_ignores_stale_compressed_loader_and_lockfile(self):
        for name in ("bootstrap.mjs", "pyodide-lock.json"):
            (self.root / name).write_bytes(b"current 3.0.2")
            (self.root / (name + ".gz")).write_bytes(gzip.compress(b"old 3.0.0"))
        native = b"\0asm\1\0\0\0"
        (self.root / "native.wasm").write_bytes(native)
        (self.root / "native.wasm.gz").write_bytes(gzip.compress(native))

        class QuietHandler(serve.Handler):
            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0),
                                     functools.partial(QuietHandler, directory=str(self.root)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for name in ("bootstrap.mjs", "pyodide-lock.json"):
                with self.subTest(name=name):
                    request = Request(f"http://127.0.0.1:{server.server_port}/{name}?v=current",
                                      headers={"Accept-Encoding": "gzip"})
                    with urlopen(request) as response:
                        self.assertEqual(response.read(), b"current 3.0.2")
                        self.assertIsNone(response.headers.get("Content-Encoding"))
            request = Request(f"http://127.0.0.1:{server.server_port}/native.wasm",
                              headers={"Accept-Encoding": "gzip"})
            with urlopen(request) as response:
                self.assertEqual(response.headers["Content-Encoding"], "gzip")
                self.assertEqual(gzip.decompress(response.read()), native)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
