import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EVALUATION, jsonResponse, resetStore } from "../../__tests__/fixtures";
import { useStore } from "../../state/store";
import { BandView } from "../BandView";

const s = () => useStore.getState();
const fetchMock = vi.fn<typeof fetch>();

function sweep(dictionary: "operating" | "design") {
  const point = (frequency: number, role: string) => ({
    frequency_ghz: frequency,
    dictionary_ghz: dictionary === "design" ? 77 : frequency,
    wavelength_mm: 299.792458 / frequency,
    capability: EVALUATION.capability,
    resolution: EVALUATION.resolution,
    psl_db: -3.8,
    azimuth_psl_db: -12,
    elevation_psl_db: -3.8,
    angle: EVALUATION.angle,
    requirements: [],
    passed: 0,
    failed: 0,
    role,
  });
  return {
    band: { preset: "77G", start_ghz: 76, stop_ghz: 81, dictionary_frequency: dictionary },
    design_ghz: 77,
    design_in_band: true,
    dictionary_frequency: dictionary,
    uses_single_frequency_data: false,
    points: [point(76, "start"), point(77, "design"), point(81, "stop")],
  };
}

beforeEach(() => {
  resetStore();
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url, init) => {
    if (String(url).endsWith("/api/band")) {
      const body = JSON.parse(String(init?.body));
      return jsonResponse(sweep(body.project.band.dictionary_frequency ?? "operating"));
    }
    if (String(url).endsWith("/api/projects")) return jsonResponse([]);
    return jsonResponse({ detail: "unexpected" }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);
});

describe("BandView dictionary frequency", () => {
  it("defaults to the operating frequency and can fix the dictionary at the design frequency", async () => {
    render(<BandView />);
    const operating = screen.getByRole("button", { name: "跟随工作频率" });
    const design = screen.getByRole("button", { name: "固定在设计频率" });
    expect(operating.getAttribute("aria-pressed")).toBe("true");
    await waitFor(() => expect(screen.getByText("81 GHz")).toBeTruthy());
    expect(screen.queryByText(/字典固定在/)).toBeNull();

    await userEvent.click(design);
    expect(s().project!.band.dictionary_frequency).toBe("design");
    expect(s().project!.band.start_ghz).toBe(76);
    await waitFor(() => expect(screen.getByText(/字典固定在 77 GHz/)).toBeTruthy());
    const bodies = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/api/band"));
    expect(JSON.parse(String(bodies[bodies.length - 1][1]?.body)).project.band.dictionary_frequency).toBe("design");
  });
});
