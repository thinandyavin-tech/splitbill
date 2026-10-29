// Run with: npm test (uses Node's built-in test runner and TypeScript stripping).
import assert from "node:assert/strict";
import { test } from "node:test";
import { formatSatang, parseSatang, splitEqual, toAmountString } from "./money.ts";

test("100.00 split three ways matches the backend", () => {
  const shares = splitEqual(parseSatang("100.00")!, ["alice", "bob", "carol"]);
  assert.deepEqual([...shares.values()].map(formatSatang), ["33.34", "33.33", "33.33"]);
});

test("0.1 + 0.2 displays 0.30", () => {
  assert.equal(formatSatang(parseSatang("0.1")! + parseSatang("0.2")!), "0.30");
});

test("Thai formatting with thousands separators", () => {
  assert.equal(formatSatang(100000), "1,000.00");
  assert.equal(formatSatang(123456789), "1,234,567.89");
  assert.equal(formatSatang(-33333), "-333.33");
  assert.equal(formatSatang(5), "0.05");
  assert.equal(toAmountString(123456789), "1234567.89");
});

test("rejects what the backend rejects", () => {
  for (const bad of ["10.005", "", "-1", "1e3", "abc", "1,000", "10000000000.00"]) {
    assert.equal(parseSatang(bad), null, bad);
  }
  assert.equal(parseSatang("7"), 700);
  assert.equal(parseSatang("1000.5"), 100050);
});
