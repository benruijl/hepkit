// Apply before the stylesheet loads to avoid a light flash on dark pages.
(() => {
  const key = "hepkit-theme";
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  let preference;
  try {
    const saved = localStorage.getItem(key);
    if (saved === "light" || saved === "dark") preference = saved;
  } catch {
    // Storage can be unavailable in private or restricted browser contexts.
  }

  function applyTheme() {
    const theme = preference || (system.matches ? "dark" : "light");
    document.documentElement.dataset.theme = theme;
    // Marimo supports the theme query parameter in its own editor and outputs.
    for (const link of document.querySelectorAll("[data-gallery-notebook]")) {
      const url = new URL(link.href);
      url.searchParams.set("theme", preference || "system");
      link.href = url.href;
    }
    document.querySelector('meta[name="theme-color"]')?.setAttribute(
      "content", theme === "dark" ? "#111d23" : "#176f5e",
    );
    const toggle = document.querySelector("#theme-toggle");
    if (toggle) {
      toggle.setAttribute("aria-pressed", String(theme === "dark"));
      toggle.title = `Switch to ${theme === "dark" ? "light" : "dark"} mode`;
    }
  }

  applyTheme();
  system.addEventListener("change", () => {
    if (!preference) applyTheme();
  });
  window.addEventListener("storage", event => {
    if (event.key !== key && event.key !== null) return;
    preference = event.newValue === "light" || event.newValue === "dark"
      ? event.newValue : undefined;
    applyTheme();
  });
  document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.querySelector("#theme-toggle");
    if (!toggle) return;
    toggle.hidden = false;
    applyTheme();
    toggle.addEventListener("click", () => {
      preference = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      try { localStorage.setItem(key, preference); } catch { /* Keep the in-page choice. */ }
      applyTheme();
    });
  });
})();
