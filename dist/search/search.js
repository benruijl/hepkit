let dialog;
let engine;
let revision = 0;
let timer;
let previousFocus;
let previousOverflow;
let engineAttempt = 0;
let vocabulary;
let spelling;
let spellingAttempt = 0;
let followingResult = false;
let autocomplete;
let autocompleteAttempt = 0;
let completeAPI;
let completedQuery;
let searchStyles;

function loadSearchStyles() {
  if (searchStyles) return searchStyles;
  let link = [...document.querySelectorAll('link[rel="stylesheet"]')].find(node => {
    const url = new URL(node.href, location.href);
    return url.pathname === "/search/search.css" && [location.origin, "https://cdn.symbolica.io"].includes(url.origin);
  });
  if (link?.sheet && new URL(link.href).origin === location.origin) return Promise.resolve();
  searchStyles = new Promise((resolve, reject) => {
    if (!link) link = document.createElement("link");
    link.rel = "stylesheet";
    link.addEventListener("load", resolve, { once: true });
    link.addEventListener("error", () => { searchStyles = undefined; reject(new Error("Search styles unavailable")); }, { once: true });
    link.href = "/search/search.css";
    if (!link.isConnected) document.head.append(link);
  });
  return searchStyles;
}

loadSearchStyles().catch(() => {});

const categories = ["Guides", "Python API", "Website"];

const tools = document.querySelector(".site-nav");
if (tools) {
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "site-search-trigger";
  trigger.dataset.siteSearch = "";
  trigger.title = "Search";
  trigger.setAttribute("aria-label", "Search");
  trigger.innerHTML = '<i class="bi bi-search" aria-hidden="true"></i>';
  tools.insertBefore(trigger, tools.querySelector("#theme-toggle"));
}

function createDialog() {
  dialog = document.createElement("dialog");
  dialog.id = "site-search";
  dialog.setAttribute("aria-label", "Search HEPkit");
  dialog.innerHTML = `
    <div class="site-search-panel">
      <form class="site-search-bar" role="search">
        <i class="bi bi-search" aria-hidden="true"></i>
        <input id="site-search-input" type="search" placeholder="Search documentation" aria-label="Search documentation" autocomplete="off" spellcheck="false">
        <button type="button" class="site-search-clear" aria-label="Clear search" title="Clear search" disabled><i class="bi bi-x-circle" aria-hidden="true"></i></button>
        <button type="button" class="site-search-close" aria-label="Close search" title="Close search"><i class="bi bi-x-lg" aria-hidden="true"></i></button>
      </form>
      <ul id="site-search-autocomplete" class="site-search-autocomplete" aria-label="API suggestions" hidden></ul>
      <div class="site-search-options">
        <p class="site-search-status" role="status" aria-live="polite"></p>
        <div class="site-search-suggestions" role="group" aria-label="Spelling suggestions" aria-live="polite" hidden></div>
        <nav class="site-search-jumps" aria-label="Result sections"></nav>
      </div>
      <ol class="site-search-results" aria-label="Search results"></ol>
    </div>`;
  dialog.querySelector("form").addEventListener("submit", event => {
    event.preventDefault();
    if (dialog.querySelector(".site-search-results").dataset.query !== dialog.querySelector("input").value) {
      search();
      return;
    }
    visibleLinks()[0]?.click();
  });
  dialog.querySelector(".site-search-close").addEventListener("click", () => dialog.close());
  dialog.querySelector(".site-search-clear").addEventListener("click", () => {
    const input = dialog.querySelector("input");
    input.value = "";
    search();
    input.focus();
  });
  dialog.querySelector("input").addEventListener("input", () => {
    dialog.querySelector(".site-search-clear").disabled = !dialog.querySelector("input").value;
    ++revision;
    clearSuggestions();
    completedQuery = undefined;
    updateAutocomplete();
    clearTimeout(timer);
    timer = setTimeout(search, 120);
  });
  dialog.addEventListener("click", event => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", () => {
    ++revision;
    clearTimeout(timer);
    clearAutocomplete();
    document.body.style.overflow = previousOverflow;
    if (!followingResult) previousFocus?.focus();
  });
  dialog.addEventListener("keydown", event => {
    if (event.isComposing) return;
    if (event.key === "Escape") {
      event.preventDefault();
      dialog.close();
      return;
    }
    const completions = [...dialog.querySelectorAll(".site-search-autocomplete button")];
    if (event.key === "Tab" && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey && completions.length &&
        (event.target === dialog.querySelector("input") || completions.includes(event.target))) {
      event.preventDefault();
      (completions.includes(event.target) ? event.target : completions[0]).click();
      return;
    }
    const links = [...dialog.querySelectorAll(".site-search-autocomplete button, .site-search-suggestions button, .site-search-result-link")].filter(link => !link.closest("[hidden]"));
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!links.length) return;
      event.preventDefault();
      const current = links.indexOf(document.activeElement);
      const next = event.key === "ArrowDown" ? current + 1 : current - 1;
      if (next < 0) dialog.querySelector("input").focus();
      else {
        const link = links[Math.min(next, links.length - 1)];
        link.focus({ preventScroll: true });
        const results = dialog.querySelector(".site-search-results");
        const viewport = results.getBoundingClientRect();
        const bounds = link.getBoundingClientRect();
        if (results.contains(link)) {
          if (bounds.top < viewport.top + 40) results.scrollTop += bounds.top - viewport.top - 40;
          else if (bounds.bottom > viewport.bottom) results.scrollTop += bounds.bottom - viewport.bottom;
        }
      }
    }
  });
  document.body.append(dialog);
}

