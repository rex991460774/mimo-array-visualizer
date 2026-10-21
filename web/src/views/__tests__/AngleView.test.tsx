import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NoiseAccuracy } from "../../api/types";
import { EVALUATION, jsonResponse, resetStore } from "../../__tests__/fixtures";
import azimuthJson from "../../__tests__/fixtures/noise-azimuth.json";
import elevationJson from "../../__tests__/fixtures/noise-elevation.json";
import { useStore } from "../../state/store";
import { AngleView } from "../AngleView";

// Plotly does not run in jsdom.
vi.mock("../../charts/Plot", () => ({ Plot: ({ ariaLabel }: { ariaLabel: string }) => <div data-testid="plot" aria-label={ariaLabel} /> }));

/** Real /api/noise responses for the default project at 10 dB. */
const AZIMUTH = azimuthJson as unknown as NoiseAccuracy;
const ELEVATION = elevationJson as unknown as NoiseAccuracy;

const s = () => useStore.getState();
const fetchMock = vi.fn<typeof fetch>();
const noiseBodies = () =>
  fetchMock.mock.calls
    .filter(([url]) => String(url).endsWith("/api/noise"))
    .map(([, init]) => JSON.parse(String(init?.body)) as { axis: string; project: { noise?: { snr_db: number } } });

function serve(overrides: Partial<Record<"azimuth" | "elevation", NoiseAccuracy>> = {}) {
  fetchMock.mockImplementation(async (url, init) => {
    if (String(url).endsWith("/api/noise")) {
      const axis = JSON.parse(String(init?.body)).axis as "azimuth" | "elevation";
      return jsonResponse(overrides[axis] ?? (axis === "azimuth" ? AZIMUTH : ELEVATION));
    }
    return jsonResponse({ detail: "unexpected" }, 500);
  });
}

let run = 0;
beforeEach(() => {
  resetStore();
  // Responses are memoised per project key across tests: give every test its own key.
  run += 1;
  useStore.setState({ evaluation: EVALUATION, angleMode: "ideal" });
  s().updateProject({ ambiguity_margin_db: 0.5 + run / 100 });
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("AngleView modes", () => {
  it("explains that the noise-free error is a bias and switches to the Monte Carlo view", async () => {
    serve();
    render(<AngleView />);
    expect(screen.getByText(/理想字典下恒为 0/)).toBeTruthy();
    expect(noiseBodies()).toHaveLength(0);

    await userEvent.click(screen.getByRole("button", { name: "加噪声（蒙特卡洛）" }));
    expect(s().angleMode).toBe("noise");
    await waitFor(() => expect(screen.getAllByText("0.029°").length).toBeGreaterThan(0));
    expect(screen.getByText("CRB 0.030°")).toBeTruthy();
    expect(screen.getByText("-5 dB")).toBeTruthy();
    expect(screen.getByText("-2 dB")).toBeTruthy();
    expect(screen.getAllByText("0%")).toHaveLength(2);
    expect(screen.getByLabelText("方位 测角 RMSE (°)")).toBeTruthy();
    expect(noiseBodies().map((body) => body.axis).sort()).toEqual(["azimuth", "elevation"]);
  });

  it("commits a valid SNR to the project and refetches; rejects values outside −20…40 dB", async () => {
    serve();
    useStore.setState({ angleMode: "noise" });
    render(<AngleView />);
    await waitFor(() => expect(noiseBodies()).toHaveLength(2));
    const input = screen.getByLabelText("单通道 SNR") as HTMLInputElement;
    expect(input.value).toBe("10");

    await userEvent.clear(input);
    await userEvent.type(input, "15 dB{Enter}");
    expect(s().project!.noise).toEqual({ snr_db: 15 });
    await waitFor(() => expect(noiseBodies()).toHaveLength(4));
    expect(noiseBodies()[3].project.noise).toEqual({ snr_db: 15 });

    await userEvent.clear(input);
    await userEvent.type(input, "99{Enter}");
    expect(s().project!.noise).toEqual({ snr_db: 15 });
    expect(input.value).toBe("15");
  });

  it("formats thresholds outside the sweep and reports ambiguous angles", async () => {
    const never: NoiseAccuracy = {
      ...AZIMUTH,
      summary: { ...AZIMUTH.summary, threshold_snr_db: null, ambiguous_count: 3 },
    };
    const always: NoiseAccuracy = { ...ELEVATION, summary: { ...ELEVATION.summary, threshold_snr_db: -20 } };
    serve({ azimuth: never, elevation: always });
    useStore.setState({ angleMode: "noise" });
    render(<AngleView />);
    await waitFor(() => expect(screen.getByText("> 40 dB")).toBeTruthy());
    expect(screen.getByText("≤ -20 dB")).toBeTruthy();
    expect(screen.getByText(/3 个角度在无噪声时已经模糊/)).toBeTruthy();
    expect(screen.getByText("无噪声时已模糊")).toBeTruthy();
  });

  it("shows the server error for an axis", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ detail: "The channel response at boresight is zero; SNR is undefined." }, 422));
    useStore.setState({ angleMode: "noise" });
    render(<AngleView />);
    await waitFor(() => expect(screen.getAllByText(/SNR is undefined/).length).toBe(2));
    await act(async () => undefined);
  });
});
