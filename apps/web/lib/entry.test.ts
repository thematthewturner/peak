import assert from "node:assert/strict";
import { test } from "node:test";
import { validateEntry } from "./entry.ts";

test("valid entries", () => {
  for (const s of ["12", "-12", "3.25", "-.5", "7/3", "-7/3", "12345", "-1234"]) {
    assert.equal(validateEntry(s).ok, true, s);
  }
});

test("invalid entries explain why", () => {
  const cases: [string, RegExp][] = [
    ["", /Enter/],
    ["1 1/2", /Mixed/],
    ["1,000", /Commas/],
    ["$5", /Commas/],
    ["50%", /Commas/],
    ["123456", /limit is 5/],
    ["-123456", /limit is 6/],
    ["1/0", /zero/],
    ["abc", /digits/],
  ];
  for (const [s, re] of cases) {
    const r = validateEntry(s);
    assert.equal(r.ok, false, s);
    if (!r.ok) assert.match(r.reason, re, s);
  }
});

test("negative numbers get six characters", () => {
  assert.equal(validateEntry("-1.234").ok, true);
});