function visibleLinks() {
  return [...dialog.querySelectorAll(".site-search-result-link")].filter(link => !link.closest("[hidden]"));
}

function status(text) {
  dialog.querySelector(".site-search-status").textContent = text;
}

function clearAutocomplete() {
  const list = dialog.querySelector(".site-search-autocomplete");
  list.hidden = true;
  list.replaceChildren();
  delete list.dataset.query;
  dialog.querySelector("input").removeAttribute("aria-controls");
}

function updateAutocomplete() {
  const input = dialog.querySelector("input");
  const list = dialog.querySelector(".site-search-autocomplete");
  if (list.dataset.query === input.value && completedQuery !== input.value) return;
  clearAutocomplete();
  if (!completeAPI || !dialog.open || completedQuery === input.value) return;
  const candidates = completeAPI(input.value);
  if (!candidates.length) return;
  list.dataset.query = input.value;
  for (const candidate of candidates) {
    const row = element("li", "", "");
    const button = element("button", "", "");
    button.type = "button";
    button.setAttribute("aria-label", `Search for ${candidate}`);
    const icon = element("i", "bi bi-code", "");
    icon.setAttribute("aria-hidden", "true");
    button.append(icon, element("code", "", candidate));
    button.addEventListener("click", () => {
      input.value = candidate;
      completedQuery = candidate;
      clearAutocomplete();
      input.focus();
      search();
    });
    row.append(button);
    list.append(row);
  }
  list.hidden = false;
  input.setAttribute("aria-controls", list.id);
}

async function loadAutocomplete() {
  if (!autocomplete) {
    const retry = autocompleteAttempt ? `?retry=${autocompleteAttempt}` : "";
    autocomplete = import(`/search/pagefind/autocomplete.js${retry}`).then(module => {
      completeAPI = module.autocomplete;
      updateAutocomplete();
    }).catch(() => { autocomplete = undefined; ++autocompleteAttempt; });
  }
  return autocomplete;
}

async function loadEngine() {
  if (!engine) {
    const retry = engineAttempt ? `?retry=${engineAttempt}` : "";
    engine = import(`/search/pagefind/pagefind.js${retry}`).then(async pagefind => {
      const response = await fetch("/search/pagefind/terms.json");
      if (!response.ok) throw new Error("Missing search vocabulary");
      vocabulary = await response.json();
      await pagefind.options({ baseUrl: "/", ranking: { metaWeights: { title: 12, symbol: 10 }, termSimilarity: 2 } });
      await pagefind.init();
      return pagefind;
    }).catch(error => {
      engine = undefined;
      ++engineAttempt;
      throw error;
    });
  }
  return engine;
}

