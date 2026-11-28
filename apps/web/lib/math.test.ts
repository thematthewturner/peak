import assert from "node:assert/strict";
import { test } from "node:test";
import { renderMath } from "./math.ts";

test("display and inline math are typeset", () => {
  const html = renderMath("$$d = \\sqrt{x^2}$$ with $(h, k)$");
  assert.match(html, /katex-display/);
  assert.match(html, /class="katex"/);
  assert.doesNotMatch(html, /\$/);
});

test("plain text is escaped and code renders monospace", () => {
  const html = renderMath("<b>hi</b> use `y1 ~ m x1 + b`");
  assert.match(html, /&lt;b&gt;hi&lt;\/b&gt;/);
  assert.match(html, /<code>y1 ~ m x1 \+ b<\/code>/);
});

test("bad TeX shows as text instead of crashing", () => {
  assert.doesNotThrow(() => renderMath("$\\frac{1$"));
});
