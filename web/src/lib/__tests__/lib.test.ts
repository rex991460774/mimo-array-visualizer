import { describe, expect, it } from "vitest";
import { decodeMatrix, matrixRow, wire } from "../encoding";
import { dbToMagnitude, fmtSigned, parseNumber, trimNumber } from "../format";
import { layoutsEqual, nextElementPosition, renumber, snap, virtualGroups } from "../geometry";

describe("geometry", () => {
  it("snaps to the λ/2 grid without negative zero", () => {
    expect(snap(0.74)).toBe(0.5);
    expect(snap(0.76)).toBe(1);
    expect(Object.is(snap(-0.1), -0)).toBe(false);
  });

  it("renumbers by position and follows the selected element", () => {
    const layout = { tx: [{ x: 5, y: 0 }, { x: 1, y: 0 }], rx: [{ x: 0, y: -1 }] };
    const result = renumber(layout, { kind: "tx", index: 0 });
    expect(result.layout.tx).toEqual([{ x: 1, y: 0 }, { x: 5, y: 0 }]);
    expect(result.follow).toEqual({ kind: "tx", index: 1 });
  });

  it("groups duplicate virtual positions with their Tx-Rx pairs", () => {
    const layout = { tx: [{ x: 0, y: 0 }, { x: 1, y: 0 }], rx: [{ x: 0, y: 0 }, { x: 1, y: 0 }] };
    const groups = virtualGroups(layout);
    expect(groups).toHaveLength(3);
    const middle = groups.find((group) => group.x === 1)!;
    expect(middle.count).toBe(2);
    expect(middle.pairs).toEqual(["Tx1-Rx2", "Tx2-Rx1"]);
  });

  it("places new elements 1 λ to the right of the anchor, skipping occupied cells", () => {
    const layout = { tx: [{ x: 0, y: 0 }, { x: 1, y: 0 }], rx: [{ x: 2, y: 0 }] };
    expect(nextElementPosition(layout, "tx", { kind: "tx", index: 0 })).toEqual({ x: 3, y: 0 });
    expect(nextElementPosition({ tx: [], rx: [] }, "rx", null)).toEqual({ x: 0, y: -5 });
  });

  it("compares layouts by value", () => {
    const a = { tx: [{ x: 0, y: 0 }], rx: [{ x: 1, y: 0 }] };
    expect(layoutsEqual(a, structuredClone(a))).toBe(true);
    expect(layoutsEqual(a, { ...a, rx: [{ x: 1.5, y: 0 }] })).toBe(false);
  });
});

describe("format", () => {
  it("parses numbers with optional unit suffixes and decimal commas", () => {
    expect(parseNumber("77 GHz", ["ghz", "g"])).toBe(77);
    expect(parseNumber("76.5")).toBe(76.5);
    expect(parseNumber("1,5")).toBe(1.5);
    expect(parseNumber("0,125")).toBe(0.125);
    expect(parseNumber("-.5")).toBe(-0.5);
    expect(parseNumber("1e-3")).toBe(0.001);
    expect(parseNumber("\u221275°", ["°"])).toBe(-75);
    expect(parseNumber("abc")).toBeNull();
    expect(parseNumber("  ")).toBeNull();
  });

  it("rejects input that could be misread instead of guessing", () => {
    // A comma before exactly three digits may be a thousands separator.
    expect(parseNumber("1,000")).toBeNull();
    expect(parseNumber("24,125g", ["ghz", "g"])).toBeNull();
    expect(parseNumber("1,000,000")).toBeNull();
    expect(parseNumber("1.000,5")).toBeNull();
    // Non-decimal literals and special values.
    expect(parseNumber("0x4D")).toBeNull();
    expect(parseNumber("0b101")).toBeNull();
    expect(parseNumber("0o17")).toBeNull();
    expect(parseNumber("Infinity")).toBeNull();
    expect(parseNumber("1e999")).toBeNull();
    expect(parseNumber("7 7")).toBeNull();
    expect(parseNumber("77..5")).toBeNull();
  });

  it("formats signed angles and trims trailing zeros", () => {
    expect(fmtSigned(12)).toBe("+12°");
    expect(fmtSigned(-0.2)).toBe("0°");
    expect(fmtSigned(null)).toBe("—");
    expect(trimNumber(1.5)).toBe("1.5");
    expect(trimNumber(2)).toBe("2");
  });

  it("converts dB to clipped correlation magnitude", () => {
    expect(dbToMagnitude(0)).toBe(1);
    expect(dbToMagnitude(-20)).toBeCloseTo(0.1);
    expect(dbToMagnitude(3)).toBe(1);
  });
});

describe("encoding", () => {
  it("decodes base64 float32 matrices", () => {
    const values = new Float32Array([1, 2, 3, 4, 5, 6]);
    const data = Buffer.from(values.buffer).toString("base64");
    const matrix = decodeMatrix({ dtype: "float32", shape: [2, 3], data });
    expect(matrix.rows).toBe(2);
    expect(matrixRow(matrix, 1)).toEqual([4, 5, 6]);
  });

  it("maps wire infinities", () => {
    expect(wire("Infinity")).toBe(Number.POSITIVE_INFINITY);
    expect(wire("-Infinity")).toBe(Number.NEGATIVE_INFINITY);
    expect(wire(null)).toBeNull();
    expect(wire(1.5)).toBe(1.5);
  });
});
