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
  const wheel = new URL("https://cdn.symbolica.io/gallery/notebooks/immutable/79c9bff0103a275b6d22/symbolica-3.0.10-cp314-abi3-pyemscripten_2026_0_wasm32.whl", import.meta.url).href;
  const nativeURL = new URL("https://cdn.symbolica.io/gallery/notebooks/immutable/c1db6f1ae3f1965e15e6/symbolica-core.wasm", import.meta.url).href;
  const native = {"path": "symbolica/core.abi3.so", "size": 167963221, "record": "symbolica-3.0.10.dist-info/RECORD", "recordEntry": "symbolica/core.abi3.so,sha256=wdtvGuPxll4V5qtYUpPP4HnGZuy0L7sjYU-C9g5iDMk,167963221\n"};
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
    lockFileURL: new URL("../pyodide-lock.json?v=1adc9a8317e7fb88", import.meta.url).href,
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
    // Native rendering fonts are only needed when cells execute. Optional
    // widgets remain available through Marimo's normal explicit-import loader.
    let resources;
    pyodide._galleryEnsureResources = () => resources ??= pyodide.loadPackage(resourcePackages).catch(error => {
      resources = undefined;
      throw error;
    });
    // Article demos execute during kernel initialization, before Marimo's Run
    // request hook. Their fonts must already be installed at that point.
    if (new URL(globalThis.location.href).searchParams.has('article-notebook')) {
      await pyodide._galleryEnsureResources();
    }
    const pagerGlobals = pyodide.runPython(`
import sys as _gallery_sys, types as _gallery_types
_gallery_pager = _gallery_types.ModuleType("_symbolica_gallery_pager")
_gallery_sys.modules[_gallery_pager.__name__] = _gallery_pager
_gallery_pager.__dict__
`);
    try {
      pyodide.runPython("\"\"\"Use Symbolica's standalone MathML viewer through Marimo's kernel RPC.\n\nThe formatter runs before Marimo's _display_ protocol, which otherwise imports\nanywidget. Function calls and cleanup run on the kernel's control queue, never\nby reentering Pyodide from a separate JavaScript message listener.\n\"\"\"\nimport html\nimport importlib.util\nimport json\nimport sys\nimport uuid\nfrom dataclasses import dataclass\n\nimport marimo._output.formatting as formatting\nfrom marimo._runtime.cell_lifecycle_item import CellLifecycleItem\nfrom marimo._runtime.context import safe_get_context\nfrom marimo._runtime.functions import Function\nfrom symbolica import MathMLViewer\n\n_references = {}\n_owned = set()\n_viewers = {}\n_original_get_formatter = formatting.get_formatter\n\n\n@dataclass\nclass Message:\n    message: dict\n\n\nclass Pager(CellLifecycleItem):\n    def __init__(self, viewer, owned):\n        self.viewer = viewer\n        self.owned = owned\n        self.views = set()\n        self.namespace = \"symbolica-pager-\" + uuid.uuid4().hex\n        self.context = None\n\n    def create(self, context):\n        self.context = context\n        _viewers[self.namespace] = self\n        key = id(self.viewer)\n        _references[key] = _references.get(key, 0) + 1\n        if self.owned:\n            _owned.add(key)\n        context.function_registry.register(\n            self.namespace, Function(\"message\", Message, self.message))\n\n    def message(self, args):\n        if self.viewer is None:\n            raise ValueError(\"Run this cell again to restore the expression viewer.\")\n        result = self.viewer.handle_message(args.message)\n        view = args.message.get(\"view\")\n        if isinstance(view, str):\n            if args.message.get(\"action\") == \"attach\":\n                self.views.add(view)\n            elif args.message.get(\"action\") == \"dispose\":\n                self.views.discard(view)\n        return result\n\n    def release(self, _args=None):\n        viewer, self.viewer = self.viewer, None\n        if viewer is not None:\n            # The kernel disposes old outputs before their DOM is removed, so\n            # detach here as well as in the frontend's normal close handshake.\n            for view in self.views:\n                viewer.handle_message({\"action\": \"dispose\", \"view\": view})\n            self.views.clear()\n            key = id(viewer)\n            _references[key] -= 1\n            if not _references[key]:\n                del _references[key]\n                if key in _owned:\n                    _owned.remove(key)\n                    viewer.close()\n            _viewers.pop(self.namespace, None)\n            self.context.function_registry.delete(self.namespace)\n\n    def dispose(self, context, deletion):\n        self.release()\n        return True\n\n\ndef _uses_community_pager(value):\n    # TensorExpression inherits Expression.mathml_viewer(), but its own paged()\n    # retains tensor notation. SquaredAmplitude exposes only paged(). Look up\n    # loaded modules so scalar-only notebooks do not initialize Community printers.\n    for module_name, type_name in (\n        (\"tensor\", \"TensorExpression\"), (\"tensor_native\", \"TensorExpression\"),\n        (\"hepkit\", \"SquaredAmplitude\"), (\"hepkit_native\", \"SquaredAmplitude\"),\n    ):\n        native_type = getattr(sys.modules.get(\"symbolica.community.\" + module_name), type_name, None)\n        if native_type is not None and isinstance(value, native_type):\n            return True\n    return False\n\n\ndef _format_pager(value):\n    viewer = (value if isinstance(value, MathMLViewer)\n              else value.paged() if _uses_community_pager(value)\n              else value.mathml_viewer())\n    owned = not isinstance(value, MathMLViewer)\n    pager = Pager(viewer, owned)\n    context = safe_get_context()\n    try:\n        page = viewer.page()\n        context.cell_lifecycle_registry.add(pager)\n        payload = html.escape(json.dumps({\"id\": pager.namespace, \"page\": page}), quote=True)\n        return \"text/html\", ('<div data-symbolica-pager=\"' + payload + '\"></div>')\n    except Exception:\n        if pager.context is not None:\n            pager.release()\n        elif owned and id(viewer) not in _references:\n            viewer.close()\n        raise\n\n\ndef _format_graph(value):\n    formatter = _original_get_formatter(value)\n    mime, data = formatter(value)\n    # 3.0.5's no-anywidget adapter returns interactive HTML in Marimo's React\n    # tree. Retain plain `diagram` output while isolating its SVG mutations.\n    # Upstream can wrap its iframe in a styled div while waiting for layout.\n    # Preserve that frame: nesting it would lose Marimo's resize helper.\n    if mime == \"text/html\" and \"<iframe\" not in data.lower():\n        import marimo as mo\n\n        return mo.iframe(data)._mime_()\n    return mime, data\n\n\ndef get_formatter(value, include_opinionated=None):\n    context = safe_get_context()\n    if context is not None and context.cell_id is not None and (\n        isinstance(value, MathMLViewer) or _uses_community_pager(value)\n        or callable(getattr(value, \"mathml_viewer\", None))\n    ):\n        return _format_pager\n    if (\n        context is not None\n        and context.cell_id is not None\n        and type(value).__module__ in {\n            \"symbolica.community.graph\", \"symbolica.community.hepkit\"\n        }\n        and callable(getattr(value, \"_mime_\", None))\n        and callable(getattr(value, \"to_html\", None))\n        and importlib.util.find_spec(\"anywidget\") is None\n    ):\n        return _format_graph\n    return _original_get_formatter(value, include_opinionated=include_opinionated)\n\n\ndef install():\n    formatting.get_formatter = get_formatter\n    # Capture executable code from the installed wheel before user cells run.\n    # HTML output carries only data, and can never select renderer JavaScript.\n    return MathMLViewer.javascript()\n", { globals: pagerGlobals });
      const javascript = pyodide.runPython("install()", { globals: pagerGlobals });
      globalThis.postMessage?.({ type: "gallery-pager-renderer", javascript });
    } finally {
      pagerGlobals.destroy();
    }
    performance.measure("symbolica:import", { start: importStart });
    pyodide.runPython(`
import sys as _gallery_sys
import marimo._runtime.patches as _gallery_patches
_gallery_patches.patch_recursion_limit = lambda limit: _gallery_sys.setrecursionlimit(limit)
`);
  }
  return pyodide;
}
