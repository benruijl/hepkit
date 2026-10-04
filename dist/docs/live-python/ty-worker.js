// loading-status.js
function watchDownloads(workerUrl, assets, onDownload, fetchAsset = globalThis.fetch) {
  const worker = new URL(workerUrl);
  if (!/^https?:$/.test(worker.protocol)) return () => {
  };
  const controller = new AbortController();
  let active = true;
  const missing = /* @__PURE__ */ new Set();
  const timer = setTimeout(() => stop(), 1500);
  function stop() {
    active = false;
    clearTimeout(timer);
    controller.abort();
  }
  async function cached(url) {
    const response = await fetchAsset(url, {
      cache: "only-if-cached",
      mode: "same-origin",
      signal: controller.signal
    });
    await response.body?.cancel();
    return response.ok ? true : response.status === 504 ? false : null;
  }
  (async () => {
    if (await cached(worker.href) !== true || !active) return;
    await Promise.all(assets.map(async ([name, value]) => {
      const url = new URL(value, worker);
      if (url.origin !== worker.origin) return;
      let found;
      try {
        found = await cached(url.href);
      } catch (error) {
        if (error.name !== "TypeError") return;
        found = false;
      }
      if (active && found === false && !missing.has(name)) {
        missing.add(name);
        onDownload([...missing]);
      }
    }));
  })().catch(() => {
  }).finally(() => clearTimeout(timer));
  return stop;
}

// ty-worker.js
var workspace;
var document;
var initialized;
var Position;
async function initialize(config) {
  postMessage({ type: "status", text: "Loading ty type hints\u2026" });
  const stopWatching = watchDownloads(import.meta.url, [
    ["type hints", config.tyModule],
    ["type hints", config.typeWasm],
    ["type hints", config.typeStubs]
  ], () => postMessage({ type: "status", text: "Downloading ty type hints\u2026" }));
  let Workspace, PositionEncoding, version, files;
  try {
    const [module, response, stubs] = await Promise.all([
      import(new URL(config.tyModule, import.meta.url).href),
      fetch(new URL(config.typeWasm, import.meta.url)),
      fetch(new URL(config.typeStubs, import.meta.url)).then(async (response2) => {
        if (!response2.ok) throw new Error(`Could not load type information (HTTP ${response2.status})`);
        return (await response2.json()).files;
      })
    ]);
    if (!response.ok) throw new Error(`Could not load ty (HTTP ${response.status})`);
    ({ Workspace, PositionEncoding, version } = module);
    Position = module.Position;
    files = stubs;
    await module.default({ module_or_path: response });
  } finally {
    stopWatching();
  }
  postMessage({ type: "status", text: "Preparing Symbolica hover information and completions\u2026" });
  workspace = new Workspace("/project", PositionEncoding.Utf16, { environment: { "python-version": "3.14" } });
  for (const [path, contents] of Object.entries(files)) {
    workspace.openFile(`/project/${path}`, contents).free();
  }
  document = workspace.openFile("/project/playground.py", "");
  postMessage({ type: "ready", version: version() });
}
self.onmessage = async ({ data }) => {
  if (data.type === "init") {
    initialized = initialize(data.config);
    initialized.catch((error) => postMessage({ type: "error", message: String(error) }));
    return;
  }
  if (!["hover", "complete", "signature"].includes(data.type)) return;
  try {
    await initialized;
    workspace.updateFile(document, data.source);
    if (data.type === "signature") {
      const result2 = workspace.signatureHelp(document, new Position(data.line, data.column));
      if (!result2) {
        postMessage({ type: "signature", id: data.id, signature: null });
        return;
      }
      const signatures = result2.signatures;
      try {
        const selected = signatures[result2.active_signature ?? 0];
        const parameters = selected?.parameters ?? [];
        try {
          postMessage({ type: "signature", id: data.id, signature: selected ? {
            label: selected.label,
            documentation: selected.documentation,
            activeParameter: selected.active_parameter,
            parameters: parameters.map((p) => ({ label: p.label, documentation: p.documentation }))
          } : null });
        } finally {
          for (const parameter of parameters) parameter.free();
        }
      } finally {
        for (const signature of signatures) signature.free();
        result2.free();
      }
      return;
    }
    if (data.type === "complete") {
      const results = workspace.completions(document, new Position(data.line, data.column));
      const completions = [];
      try {
        for (const item of results) {
          const edits = item.additional_text_edits;
          if (edits) {
            for (const edit of edits) edit.free();
            if (edits.length) continue;
          }
          completions.push({
            label: item.name,
            kind: item.kind,
            insertText: item.insert_text,
            detail: item.detail,
            documentation: item.documentation
          });
        }
        postMessage({ type: "complete", id: data.id, completions });
      } finally {
        for (const item of results) item.free();
      }
      return;
    }
    const result = workspace.hover(document, new Position(data.line, data.column));
    if (!result) {
      postMessage({ type: "hover", id: data.id, hover: null });
      return;
    }
    const range = result.range;
    const start = range.start;
    const end = range.end;
    try {
      postMessage({ type: "hover", id: data.id, hover: {
        markdown: result.markdown,
        start: { line: start.line, column: start.column },
        end: { line: end.line, column: end.column }
      } });
    } finally {
      start.free();
      end.free();
      range.free();
      result.free();
    }
  } catch (error) {
    postMessage({ type: "error", id: data.id, message: String(error) });
  }
};
