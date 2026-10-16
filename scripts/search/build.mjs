import { readFile, writeFile, mkdir, rename, rm } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { createRequire } from "node:module";
import * as pagefind from "pagefind";
import { renderPreview } from "./preview.mjs";

const [source, destination] = process.argv.slice(2);
if (!source || !destination) throw new Error("Usage: node build.mjs records.json output-directory");
const records = JSON.parse(await readFile(source, "utf8"));
const previews = new Map();
const render = html => {
  if (!previews.has(html)) previews.set(html, renderPreview(html));
  return previews.get(html);
};
for (const record of records) {
  record.meta.page_summary_html = render(record.meta.page_summary_html || "");
  const passages = JSON.parse(record.meta.passages || "[]");
  for (const passage of passages) passage.html = render(passage.html);
  record.meta.passages = JSON.stringify(passages);
}
const require = createRequire(import.meta.url);
const target = resolve(destination);
const temporary = `${target}.building`;
const escape = value => value.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
await rm(temporary, { recursive: true, force: true });
try {
  const { index, errors } = await pagefind.createIndex({
    forceLanguage: "en", includeCharacters: "._", writePlayground: false,
  });
  if (errors?.length || !index) throw new Error(JSON.stringify(errors));
  for (const record of records) {
    const metadata = Object.entries(record.meta).map(([key, value]) =>
      `<meta data-pagefind-meta="${key}[content]" content="${escape(value)}">`).join("");
    const name = record.meta.symbol?.split(".").at(-1) || "";
    const names = record.meta.symbol ? [...new Set([record.meta.title, record.meta.symbol, name])] : [];
    const result = await index.addHTMLFile({
      url: record.url,
      content: `<html lang="en"><head>${metadata}</head><body data-pagefind-body>
        <meta data-pagefind-filter="section[content]" content="${escape(record.meta.section)}">
        ${names.map(value => `<meta data-pagefind-filter="api_name[content]" content="${escape(value)}">`).join("")}
        <h1 data-pagefind-weight="24">${escape(record.meta.title)}</h1>
        <p data-pagefind-weight="12">${escape([record.meta.symbol, name].filter(Boolean).join(" "))}</p>
        <p>${escape(record.content)}</p></body></html>`,
    });
    if (result.errors?.length) throw new Error(JSON.stringify(result.errors));
  }
  const written = await index.writeFiles({ outputPath: temporary });
  if (written.errors?.length) throw new Error(JSON.stringify(written.errors));
  for (const name of ["pagefind-ui.js", "pagefind-ui.css", "pagefind-modular-ui.js", "pagefind-modular-ui.css",
    "pagefind-component-ui.js", "pagefind-component-ui.css", "pagefind-highlight.js"]) {
    await rm(`${temporary}/${name}`, { force: true });
  }
  const terms = [...new Set(records.flatMap(record => record.content.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "").match(/[\p{L}\p{N}_]+(?:\.[\p{L}\p{N}_]+)*/gu) || []))].sort();
  await writeFile(`${temporary}/terms.json`, JSON.stringify(terms));
  const modules = new Map();
  for (const { meta } of records) {
    if (meta.section !== "Python API" || !meta.symbol) continue;
    if (!modules.has(meta.module)) modules.set(meta.module, new Set());
    modules.get(meta.module).add(meta.title);
  }
  const names = [...modules].map(([module, titles]) => [module, [...titles].sort()]);
  const autocomplete = await readFile(new URL("./autocomplete.mjs", import.meta.url), "utf8");
  await writeFile(`${temporary}/autocomplete.js`, `${autocomplete}\nexport const autocomplete = createAutocomplete(${JSON.stringify(names)}.flatMap(([module, names]) => names.map(name => [name, module + "." + name])));\n`);
  const frequencies = new Map();
  const canonical = new Map();
  for (const record of records) {
    const tokens = new Set(record.content.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "").match(/[\p{L}\p{N}_]+/gu) || []);
    for (const token of tokens) {
      if (/^[\p{L}][\p{L}_]{2,47}$/u.test(token)) frequencies.set(token, (frequencies.get(token) || 0) + 1);
    }
    for (const name of record.meta.symbol?.split(".") || []) {
      if (/^[A-Z]/.test(name)) canonical.set(name.toLowerCase(), name);
    }
  }
  const lexicon = [...frequencies].sort(([a], [b]) => a.localeCompare(b))
    .map(([word, frequency]) => canonical.has(word) ? [word, frequency, canonical.get(word)] : [word, frequency]);
  await writeFile(`${temporary}/spelling.json`, JSON.stringify(lexicon));
  const library = require.resolve("damerau-levenshtein");
  const license = await readFile(resolve(dirname(library), "LICENSE"), "utf8");
  // Keep the pinned CommonJS library verbatim inside a browser-module wrapper.
  const metric = await readFile(library, "utf8");
  const spelling = await readFile(new URL("./spelling.mjs", import.meta.url), "utf8");
  await writeFile(`${temporary}/spelling.js`, `/*! damerau-levenshtein 1.0.8\n${license}*/\nconst module = {exports: {}};\n${metric}\n${spelling}\nexport const spellingDistance = (a, b) => module.exports(a, b).steps;\n`);
  await mkdir(dirname(target), { recursive: true });
  // Replace the complete bundle, so fragments from older releases cannot accumulate.
  await rm(target, { recursive: true, force: true });
  await rename(temporary, target);
  console.log(`Indexed ${records.length} search records with Pagefind.`);
} finally {
  await pagefind.close();
  await rm(temporary, { recursive: true, force: true });
}
