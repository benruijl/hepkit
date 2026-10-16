const menu = document.querySelector(".docs-menu");
if (window.matchMedia("(max-width: 900px)").matches) menu.open = false;

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