function knownPrefix(term) {
  let low = 0;
  let high = vocabulary.length;
  while (low < high) {
    const middle = (low + high) >>> 1;
    if (vocabulary[middle] < term) low = middle + 1;
    else high = middle;
  }
  return vocabulary[low]?.startsWith(term);
}

function plausibleQuery(query) {
  // Pagefind also matches shorter indexed prefixes (e.g. "z" for a long unknown
  // word). Reject those false positives without downloading unrelated fragments.
  const terms = query.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "").match(/[\p{L}\p{N}_]+(?:\.[\p{L}\p{N}_]+)*/gu) || [];
  return terms.every(knownTerm);
}

function knownTerm(term) {
  return term.length < 2 || knownPrefix(term) ||
    ["ing", "ed", "es", "s"].some(ending => term.endsWith(ending) && term.length - ending.length >= 3 && knownPrefix(term.slice(0, -ending.length)));
}

function clearSuggestions() {
  const container = dialog.querySelector(".site-search-suggestions");
  container.hidden = true;
  container.replaceChildren();
}

async function suggestSpelling(query, pagefind, current) {
  const words = query.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "").match(/[\p{L}\p{N}_]+/gu) || [];
  if (query.length > 256 || words.length > 12 || !words.some(word => /^[\p{L}_]{4,48}$/u.test(word) && !knownTerm(word))) return;
  try {
    if (!spelling) {
      const retry = spellingAttempt ? `?retry=${spellingAttempt}` : "";
      spelling = Promise.all([
        import(`/search/pagefind/spelling.js${retry}`),
        fetch("/search/pagefind/spelling.json").then(response => {
          if (!response.ok) throw new Error("Missing spelling dictionary");
          return response.json();
        }),
      ]).then(([module, entries]) => module.createSpelling(entries, module.spellingDistance, knownTerm))
        .catch(error => { spelling = undefined; ++spellingAttempt; throw error; });
    }
    const suggest = await spelling;
    if (current !== revision || !dialog.open) return;
    const candidates = suggest(query);
    const suggestions = [];
    for (const candidate of candidates) {
      const normalized = candidate.trim().replace(/\(\)$/, "").replace(/::/g, ".");
      if (!plausibleQuery(normalized)) continue;
      // Verify lightweight search handles only; no result fragments are needed
      // until the user explicitly accepts a corrected query.
      const response = await pagefind.search(normalized);
      if (current !== revision || !dialog.open) return;
      if (response.results.length) suggestions.push(candidate);
      if (suggestions.length === 3) break;
    }
    if (!suggestions.length) return;
    const container = dialog.querySelector(".site-search-suggestions");
    container.append(element("span", "", "Did you mean:"));
    for (const candidate of suggestions) {
      const button = element("button", "site-search-suggestion", candidate);
      button.type = "button";
      button.setAttribute("aria-label", `Search for ${candidate}`);
      button.addEventListener("click", () => {
        const input = dialog.querySelector("input");
        input.value = candidate;
        input.focus();
        search();
      });
      container.append(button);
    }
    container.hidden = false;
  } catch {
    // Spelling is optional; an unavailable helper must not break normal search.
  }
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = text;
  return node;
}

