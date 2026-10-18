export function compileSymbolica(url) {
  return WebAssembly.compileStreaming(fetch(url).then(response => {
    if (!response.ok) throw new Error('Cannot load Symbolica binary: HTTP ' + response.status);
    return response;
  })).then(module => ({ module }), error => ({ error }));
}

function installNativeFile(FS, path, url, size) {
  const slash = path.lastIndexOf('/');
  const node = FS.createLazyFile(path.slice(0, slash), path.slice(slash + 1), url, true, false);
  let bytes;
  const read = () => {
    if (!bytes) {
      const request = new XMLHttpRequest();
      request.open('GET', url, false);
      request.responseType = 'arraybuffer';
      request.send();
      if (request.status !== 200 || request.response?.byteLength !== size) {
        throw new Error('Cannot read Symbolica binary: HTTP ' + request.status);
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

export async function mountSymbolica(pyodide, compiled, url, native, runtimeVersion) {
  const result = await compiled;
  if (result.error) throw result.error;
  const module = pyodide._module;
  if (pyodide.version !== runtimeVersion || !module?.preloadedWasm ||
      typeof module.loadWebAssemblyModule !== 'function' ||
      typeof pyodide._api?.loadDynlib !== 'function') {
    throw new Error('Pyodide changed; review the Symbolica streaming loader');
  }
  const site = pyodide.runPython("__import__('sysconfig').get_path('platlib')").replace(/^\/+/, '/');
  const path = site + '/' + native.path;
  if (pyodide.FS.analyzePath(path).exists) {
    throw new Error('Symbolica support wheel unexpectedly contains the native binary');
  }
  module.preloadedWasm[path] = await module.loadWebAssemblyModule(
    result.module, { loadAsync: true, nodelete: true }, path, {});
  // Register before exposing the file, avoiding libc's retained native-byte copy.
  await pyodide._api.loadDynlib(path);
  installNativeFile(pyodide.FS, path, url, native.size);
  const record = site + '/' + native.record;
  pyodide.FS.writeFile(record, pyodide.FS.readFile(record, { encoding: 'utf8' }) + native.recordEntry);
}

// Shared native-loader.js is prepended at build time, without an extra request.
export async function loadGalleryPyodide(saveOnly = false) {
  const runtime = new URL("https://cdn.symbolica.io/docs/live-python/immutable/d4942fa4acf2d1c4414e/runtime/", import.meta.url).href;
  const wheel = new URL("https://cdn.symbolica.io/gallery/notebooks/immutable/18bd3278d3de3661e1a7/symbolica-3.0.2-cp314-abi3-pyemscripten_2026_0_wasm32.whl", import.meta.url).href;
  const nativeURL = new URL("https://cdn.symbolica.io/gallery/notebooks/immutable/6fec83e47543828a023e/symbolica-core.wasm", import.meta.url).href;
  const native = {"path": "symbolica/core.abi3.so", "size": 168628852, "record": "symbolica-3.0.2.dist-info/RECORD", "recordEntry": "symbolica/core.abi3.so,sha256=b-yD5HVDgooCPpd02gz5sKpExwajOaB2fybAtcg7ZiU,168628852\n"};
  const packages = [];
  const resourcePackages = ["symbolica-fonts"];
  const loaderStart = performance.now();
  const compiled = saveOnly ? null : compileSymbolica(nativeURL);
  const { loadPyodide } = await import(`${runtime}pyodide.mjs`);
  performance.measure("symbolica:loader", { start: loaderStart });
  const runtimeStart = performance.now();
  const pyodide = await loadPyodide({
    indexURL: runtime,
    stdLibURL: new URL("https://cdn.symbolica.io/docs/live-python/immutable/47ba18c65b0e98763205/optimized/python_stdlib.zip", import.meta.url).href,
    lockFileURL: new URL("../pyodide-lock.json?v=0dfb602e4944f1f4", import.meta.url).href,
    packageBaseUrl: new URL("https://cdn.symbolica.io/gallery/notebooks/", import.meta.url).href,
    packages: saveOnly ? ["marimo-base", "micropip"]
      : [wheel, ...packages, "marimo-base", "micropip", "pygments", "pyodide-http"],
    convertNullToNone: true,
  });
  performance.measure("symbolica:runtime-and-packages", { start: runtimeStart });
  if (!saveOnly) {
    const importStart = performance.now();
    await mountSymbolica(pyodide, compiled, nativeURL, native, "314.0.7");
    pyodide.runPython("import symbolica");
    // Widgets and native rendering fonts are only needed when cells execute.
    let widgets;
    pyodide._galleryEnsureWidgets = () => widgets ??= pyodide.loadPackage(["anywidget", ...resourcePackages]).catch(error => {
      widgets = undefined;
      throw error;
    });
    performance.measure("symbolica:import", { start: importStart });
    pyodide.runPython(`
import sys as _gallery_sys
import marimo._runtime.patches as _gallery_patches
_gallery_patches.patch_recursion_limit = lambda limit: _gallery_sys.setrecursionlimit(limit)
`);
  }
  return pyodide;
}
