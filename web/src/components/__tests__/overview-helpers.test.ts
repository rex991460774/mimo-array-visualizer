import { describe, expect, it } from "vitest";
import type { AngleMetrics, RequirementCheck } from "../../api/types";
import { translate } from "../../i18n";
import { axisName, cutSummary, errorText, marginText, noFoldText, requirementLabel, requirementValue } from "../Overview";

const t = (key: Parameters<typeof translate>[1], params?: Record<string, string | number>) => translate("zh", key, params);
const metrics = (overrides: Partial<AngleMetrics> = {}) =>
  ({
    no_fold_left: -75,
    no_fold_right: 75,
    no_fold_width: 150,
    min_peak_margin_db: 12.3,
    negative_cut_reason: "data_boundary",
    positive_cut_reason: "data_boundary",
    ...overrides,
  }) as AngleMetrics;

describe("Overview text helpers", () => {
  it("cutSummary merges equal reasons and pairs different ones", () => {
    expect(cutSummary(metrics(), t)).toBe("覆盖整个视场");
    expect(cutSummary(metrics({ negative_cut_reason: "competitor" }), t)).toBe("负 竞争峰模糊 / 正 覆盖整个视场");
  });

  it("noFoldText formats the unambiguous range", () => {
    expect(noFoldText(metrics())).toBe("-75° ~ +75°  (150°)");
    expect(noFoldText(metrics({ no_fold_left: null as never }))).toBe("—");
  });

  it("marginText handles infinite margins and limited ranges", () => {
    expect(marginText(metrics(), t)).toBe("12.3 dB");
    expect(marginText(metrics({ min_peak_margin_db: "Infinity" }), t)).toBe("无竞争峰");
    expect(marginText(metrics({ no_fold_width: 0, negative_cut_reason: "boundary_limited" }), t)).toBe("不可用");
  });

  it("errorText uses 3 decimals below 1° (0.092° from the HFSS case)", () => {
    expect(errorText(0.092)).toBe("0.092°");
    expect(errorText(10)).toBe("10.00°");
    expect(errorText(null)).toBe("—");
    expect(errorText(Number.NaN)).toBe("—");
  });

  it("requirement labels and values", () => {
    const check = (key: RequirementCheck["key"], actual: number, target: number) =>
      ({ key, axis: "azimuth", actual, target, status: "pass" }) as RequirementCheck;
    expect(axisName(null, t)).toBe("");
    expect(requirementLabel(check("resolution", 1, 2), t)).toBe("方位分辨率");
    expect(requirementValue(check("resolution", 1.723, 2), t)).toBe("1.72° / ≤ 2.00°");
    expect(requirementValue(check("unambiguous_fov", 150, 150), t)).toBe("150° / 150°");
    expect(requirementValue(check("max_error", 0.05, 0.1), t)).toBe("0.050° / ≤ 0.100°");
    expect(requirementValue(check("peak_margin", 3.2, 1), t)).toBe("3.2 dB / ≥ 1.0 dB");
    expect(requirementValue(check("psl", -12.66, -10), t)).toBe("-12.7 dB / ≤ -10.0 dB");
  });
});