function formatted(html) {
  const fragment = document.createDocumentFragment();
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const allowed = new Set(["CODE", "STRONG", "EM", "B", "I", "SUB", "SUP", "BR", "MARK"]);
  const syntax = new Set("al an at bn bu cf ch cn co cv do dt dv er ex fl fu im in kw op ot pp sc ss st va vs wa".split(" "));
  const mathTags = new Set("math semantics mrow mi mn mo mtext mspace mfrac msqrt mroot msub msup msubsup mover munder munderover mstyle mpadded mphantom menclose mtable mtr mtd mmultiscripts mprescripts none".split(" "));
  const mathAttrs = new Set("display mathvariant stretchy fence separator symmetric largeop movablelimits accent accentunder displaystyle scriptlevel lspace rspace width height depth linethickness columnalign rowalign columnspacing rowspacing columnlines rowlines columnspan rowspan minsize maxsize notation".split(" "));
  const mathNamespace = "http://www.w3.org/1998/Math/MathML";
  // Never copy source attributes, links, images, or executable elements.
  function copy(node, parent) {
    for (const child of node.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) parent.append(document.createTextNode(child.textContent));
      else if (["SCRIPT", "STYLE", "IFRAME", "OBJECT", "SVG"].includes(child.nodeName)) continue;
      else if (child.namespaceURI === mathNamespace) {
        if (!mathTags.has(child.localName)) continue;
        const safe = document.createElementNS(mathNamespace, child.localName);
        for (const attr of child.attributes) {
          if (mathAttrs.has(attr.name) && /^[a-zA-Z0-9 .,+%\-]*$/.test(attr.value)) safe.setAttribute(attr.name, attr.value);
        }
        copy(child, safe);
        if (child.localName === "math") {
          const box = element("span", "site-search-math", "");
          box.append(safe);
          parent.append(box);
        } else parent.append(safe);
      } else if (child.nodeName === "SPAN" && child.closest("code")) {
        const classes = [...child.classList].filter(value => syntax.has(value));
        if (classes.length) {
          const safe = element("span", classes.join(" "), "");
          copy(child, safe);
          parent.append(safe);
        } else copy(child, parent);
      }
      else if (allowed.has(child.nodeName)) {
        const safe = document.createElement(child.nodeName.toLowerCase());
        copy(child, safe);
        parent.append(safe);
      } else copy(child, parent);
    }
  }
  copy(parsed.body, fragment);
  return fragment;
}

function queryTerms(query) {
  return [...new Set(query.toLowerCase().match(/[\p{L}\p{N}_]+/gu) || [])];
}

function termPattern(terms) {
  return new RegExp(`(?<![\\p{L}\\p{N}_])(?:${terms.map(term => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).sort((a, b) => b.length - a.length).join("|")})[\\p{L}\\p{N}_]*`, "giu");
}

function passageScore(text, terms, query) {
  const lower = text.toLowerCase();
  return terms.filter(term => termPattern([term]).test(lower)).length * 20 + (lower.includes(query.toLowerCase()) ? 30 : 0);
}

function preview(passage, terms, limit = 500) {
  let fragment = formatted(passage.html);
  const text = fragment.textContent;
  let start = 0;
  let end = text.length;
  const first = terms.length ? text.search(termPattern(terms)) : -1;
  if (passage.kind === "code") {
    const lines = text.split("\n");
    const line = first < 0 ? 0 : text.slice(0, first).split("\n").length - 1;
    const from = Math.max(0, line - 1);
    start = lines.slice(0, from).join("\n").length + (from ? 1 : 0);
    end = start + lines.slice(from, from + 5).join("\n").length;
  } else if (text.length > limit) {
    start = Math.max(0, first - 140);
    if (start) {
      const sentence = text.lastIndexOf(". ", first);
      start = sentence >= start ? sentence + 2 : text.indexOf(" ", start) + 1;
    }
    end = Math.min(text.length, start + limit);
    if (end < text.length) end = text.lastIndexOf(" ", end);
  }
  if (start || end < text.length) {
    const walker = document.createTreeWalker(fragment, NodeFilter.SHOW_TEXT);
    const range = document.createRange();
    let offset = 0;
    let node;
    while ((node = walker.nextNode())) {
      const next = offset + node.textContent.length;
      if (offset <= start && start < next) range.setStart(node, start - offset);
      if (offset < end && end <= next) {
        range.setEnd(node, end - offset);
        break;
      }
      offset = next;
    }
    // A preview may trim prose, never half of a formula or its layout tree.
    const startMath = range.startContainer.parentElement?.closest(".site-search-math");
    const endMath = range.endContainer.parentElement?.closest(".site-search-math");
    if (startMath) range.setStartBefore(startMath);
    if (endMath) range.setEndAfter(endMath);
    fragment = range.cloneContents();
    if (start) fragment.prepend(document.createTextNode("..." + (passage.kind === "code" ? "\n" : " ")));
    if (end < text.length) fragment.append(document.createTextNode(passage.kind === "code" ? "\n..." : "..."));
  }
  if (terms.length) {
    const walker = document.createTreeWalker(fragment, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      if (node.parentElement?.closest("math")) continue;
      const replacement = document.createDocumentFragment();
      let offset = 0;
      for (const match of node.textContent.matchAll(termPattern(terms))) {
        replacement.append(document.createTextNode(node.textContent.slice(offset, match.index)));
        replacement.append(element("mark", "", match[0]));
        offset = match.index + match[0].length;
      }
      replacement.append(document.createTextNode(node.textContent.slice(offset)));
      node.replaceWith(replacement);
    }
  }
  return fragment;
}

