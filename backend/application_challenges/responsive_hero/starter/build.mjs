// Deterministic, dependency-free build for the Responsive Hero starter.
// Validates the two editable source files and copies them to dist/. No network, no npm.
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";

const html = readFileSync("src/index.html", "utf8");
const css = readFileSync("src/styles.css", "utf8");
const errors = [];

if (!/<main[\s>]/i.test(html)) errors.push("index.html must contain a <main> element.");
if (!/<link[^>]+href="styles\.css"/i.test(html)) errors.push("index.html must link styles.css.");
if (/<(script|iframe|frame|object|embed)[\s>]/i.test(html)) {
  errors.push("Scripts and embedded frames are not allowed in this project.");
}
if (/<link\b(?![^>]*href="styles\.css")[^>]*>/i.test(html)) {
  errors.push("Only styles.css may be linked.");
}
const externalReference = /(?:src|href)\s*=\s*["']?\s*(?:[a-z][a-z0-9+.-]*:|\/\/)(?!#)/i;
if (externalReference.test(html.replace(/xmlns(?::\w+)?="[^"]*"/gi, ""))) {
  errors.push("External or absolute resource URLs are not allowed.");
}
if (/@import|url\(\s*["']?\s*(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(css)) {
  errors.push("styles.css may not import or reference external resources.");
}

const stripped = css.replace(/\/\*[\s\S]*?\*\//g, "").replace(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g, "");
let depth = 0;
for (const character of stripped) {
  if (character === "{") depth += 1;
  if (character === "}") depth -= 1;
  if (depth < 0) break;
}
if (depth !== 0) errors.push("styles.css has unbalanced braces.");

if (errors.length > 0) {
  for (const error of errors) console.error(`build error: ${error}`);
  process.exit(1);
}

rmSync("dist", { recursive: true, force: true });
mkdirSync("dist");
writeFileSync("dist/index.html", html);
writeFileSync("dist/styles.css", css);
console.log("Built dist/index.html and dist/styles.css.");
