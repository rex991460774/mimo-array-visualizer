import { describe, expect, it } from "vitest";
import { baseLayout, type ChartTheme } from "../../charts/theme";
import { displayValues } from "../DbfView";
import { fitViewport, PLOT_MARGIN } from "../plane";

describe("fitViewport", () => {
  it("centres the bounds and fits the tighter axis", () => {
    const vp = fitViewport({ minX: 0, maxX: 37.5, minY: -7, maxY: 9 }, 800 + PLOT_MARGIN.left + PLOT_MARGIN.right, 400 + PLOT_MARGIN.top + PLOT_MARGIN.bottom);
    expect(vp.cx).toBe(18.75);
    expect(vp.cy).toBe(1);
    expect(vp.scale).toBeCloseTo(Math.min(800 / 37.5, 400 / 16));
  });

  it("clamps the scale for tiny and huge arrays (±500 λ)", () => {
    expect(fitViewport({ minX: 0, maxX: 0, minY: 0, maxY: 0 }, 2000, 2000).scale).toBe(120);
    expect(fitViewport({ minX: -500, maxX: 500, minY: -500, maxY: 500 }, 300, 300).scale).toBe(2);
    expect(fitViewport({ minX: 0, maxX: 1, minY: 0, maxY: 1 }, 0, 0).scale).toBeGreaterThanOrEqual(2);
  });
});

describe("displayValues", () => {
  it("clips dB to [-40, 0] and maps NaN to the floor", () => {
    expect(displayValues([3, -10, -80, Number.NaN], "db")).toEqual([0, -10, -40, -40]);
  });

  it("converts to linear magnitude", () => {
    const [a, b] = displayValues([0, -20], "magnitude");
    expect(a).toBe(1);
    expect(b).toBeCloseTo(0.1);
  });
});

describe("baseLayout", () => {
  it("applies theme colours and keeps overrides", () => {
    const theme = { grid: "#111", zero: "#222", textSecondary: "#333" } as ChartTheme;
    const layout = baseLayout(theme, { height: 300 });
    expect(layout.height).toBe(300);
    expect(JSON.stringify(layout)).toContain("#111");
  });
});
