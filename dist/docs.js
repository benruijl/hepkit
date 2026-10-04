const search = document.querySelector("#docs-search");
const results = document.querySelector("#docs-search-results");
const status = document.querySelector("#docs-search-status");
const menu = document.querySelector(".docs-menu");
if (window.matchMedia("(max-width: 900px)").matches) menu.open = false;

let index;
let requestId = 0;
search.addEventListener("input", async () => {
  const current = ++requestId;
  const query = search.value.trim().toLowerCase();
  if (!query) {
    results.hidden = true;
    menu.hidden = false;
    status.textContent = "";
    return;
  }
  try {
    status.textContent = "Searching…";
    if (!index) {
      const response = await fetch("/docs/search-index.json");
      if (!response.ok) throw new Error("Search unavailable");
      index = await response.json();
    }
    if (current !== requestId) return;
    const words = query.split(/\s+/);
    const matches = index.map(entry => {
      const title = entry.title.toLowerCase();
      const text = `${title} ${entry.group} ${entry.summary}`.toLowerCase();
      const score = title === query ? 4 : title.startsWith(query) ? 3 : title.includes(query) ? 2 : words.every(word => text.includes(word)) ? 1 : 0;
      return {entry, score};
    }).filter(match => match.score).sort((a, b) => b.score - a.score || a.entry.title.localeCompare(b.entry.title));
    results.replaceChildren();
    for (const {entry} of matches.slice(0, 25)) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      const label = document.createElement("strong");
      const group = document.createElement("span");
      link.href = entry.url;
      label.textContent = entry.title;
      group.textContent = entry.group;
      link.append(label, group);
      item.append(link);
      results.append(item);
    }
    menu.hidden = true;
    results.hidden = false;
    status.textContent = matches.length ? `${matches.length} results${matches.length > 25 ? "; showing the first 25" : ""}` : "No results. Try a class or method name.";
  } catch {
    if (current !== requestId) return;
    status.textContent = "Search is unavailable. Browse the reference below.";
    menu.hidden = false;
    results.hidden = true;
  }
});
search.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    search.value = "";
    search.dispatchEvent(new Event("input"));
  }
});

for (const block of document.querySelectorAll(".docs-content pre")) {
  const code = block.querySelector("code");
  if (!code || !navigator.clipboard) continue;
  const button = document.createElement("button");
  button.className = "copy-code";
  button.type = "button";
  button.textContent = "Copy";
  button.setAttribute("aria-label", "Copy code example");
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(code.textContent);
      button.textContent = "Copied";
    } catch { button.textContent = "Select to copy"; }
    setTimeout(() => { button.textContent = "Copy"; }, 1800);
  });
  block.parentElement.insertBefore(button, block);
}
