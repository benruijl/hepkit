import { parseFragment, serialize } from "parse5";
import katex from "katex";

const text = node => node.nodeName === "#text" ? node.value : (node.childNodes || []).map(text).join("");

function removeAnnotations(node) {
  if (node.childNodes) {
    node.childNodes = node.childNodes.filter(child => !["annotation", "annotation-xml"].includes(child.tagName));
    node.childNodes.forEach(removeAnnotations);
  }
}

function findMath(node) {
  if (node.tagName === "math") return node;
  return node.childNodes?.map(findMath).find(Boolean);
}

export function renderPreview(html) {
  const fragment = parseFragment(html);
  function visit(parent) {
    parent.childNodes = parent.childNodes.map(node => {
      if (node.tagName === "span" && node.attrs?.some(attr => attr.name === "class" && attr.value.split(/\s+/).includes("math"))) {
        let source = text(node).trim();
        for (const [open, close] of [["\\(", "\\)"], ["\\[", "\\]"], ["$$", "$$"], ["$", "$"]]) {
          if (source.startsWith(open) && source.endsWith(close)) {
            source = source.slice(open.length, -close.length);
            break;
          }
        }
        try {
          const rendered = katex.renderToString(source, {
            output: "mathml", displayMode: false, throwOnError: true,
            trust: false, strict: "ignore", maxExpand: 200, maxSize: 6,
          });
          const math = findMath(parseFragment(rendered));
          removeAnnotations(math);
          math.parentNode = parent;
          return math;
        } catch {
          // Unsupported notation stays readable; it must not break the index.
          node.tagName = node.nodeName = "code";
          node.attrs = [];
        }
      }
      if (node.childNodes) visit(node);
      return node;
    });
  }
  visit(fragment);
  return serialize(fragment);
}