function matchingPassage(data, query) {
  let passages;
  try { passages = JSON.parse(data.meta.passages || "[]"); } catch { passages = []; }
  const terms = queryTerms(query);
  if (data.meta.symbol?.toLowerCase().includes(query) || exactName(data, query)) {
    return passages.find(passage => passage.kind === "prose" && !passage.label) || passages[0];
  }
  return passages.map(passage => ({ passage, score: passageScore(formatted(passage.html).textContent, terms, query) - (passage.kind === "code" ? 1 : 0) }))
    .sort((a, b) => b.score - a.score)[0]?.passage;
}

function exactName(data, query) {
  return [data.meta.title, data.meta.symbol, data.meta.symbol?.split(".").at(-1)]
    .some(name => name?.toLowerCase() === query);
}

function resultLink(href, className) {
  const link = document.createElement("a");
  const url = new URL(href, location.origin);
  if (url.origin !== location.origin || !url.pathname.startsWith("/")) return null;
  link.className = className;
  link.href = url.pathname + url.search + url.hash;
  link.addEventListener("click", event => {
    if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && event.button === 0) {
      followingResult = true;
      dialog.close();
      document.dispatchEvent(new CustomEvent("symbolica-search-navigate", { detail: { url: link.href } }));
    }
  });
  return link;
}

function showResult(data, query) {
  const row = document.createElement("li");
  const passage = matchingPassage(data, query);
  const href = passage?.anchor ? `${data.meta.page_url}#${passage.anchor}` : data.url;
  const link = resultLink(href, "site-search-result-link");
  if (!link) return row;
  const meta = data.meta;
  row.dataset.overview = String(passage?.html === meta.page_summary_html);
  const title = meta.symbol ? meta.title.replace(new RegExp(`^${meta.page_title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\.`), "") : meta.heading;
  const breadcrumb = element("span", "site-search-breadcrumb", "");
  breadcrumb.append(element("span", meta.symbol ? "site-search-title site-search-symbol" : "site-search-title", title && title !== meta.page_title ? title : "Overview"));
  if (passage?.label) {
    const arrow = element("i", "bi bi-chevron-right", "");
    arrow.setAttribute("aria-hidden", "true");
    breadcrumb.append(arrow, element("span", "site-search-location", passage.label));
  }
  link.setAttribute("aria-label", [meta.title, passage?.label].filter(Boolean).join(" / "));
  link.append(breadcrumb);
  const description = element(passage?.kind === "code" ? "pre" : "span", "site-search-description", "");
  if (passage) {
    const fragment = preview(passage, queryTerms(query));
    if (passage.kind === "code") {
      const code = element("code", "sourceCode", "");
      for (const child of [...fragment.childNodes]) {
        if (child.nodeName === "CODE") code.append(...child.childNodes);
        else code.append(child);
      }
      description.append(code);
    } else description.append(fragment);
  }
  else description.textContent = meta.summary || "";
  if (description.textContent) link.append(description);
  row.append(link);
  return row;
}

