import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { EVALUATION, jsonResponse, project, resetStore } from "../../__tests__/fixtures";
import { dbfKey, evaluationKey, fetchBank, fetchNoise, noiseKey, snrOf, useEvaluationSync } from "../compute";
import { useStore } from "../store";

const fetchMock = vi.fn<typeof fetch>();
beforeEach(() => {
  resetStore();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("cache keys", () => {
  it("the project name does not affect evaluation", () => {
    expect(evaluationKey(project({ name: "a" }))).toBe(evaluationKey(project({ name: "b" })));
    expect(evaluationKey(project({ frequency_ghz: 79 }))).not.toBe(evaluationKey(project()));
  });

  it("frequency does not affect DBF spectra, layout does", () => {
    expect(dbfKey(project({ frequency_ghz: 79 }))).toBe(dbfKey(project()));
    const moved = project();
    moved.layout.tx[0] = { x: -1, y: 0 };
    expect(dbfKey(moved)).not.toBe(dbfKey(project()));
  });
});

describe("noise key", () => {
  it("depends on SNR and element pattern but not on frequency, band or name", () => {
    const base = project();
    expect(snrOf(base)).toBe(10);
    expect(noiseKey(project({ noise: { snr_db: 10 } }))).toBe(noiseKey(base));
    expect(noiseKey(project({ noise: { snr_db: 20 } }))).not.toBe(noiseKey(base));
    expect(noiseKey(project({ element_pattern: { asset: "a".repeat(64), swap_axes: false } }))).not.toBe(noiseKey(base));
    expect(noiseKey(project({ name: "x", frequency_ghz: 79 }))).toBe(noiseKey(base));
    expect(noiseKey(project({ band: { ...base.band, dictionary_frequency: "design" } }))).toBe(noiseKey(base));
  });

  it("dictionary frequency only changes the evaluation (band sweep) key", () => {
    const base = project();
    const fixed = project({ band: { ...base.band, dictionary_frequency: "design" } });
    expect(dbfKey(fixed)).toBe(dbfKey(base));
    expect(evaluationKey(fixed)).not.toBe(evaluationKey(base));
  });

  it("fetchNoise shares one request per (axis, noise key)", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ ok: true }));
    const p = project({ noise: { snr_db: 33 } });
    const first = fetchNoise(p, "azimuth");
    expect(fetchNoise(project({ ...p, name: "renamed" }), "azimuth")).toBe(first);
    await first;
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/noise$/);
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toMatchObject({ axis: "azimuth", project: { noise: { snr_db: 33 } } });
  });
});

describe("fetchBank", () => {
  it("shares one request per (axis, DBF key) and retries after a failure", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "x" }, 500));
    const p = project({ name: "bank-a" });
    p.layout.tx[0] = { x: -7, y: 0 }; // unique key for this test
    await expect(fetchBank(p, "azimuth")).rejects.toBeTruthy();
    fetchMock.mockImplementation(async () => jsonResponse({ ok: true }));
    const first = fetchBank(p, "azimuth");
    const second = fetchBank(project({ ...p, name: "renamed" }), "azimuth");
    expect(second).toBe(first);
    await first;
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await fetchBank(p, "elevation");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});

describe("useEvaluationSync", () => {
  it("evaluates after a debounce and stores the result", async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation(async () => jsonResponse(EVALUATION));
    renderHook(() => useEvaluationSync());
    expect(fetchMock).not.toHaveBeenCalled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(useStore.getState().evaluation?.summary.virtual_count).toBe(64);
    expect(useStore.getState().evaluating).toBe(false);
    vi.useRealTimers();
  });

  it("keeps the last result and records a localised error when the server is down", async () => {
    vi.useFakeTimers();
    useStore.setState({ evaluation: EVALUATION });
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    renderHook(() => useEvaluationSync());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    expect(useStore.getState().evaluation).toBe(EVALUATION);
    expect(useStore.getState().evaluationError).toContain("无法连接到服务器");
    vi.useRealTimers();
  });

  it("a rename does not trigger a new evaluation", async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation(async () => jsonResponse(EVALUATION));
    renderHook(() => useEvaluationSync());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    act(() => useStore.getState().updateProject({ name: "renamed" }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});
