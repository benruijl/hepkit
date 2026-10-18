const categories = [...document.querySelectorAll(".gallery-category")];
const filters = [...document.querySelectorAll("[data-filter]")];
for (const button of filters) {
  button.addEventListener("click", () => {
    for (const filter of filters) filter.setAttribute("aria-pressed", String(filter === button));
    for (const category of categories) category.hidden = button.dataset.filter !== "all" && category.dataset.category !== button.dataset.filter;
  });
}

const localPanel = document.querySelector("#gallery-local-dialog");
const localTitle = document.querySelector("#local-title");
const localDownload = document.querySelector("#local-download");
const localCommand = document.querySelector("#local-command");
const localCopy = document.querySelector("#local-copy");
const localCopyStatus = document.querySelector("#local-copy-status");
for (const link of document.querySelectorAll(".gallery-download")) {
  const name = link.closest(".gallery-card").querySelector("h3").textContent;
  link.setAttribute("aria-haspopup", "dialog");
  link.setAttribute("aria-controls", localPanel.id);
  link.setAttribute("aria-label", `Run locally: ${name}`);
  link.title = "Download and run locally";
  link.addEventListener("click", event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const filename = new URL(link.href).pathname.split("/").pop();
    document.querySelector("#local-filename").textContent = filename;
    localDownload.href = link.href;
    localDownload.download = filename;
    localCommand.textContent = `uvx --refresh --python 3.14 --with symbolica marimo edit ${filename}`;
    localCopy.textContent = "Copy";
    localCopyStatus.textContent = "";
    localPanel.showModal();
    document.documentElement.classList.add("gallery-local-open");
    localTitle.focus({ preventScroll: true });
  });
}
document.querySelector("#local-close").addEventListener("click", () => localPanel.close());
localPanel.addEventListener("click", event => {
  if (event.target !== localPanel) return;
  const bounds = localPanel.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) localPanel.close();
});
localPanel.addEventListener("close", () => document.documentElement.classList.remove("gallery-local-open"));
localCopy.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(localCommand.textContent);
    localCopy.textContent = "Copied!";
    localCopyStatus.textContent = "Command copied. Paste it into your terminal.";
  } catch {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(localCommand);
    selection.removeAllRanges();
    selection.addRange(range);
    localCopyStatus.textContent = "Select and copy the command above, then paste it into your terminal.";
  }
});

const panel = document.querySelector("#gallery-notebook");
const frameHost = document.querySelector("#notebook-frame");
const heading = document.querySelector("#notebook-title");
const status = document.querySelector("#notebook-status");
const fullPage = document.querySelector("#notebook-full-page");
let activeLink;
// Keep only source/configuration, never iframe objects or Python results.
const drafts = new Map();
window.__symbolicaGalleryRestore = source => {
  const frame = frameHost.firstElementChild;
  return frame?.contentWindow === source ? drafts.get(frame.dataset.galleryNotebook) ?? null : null;
};

function releaseNotebook() {
  const frame = frameHost.firstElementChild;
  if (!frame) return true;
  try {
    const snapshot = frame.contentWindow.__symbolicaGallerySnapshot;
    // Before the editor mounts there can be no new edits. Keep any older draft.
    if (frame.contentDocument?.querySelector('.cm-content')) {
      if (!snapshot) throw new Error('Notebook draft adapter unavailable');
      // Serialize in the parent to avoid retaining objects from the old iframe.
      drafts.set(frame.dataset.galleryNotebook, JSON.stringify(snapshot()));
    }
    frame.remove(); // Also terminates execution, save and type-hint workers.
    return true;
  } catch (error) {
    console.error('Could not preserve notebook edits:', error);
    status.textContent = 'Could not preserve your edits. Download your notebook before leaving it.';
    return false;
  }
}

for (const link of document.querySelectorAll("[data-gallery-notebook]")) {
  link.setAttribute("aria-haspopup", "dialog");
  link.addEventListener("click", event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    let frame = frameHost.querySelector(`[data-gallery-notebook="${link.dataset.galleryNotebook}"]`);
    if (!frame) {
      if (!releaseNotebook()) return;
      frame = document.createElement("iframe");
      frame.dataset.galleryNotebook = link.dataset.galleryNotebook;
      frame.title = link.dataset.title + " — editable marimo notebook";
      frame.src = link.href;
      frame.addEventListener("load", () => {
        // Inline Linnet viewers must not resize the whole notebook iframe.
        // Nested output frames still own and resize their individual viewers.
        frame.contentDocument?.documentElement.setAttribute("data-linnet-frame-owner", "");
        frame.dataset.loaded = "true";
        if (activeLink === link) status.textContent = "";
      });
      frameHost.append(frame);
    }
    activeLink = link;
    heading.textContent = link.dataset.title;
    fullPage.href = link.href;
    status.textContent = frame.dataset.loaded ? "" : "Loading notebook…";
    if (!panel.open) panel.showModal();
    document.documentElement.classList.add("gallery-notebook-open");
    heading.focus({ preventScroll: true });
  });
}
function closeNotebook() {
  if (!releaseNotebook()) return;
  panel.close();
  document.documentElement.classList.remove("gallery-notebook-open");
  activeLink?.focus({ preventScroll: true });
}
document.querySelector("#notebook-close").addEventListener("click", closeNotebook);
panel.addEventListener("cancel", event => {
  // Escape must preserve the draft just like the Close button.
  event.preventDefault();
  closeNotebook();
});