function resultGroup(data) {
  const meta = data.meta;
  const row = element("li", "site-search-group", "");
  const header = element("div", "site-search-group-header", "");
  if (meta.module) header.append(element("span", "site-search-context", meta.module));
  const heading = element("h3", "site-search-page-title", "");
  const link = resultLink(meta.page_url || data.url.split("#")[0], "site-search-page-link");
  if (link) {
    link.textContent = meta.page_title || meta.title;
    if (meta.symbol) link.classList.add("site-search-symbol");
    heading.append(link);
  }
  header.append(heading);
  if (meta.page_summary_html || meta.page_summary) {
    const summary = element("p", "site-search-page-summary", "");
    if (meta.page_summary_html) summary.append(preview({ html: meta.page_summary_html, kind: "prose" }, [], 260));
    else summary.textContent = meta.page_summary;
    header.append(summary);
  }
  const children = element("ol", "site-search-members", "");
  children.setAttribute("aria-label", `Matches in ${meta.page_title || meta.title}`);
  children.id = `site-search-members-${revision}-${data.meta.page_url}`.replace(/[^a-zA-Z0-9_-]/g, "-");
  const toggle = element("button", "site-search-expand", "");
  toggle.type = "button";
  toggle.setAttribute("aria-controls", children.id);
  const toggleIcon = element("i", "bi bi-plus-lg", "");
  toggleIcon.setAttribute("aria-hidden", "true");
  const toggleLabel = element("span", "", "");
  toggle.append(toggleIcon, toggleLabel);
  let expanded = false;
  function update() {
    [...children.children].forEach((child, index) => { child.hidden = !expanded && index >= 3; });
    const summary = header.querySelector(".site-search-page-summary");
    if (summary) summary.hidden = [...children.children].some(child => !child.hidden && child.dataset.overview === "true");
    toggle.hidden = children.children.length <= 3;
    toggle.setAttribute("aria-expanded", String(expanded));
    toggleIcon.className = expanded ? "bi bi-dash-lg" : "bi bi-plus-lg";
    toggleLabel.textContent = expanded ? "Show fewer matches" : `Show ${Math.max(0, children.children.length - 3)} more matches in ${meta.page_title}`;
  }
  toggle.addEventListener("click", () => {
    expanded = !expanded;
    update();
    if (!expanded) {
      const results = dialog.querySelector(".site-search-results");
      results.scrollTop += row.getBoundingClientRect().top - results.getBoundingClientRect().top - 40;
      children.querySelector("a")?.focus({ preventScroll: true });
    }
  });
  row.append(header, children, toggle);
  update();
  return { row, children, update };
}

