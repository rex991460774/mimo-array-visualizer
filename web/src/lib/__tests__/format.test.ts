import { afterEach, describe, expect, it, vi } from "vitest";
import {
  dbToMagnitude,
  downloadBlob,
  downloadJson,
  fmt,
  fmtLambda,
  fmtSigned,
  formatBytes,
  parseNumber,
  safeFilename,
  trimNumber,
} from "../format";

describe("parseNumber — accepted input", () => {
  it.each([
    ["77", 77],
    ["76.5", 76.5],
    [" 76.5 ", 76.5],
    ["+3", 3],
    ["-3", -3],
    ["\u22123", -3], // typographic minus
    [".5", 0.5],
    ["5.", 5],
    ["7.65e1", 76.5],
    ["7.65E1", 76.5],
    ["1e-3", 0.001],
    ["0", 0],
  ])("%j → %d", (text, expected) => {
    expect(parseNumber(text)).toBe(expected);
  });

  it("accepts an unambiguous decimal comma (round 1 comma bug)", () => {
    expect(parseNumber("1,5")).toBe(1.5);
    expect(parseNumber("0,125")).toBe(0.125);
    expect(parseNumber("-2,25")).toBe(-2.25);
    expect(parseNumber("12,3456")).toBe(12.3456);
  });

  it("strips one unit suffix, case-insensitively, with or without a space", () => {
    expect(parseNumber("1946.5mm", ["mm"])).toBe(1946.5);
    expect(parseNumber("12 MM", ["mm"])).toBe(12);
    expect(parseNumber("3λ", ["λ"])).toBe(3);
    expect(parseNumber("77 ghz", ["ghz", "g"])).toBe(77);
  });
});

describe("parseNumber — rejected input (regressions from rounds 1–2)", () => {
  it.each([
    "1,000", // thousands separator or decimal? ambiguous → refuse
    "-1,000",
    "12,345",
    "1.000,5",
    "1,000.5",
    "1,2,3",
    "0x4D", // hex literal (round 1)
    "0X4d",
    "0b1", // binary literal
    "0o7",
    "Infinity",
    "NaN",
    "1e309", // overflows to Infinity
    "",
    " ",
    "-",
    ".",
    "e5",
    "1e",
    "1..2",
    "--1",
    "1 2",
    "abc",
    "1_000",
  ])("%j → null", (text) => {
    expect(parseNumber(text)).toBeNull();
  });

  it("does not accept a unit that was not allowed", () => {
    expect(parseNumber("12mm")).toBeNull();
    expect(parseNumber("12mm", ["λ"])).toBeNull();
  });
});

describe("display formatting", () => {
  it("fmt renders placeholders for missing or non-finite values", () => {
    expect(fmt(null)).toBe("—");
    expect(fmt(undefined)).toBe("—");
    expect(fmt(Number.NaN)).toBe("—");
    expect(fmt(Number.POSITIVE_INFINITY)).toBe("—");
    expect(fmt(1.234, 2, " dB")).toBe("1.23 dB");
    expect(fmt(2)).toBe("2.0");
  });

  it("fmtSigned adds a plus sign and folds tiny values to zero", () => {
    expect(fmtSigned(3)).toBe("+3°");
    expect(fmtSigned(-3)).toBe("-3°");
    expect(fmtSigned(0.4)).toBe("0°");
    expect(fmtSigned(-0.04, 1)).toBe("0°");
    expect(fmtSigned(0.06, 1, " dB")).toBe("+0.1 dB");
    expect(fmtSigned(null)).toBe("—");
  });

  it("trimNumber drops trailing zeros only after a decimal point", () => {
    expect(trimNumber(1.5)).toBe("1.5");
    expect(trimNumber(2)).toBe("2");
    expect(trimNumber(100)).toBe("100");
    expect(trimNumber(1.23456, 4)).toBe("1.2346");
    expect(trimNumber(Number.NaN)).toBe("—");
    expect(fmtLambda(3.5)).toBe("3.5 λ");
  });

  it("dbToMagnitude clamps to [0, 1]", () => {
    expect(dbToMagnitude(0)).toBe(1);
    expect(dbToMagnitude(6)).toBe(1);
    expect(dbToMagnitude(-20)).toBeCloseTo(0.1);
    expect(dbToMagnitude(-400)).toBeGreaterThanOrEqual(0);
  });

  it("formatBytes picks B / KB / MB", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(32 * 1024 * 1024)).toBe("32.0 MB");
  });

  it("safeFilename removes path separators and control characters", () => {
    expect(safeFilename('a/b\\c:d*e?f"g<h>i|j')).toBe("a_b_c_d_e_f_g_h_i_j");
    expect(safeFilename("x\u0000y")).toBe("x_y");
    expect(safeFilename("   ")).toBe("project");
    expect(safeFilename("../../etc/passwd")).toBe(".._.._etc_passwd");
  });
});

describe("downloads", () => {
  afterEach(() => vi.useRealTimers());

  it("downloadBlob clicks a temporary link and revokes the URL later", () => {
    vi.useFakeTimers();
    const create = vi.fn(() => "blob:mock");
    const revoke = vi.fn();
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    downloadBlob(new Blob(["x"]), "out.zip");
    expect(click).toHaveBeenCalledTimes(1);
    expect(document.querySelector("a[download]")).toBeNull();
    expect(revoke).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    expect(revoke).toHaveBeenCalledWith("blob:mock");
  });

  it("downloadJson writes pretty JSON with a trailing newline", async () => {
    let captured: Blob | null = null;
    Object.assign(URL, {
      createObjectURL: (blob: Blob) => {
        captured = blob;
        return "blob:x";
      },
      revokeObjectURL: () => {},
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    downloadJson({ a: 1 }, "a.json");
    const text = await new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.readAsText(captured!);
    });
    expect(text).toBe('{\n  "a": 1\n}\n');
    expect(captured!.type).toBe("application/json");
  });
});
