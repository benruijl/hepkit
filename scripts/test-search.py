"""Check standalone reference extraction, local anchors and upstream provenance."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_search", ROOT / "scripts/build-search.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROOT.parent / "website"
        cls.extract = build.extractor(cls.source)

    def test_class_heading_and_local_method_anchors(self):
        html = '''<title>IBPFamily — HEPkit documentation</title><main>
        <div>Unrelated breadcrumb</div><article>
        <h1 id="symbolica.community.hepkit.IBPFamily">IBPFamily</h1>
        <pre><code>class IBPFamily</code></pre><p>Exact IBP relations.</p>
        <h2 id="symbolica.community.hepkit.IBPFamily.solve_parametric">solve_parametric</h2>
        <pre><code>solve_parametric(sector: list[int])</code></pre><p>Find a recurrence.</p>
        <h3 id="examples-4">Examples</h3><p>Inspect residual integrals.</p>
        <pre><code>family.solve_parametric([1, 1])</code></pre></article></main>'''
        symbols = {name: "symbolica.community.hepkit" for name in (
            "symbolica.community.hepkit.IBPFamily", "symbolica.community.hepkit.IBPFamily.solve_parametric")}
        records = build.records_for_page(self.extract, html, "hepkit/IBPFamily.html", symbols)
        self.assertEqual([record["meta"]["title"] for record in records], ["IBPFamily", "IBPFamily.solve_parametric"])
        self.assertEqual(records[1]["url"], "/docs/hepkit/IBPFamily.html#symbolica.community.hepkit.IBPFamily.solve_parametric")
        for record in records:
            self.assertEqual(record["meta"]["page_title"], "IBPFamily")
            self.assertEqual(record["meta"]["page_summary"], "Exact IBP relations.")
            self.assertNotIn("Unrelated breadcrumb", record["content"])
        passages = json.loads(records[1]["meta"]["passages"])
        self.assertTrue(any(passage["anchor"] == "examples-4" for passage in passages))
        self.assertFalse(any("sector:" in passage["html"] for passage in passages))

    def test_synced_docs_match_upstream_sources(self):
        manifest = json.loads((ROOT / "dist/docs/sync-manifest.json").read_text())
        symbols = self.extract.shipped_symbols()
        for page in manifest["pages"]:
            with self.subTest(page=page["relative"]):
                self.assertEqual(hashlib.sha256((self.source / page["source"]).read_bytes()).hexdigest(), page["sha256"])
                html = (ROOT / "dist/docs" / page["relative"]).read_text()
                self.assertIn('src="/search/search.js"', html)
                self.assertIn('href="/search/search.css"', html)
                self.assertNotIn('class="docs-source"', html)
                self.assertNotIn("Reference synced from", html)
                self.assertTrue(build.records_for_page(self.extract, html, page["relative"], symbols))
        self.assertFalse((ROOT / "dist/docs/search-index.json").exists())
        self.assertFalse((ROOT / "dist/docs/hepkit/AmplitudeRender.html").exists())
        self.assertFalse((ROOT / "dist/docs/hepkit/RenderSettings.html").exists())
        self.assertTrue((ROOT / "dist/docs/graph/RenderSettings.html").is_file())

    def test_module_overview_is_indexed_without_navigation(self):
        html = '''<title>Graph presentation — HEPkit documentation</title><main>
        <div class="docs-breadcrumb">Unrelated breadcrumb</div><article>
        <h1 id="symbolica.community.graph">Graph presentation</h1>
        <p>Shared typed graph settings and exports.</p></article>
        <p class="docs-source">Unrelated source credit</p></main>'''
        records = build.records_for_page(self.extract, html, "graph/index.html", {})
        self.assertEqual(len(records), 1)
        self.assertIn("Shared typed graph settings", records[0]["content"])
        self.assertNotIn("Unrelated", records[0]["content"])
        self.assertEqual(records[0]["meta"]["page_summary"], "Shared typed graph settings and exports.")
        self.assertEqual(records[0]["url"], "/docs/graph/index.html#symbolica.community.graph")
        generic = html.replace("symbolica.community.graph", "reference-title")
        self.assertTrue(build.records_for_page(self.extract, generic, "graph/index.html", {}))


if __name__ == "__main__":
    unittest.main()