async function search() {
  clearTimeout(timer);
  const current = ++revision;
  const input = dialog.querySelector("input");
  dialog.querySelector(".site-search-clear").disabled = !input.value;
  updateAutocomplete();
  const query = input.value.trim().replace(/\(\)$/, "").replace(/::/g, ".");
  const results = dialog.querySelector(".site-search-results");
  const jumps = dialog.querySelector(".site-search-jumps");
  clearSuggestions();
  jumps.replaceChildren();
  results.replaceChildren();
  delete results.dataset.query;
  if (!query) {
    status("");
    return;
  }
  status("Searching...");
  results.setAttribute("aria-busy", "true");
  try {
    const pagefind = await loadEngine();
    if (current !== revision || !dialog.open) return;
    if (!plausibleQuery(query)) {
      status("No results. Try another search term.");
      await suggestSpelling(input.value.trim(), pagefind, current);
      if (current !== revision || !dialog.open) return;
      results.dataset.query = input.value;
      return;
    }
    // Filtered searches return lightweight result handles. Establish category
    // precedence before pagination without downloading every matching fragment.
    const [responses, named] = await Promise.all([
      Promise.all(categories.map(section => pagefind.search(query, { filters: { section } }))),
      /\s/.test(query) ? null : pagefind.search(query, { filters: { section: "Python API", api_name: query } }),
    ]);
    if (named?.results.length) {
      const api = responses[categories.indexOf("Python API")];
      const ids = new Set(named.results.map(result => result.id));
      api.results = [...named.results, ...api.results.filter(result => !ids.has(result.id))];
    }
    if (current !== revision || !dialog.open) return;
    const total = responses.reduce((count, response) => count + response.results.length, 0);
    const normalized = query.toLowerCase();
    const groups = new Map();
    const initial = [];
    const failures = new Set();
    for (const [index, response] of responses.entries()) {
      if (!response.results.length) continue;
      const section = categories[index];
      const container = element("li", "site-search-section", "");
      const heading = element("h2", "site-search-section-title", section);
      heading.id = `site-search-section-${index}`;
      heading.tabIndex = -1;
      const list = element("ol", "site-search-pages", "");
      list.setAttribute("aria-label", `${section} results`);
      const more = element("button", "site-search-more", "");
      more.type = "button";
      more.hidden = true;
      const moreIcon = element("i", "bi bi-plus-lg", "");
      moreIcon.setAttribute("aria-hidden", "true");
      const moreText = element("span", "", "");
      const moreLabel = element("span", "", "");
      const moreCount = element("span", "site-search-more-count", "");
      moreText.append(moreLabel, document.createTextNode(" "), moreCount);
      more.append(moreIcon, moreText);
      container.append(heading, list, more);
      results.append(container);
      const jump = element("a", "", "");
      jump.href = `#${heading.id}`;
      jump.append(document.createTextNode(section + " "), element("span", "site-search-count", response.results.length.toLocaleString()));
      jumps.append(jump);
      let offset = 0;
      let loading;
      function updateMore(failed = false) {
        const remaining = response.results.length - offset;
        more.hidden = !remaining;
        moreLabel.textContent = failed ? `Retry loading ${section} matches` : `Load more ${section} matches`;
        moreCount.textContent = `(${remaining.toLocaleString()} remaining)`;
      }
      async function append(count = 9) {
        if (loading) return loading;
        more.disabled = true;
        more.setAttribute("aria-busy", "true");
        moreLabel.textContent = `Loading more ${section} matches...`;
        loading = (async () => {
          try {
            const batch = await Promise.all(response.results.slice(offset, offset + count).map(result => result.data()));
            if (current !== revision || !dialog.open) return;
            batch.sort((a, b) => Number(exactName(b, normalized)) - Number(exactName(a, normalized)));
            for (const data of batch) {
              const key = data.meta.page_url || data.url.split("#")[0];
              let group = groups.get(key);
              if (!group) {
                group = resultGroup(data);
                groups.set(key, group);
                list.append(group.row);
              }
              group.children.append(showResult(data, normalized));
              group.update();
            }
            offset += batch.length;
            failures.delete(section);
            updateMore();
            if (!failures.size) status(`${total.toLocaleString()} ${total === 1 ? "result" : "results"}`);
          } catch {
            if (current === revision) {
              failures.add(section);
              updateMore(true);
              status("Could not load results. Try again.");
            }
          } finally {
            more.disabled = false;
            more.removeAttribute("aria-busy");
            loading = undefined;
          }
        })();
        return loading;
      }
      jump.addEventListener("click", async event => {
        event.preventDefault();
        if (!offset) await append(3);
        if (current !== revision || !dialog.open) return;
        results.scrollTop += container.getBoundingClientRect().top - results.getBoundingClientRect().top;
        heading.focus({ preventScroll: true });
      });
      more.addEventListener("click", () => append());
      initial.push(append(3));
    }
    await Promise.all(initial);
    if (current !== revision || !dialog.open) return;
    if (!failures.size) status(total ? `${total.toLocaleString()} ${total === 1 ? "result" : "results"}` : "No results. Try another search term.");
    if (!total) await suggestSpelling(input.value.trim(), pagefind, current);
    if (current !== revision || !dialog.open) return;
    results.dataset.query = input.value;
  } catch (error) {
    if (current === revision && dialog.open) status("Search is unavailable. Edit your query to retry.");
  } finally {
    if (current === revision) results.removeAttribute("aria-busy");
  }
}

async function openSearch() {
  try {
    await loadSearchStyles();
  } catch {
    document.querySelector(".site-search-trigger")?.setAttribute("title", "Search could not load. Try again.");
    return;
  }
  document.querySelector(".site-search-trigger")?.setAttribute("title", "Search");
  if (!dialog) createDialog();
  if (dialog.open) return;
  previousFocus = document.activeElement;
  followingResult = false;
  previousOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  dialog.showModal();
  dialog.querySelector("input").focus();
  loadAutocomplete();
  updateAutocomplete();
  loadEngine().catch(() => status("Search is unavailable. Enter a query to retry."));
  if (dialog.querySelector("input").value) search();
}

document.addEventListener("click", event => {
  if (event.target.closest('a[href$="#site-search"], [data-site-search]')) {
    event.preventDefault();
    openSearch();
  }
});

document.addEventListener("keydown", event => {
  const typing = event.target.closest("input, textarea, select, [contenteditable]:not([contenteditable=false])");
  if ((event.key.toLowerCase() === "k" && (event.ctrlKey || event.metaKey)) ||
      (event.key === "/" && !typing && !event.ctrlKey && !event.metaKey && !event.altKey)) {
    event.preventDefault();
    openSearch();
  }
});
