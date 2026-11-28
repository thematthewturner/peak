// Text with math typeset by KaTeX: $$...$$ display, $...$ inline, `...` code.
// Everything outside those markers is escaped, so card and tip text can never inject markup.
import katex from "katex";

const TOKEN = /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$|`[^`\n]+?`)/g;

export function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

export function renderMath(text: string): string {
  return text.split(TOKEN).map((part) => {
    if (part.length > 4 && part.startsWith("$$") && part.endsWith("$$")) {
      return katex.renderToString(part.slice(2, -2), { displayMode: true, throwOnError: false, strict: "ignore" });
    }
    if (part.length > 2 && part.startsWith("$") && part.endsWith("$")) {
      return katex.renderToString(part.slice(1, -1), { throwOnError: false, strict: "ignore" });
    }
    if (part.length > 2 && part.startsWith("`") && part.endsWith("`")) {
      return `<code>${escapeHtml(part.slice(1, -1))}</code>`;
    }
    return escapeHtml(part);
  }).join("");
}
