// Numeric-entry rules, mirrored from services/backend/peak/entry.py (College Board student-produced
// responses). The server is the authority; this gives instant, identical feedback.
export type EntryResult = { ok: true } | { ok: false; reason: string };

const DECIMAL = /^-?(\d+\.?\d*|\.\d+)$/;
const FRACTION = /^-?\d+\/\d+$/;

export function validateEntry(raw: string): EntryResult {
  const s = raw.trim();
  if (!s) return { ok: false, reason: "Enter an answer." };
  if (s.includes(" "))
    return { ok: false, reason: "Mixed numbers aren't accepted. Enter a fraction or decimal instead." };
  if (/[,$%]/.test(s)) return { ok: false, reason: "Commas, $ and % aren't accepted." };
  const limit = s.startsWith("-") ? 6 : 5;
  if (s.length > limit) return { ok: false, reason: `Too many characters: the limit is ${limit}.` };
  if (FRACTION.test(s)) {
    const den = Number(s.split("/")[1]);
    return den === 0 ? { ok: false, reason: "The denominator can't be zero." } : { ok: true };
  }
  if (DECIMAL.test(s)) return { ok: true };
  return { ok: false, reason: "Use only digits, a decimal point, a slash, and a leading minus sign." };
}
