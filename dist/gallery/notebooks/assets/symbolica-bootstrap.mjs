// Loaded inside marimo's worker. Use the site's exact Python/Symbolica build.
// Keep the binary readable without materializing it during stat/import. Normal
// Emscripten lazy files issue a HEAD and confuse compressed Content-Length with
// the decoded size (especially with Brotli). Our build already knows the size.
function installNativeFile(FS, path, url, size) {
  const slash = path.lastIndexOf("/");
  const node = FS.createLazyFile(path.slice(0, slash), path.slice(slash + 1), url, true, false);
  let bytes;
  const read = () => {
    if (!bytes) {
      // Python file I/O is synchronous. This rare path runs only when someone
      // explicitly reads the installed binary, never for imports or stat.
      const request = new XMLHttpRequest();
      request.open("GET", url, false);
      request.responseType = "arraybuffer";
      request.send();
      if (request.status !== 200 || request.response?.byteLength !== size) {
        throw new Error(`Cannot read Symbolica binary: HTTP ${request.status}`);
      }
      bytes = new Uint8Array(request.response);
    }
    return bytes;
  };
  node.contents = { length: size, get: index => read()[index] };
  node.stream_ops.read = (stream, buffer, offset, length, position) => {
    const count = Math.max(0, Math.min(size - position, length));
    if (count) buffer.set(read().subarray(position, position + count), offset);
    return count;
  };
}

export async function loadGalleryPyodide(saveOnly = false) {
  // The build pins these to verified, content-hashed artifacts, avoiding a
  // configuration fetch on the worker's startup path.
  const runtime = new URL("https://cdn.symbolica.io/docs/live-python/immutable/d4942fa4acf2d1c4414e/runtime/", import.meta.url).href;
  const wheel = new URL("https://cdn.symbolica.io/gallery/notebooks/immutable/2d33702bc86afd1fb787/symbolica-3.0.0-cp314-abi3-pyemscripten_2026_0_wasm32.whl", import.meta.url).href;
  const nativeURL = new URL("https://cdn.symbolica.io/gallery/notebooks/immutable/29e40afcac8911634524/symbolica-core.wasm", import.meta.url).href;
  const native = {"path": "symbolica/core.abi3.so", "size": 151094788, "record": "symbolica-3.0.0.dist-info/RECORD", "recordEntry": "symbolica/core.abi3.so,sha256=KeQK_KyJEWNFJAe8JwLooC3J8DfBYFx8sJ2DQTSoAfQ,151094788\n"};
  const packages = [];
  const loaderStart = performance.now();
  // Start before importing Pyodide: transfer and streaming compilation overlap
  // interpreter/package initialization. Observe failures immediately so a fast
  // HTTP error cannot become an unhandled rejection while Python initializes.
  const compiled = saveOnly ? null : WebAssembly.compileStreaming(fetch(nativeURL).then(response => {
    if (!response.ok) throw new Error(`Cannot load Symbolica binary: HTTP ${response.status}`);
    return response;
  })).then(module => ({ module }), error => ({ error }));
  const { loadPyodide } = await import(`${runtime}pyodide.mjs`);
  performance.measure("symbolica:loader", { start: loaderStart });
  const runtimeStart = performance.now();
  const pyodide = await loadPyodide({
    indexURL: runtime,
    stdLibURL: new URL("https://cdn.symbolica.io/docs/live-python/immutable/47ba18c65b0e98763205/optimized/python_stdlib.zip", import.meta.url).href,
    lockFileURL: new URL("../pyodide-lock.json?v=9f89a53efb79bf92", import.meta.url).href,
    packageBaseUrl: new URL("https://cdn.symbolica.io/gallery/notebooks/", import.meta.url).href,
    // Fetch execution packages while Python starts; ty runs separately.
    packages: saveOnly ? ["marimo-base", "micropip"]
      : [wheel, ...packages, "marimo-base", "micropip", "pygments", "pyodide-http"],
    convertNullToNone: true,
  });
  performance.measure("symbolica:runtime-and-packages", { start: runtimeStart });
  if (!saveOnly) {
    const importStart = performance.now();
    const result = await compiled;
    if (result.error) throw result.error;
    const module = pyodide._module;
    if (pyodide.version !== "314.0.7" ||
        !module?.preloadedWasm || typeof module.loadWebAssemblyModule !== "function" ||
        typeof pyodide._api?.loadDynlib !== "function") {
      throw new Error("Pyodide changed; review the Symbolica streaming loader");
    }
    // This runtime reports //lib/...; dlopen normalizes it before cache lookup.
    const sitePackages = pyodide.runPython("__import__('sysconfig').get_path('platlib')").replace(/^\/+/, "/");
    const path = `${sitePackages}/${native.path}`;
    if (pyodide.FS.analyzePath(path).exists) {
      throw new Error("Symbolica support wheel unexpectedly contains the native binary");
    }
    module.preloadedWasm[path] = await module.loadWebAssemblyModule(
      result.module, { loadAsync: true, nodelete: true }, path, {});
    // Register with C dlopen BEFORE making the file visible. Otherwise libc
    // mallocs and retains a second 143 MiB copy for potential thread loading.
    await pyodide._api.loadDynlib(path);
    installNativeFile(pyodide.FS, path, nativeURL, native.size);
    // The small wheel has a valid RECORD of its own. Complete the installed
    // distribution's inventory now that its native file is also available.
    const record = `${sitePackages}/${native.record}`;
    pyodide.FS.writeFile(record, pyodide.FS.readFile(record, { encoding: "utf8" }) + native.recordEntry);
    pyodide.runPython(`import symbolica`);
    // The native paginated viewer needs anywidget only when cells execute.
    // Its pinned dependency graph is in the local lockfile, off the open path.
    let widgets;
    pyodide._galleryEnsureWidgets = () => widgets ??= pyodide.loadPackage("anywidget").catch(error => {
      widgets = undefined;
      throw error;
    });
    performance.measure("symbolica:import", { start: importStart });
    // marimo 0.24 imports Jedi just to undo its recursion-limit side effect.
    // The gallery uses ty, so set the limit directly without installing Jedi.
    pyodide.runPython(`
import sys as _gallery_sys
import marimo._runtime.patches as _gallery_patches
_gallery_patches.patch_recursion_limit = lambda limit: _gallery_sys.setrecursionlimit(limit)
`);
  }
  return pyodide;
}
