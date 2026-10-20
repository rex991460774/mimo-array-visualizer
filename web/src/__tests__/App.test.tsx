import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { DialogId, ViewId } from "../state/store";
import { useStore } from "../state/store";
import { CONFIG, EVALUATION, jsonResponse, resetStore } from "./fixtures";

// Plotly cannot run in jsdom: every chart becomes a placeholder.
vi.mock("../charts/Plot", () => ({ Plot: () => <div data-testid="plot" /> }));

const fetchMock = vi.fn<typeof fetch>();
const s = () => useStore.getState();

function router(path: string, init?: RequestInit): Response {
  if (path === "/api/config") return jsonResponse(CONFIG);
  if (path === "/api/evaluate") return jsonResponse(EVALUATION);
  if (path === "/api/projects" && !init?.method) return jsonResponse([]);
  if (path === "/api/health") return jsonResponse({ status: "ok", version: "1.0.0" });
  // Heavy analyses are not faked: views must show an error, not crash.
  return jsonResponse({ detail: "not available in unit tests" }, 503);
}

beforeEach(() => {
  resetStore();
  useStore.setState({ config: null, project: null });
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (input, init) => router(String(input), init));
  vi.stubGlobal("fetch", fetchMock);
});

async function boot() {
  render(<App />);
  await waitFor(() => expect(s().project).not.toBeNull());
  await waitFor(() => expect(s().evaluation).not.toBeNull(), { timeout: 2000 });
}

describe("App smoke", () => {
  it("loads the config, evaluates and renders the overview", async () => {
    await boot();
    expect(fetchMock.mock.calls.some(([path]) => path === "/api/config")).toBe(true);
    expect(await screen.findByText("阵列概览")).toBeTruthy();
  });

  it("shows a localised error with a retry when the server is unreachable", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<App />);
    expect(await screen.findByText(/无法连接到服务器/)).toBeTruthy();
  });

  it.each(["array", "dbf1d", "dbf2d", "angle", "band"] as ViewId[])("view %s renders without throwing", async (view) => {
    const errors: unknown[] = [];
    const onError = (event: ErrorEvent) => errors.push(event.error);
    window.addEventListener("error", onError);
    await boot();
    act(() => s().setView(view));
    await new Promise((resolve) => setTimeout(resolve, 400));
    window.removeEventListener("error", onError);
    expect(errors).toEqual([]);
    expect(document.querySelector(".app, #root, body")!.textContent!.length).toBeGreaterThan(0);
  });

  it.each(["dictionary", "patterns", "report", "projects", "help", "settings", "share"] as DialogId[])(
    "dialog %s opens and closes",
    async (dialog) => {
      await boot();
      act(() => s().openDialog(dialog));
      const node = await screen.findByRole("dialog", {}, { timeout: 3000 });
      expect(node).toBeTruthy();
      fireEvent.keyDown(window, { key: "Escape" });
      await waitFor(() => expect(s().dialog).toBeNull());
    },
  );

  it("keyboard shortcuts switch views and toggle delete mode", async () => {
    await boot();
    fireEvent.keyDown(window, { key: "4" });
    expect(s().view).toBe("angle");
    fireEvent.keyDown(window, { key: "1" });
    fireEvent.keyDown(window, { key: "Delete" });
    expect(s().deleteMode).toBe(true);
  });

  it("Ctrl+Z / Ctrl+Y undo and redo a layout edit", async () => {
    await boot();
    const layout = s().project!.layout;
    act(() => s().commitLayout({ ...layout, rx: [{ x: -1, y: -5 }, ...layout.rx.slice(1)] }));
    fireEvent.keyDown(window, { key: "z", ctrlKey: true });
    expect(s().project!.layout).toEqual(layout);
    fireEvent.keyDown(window, { key: "y", ctrlKey: true });
    expect(s().project!.layout.rx[0]).toEqual({ x: -1, y: -5 });
  });

  it("switching language re-renders the chrome", async () => {
    await boot();
    act(() => s().setLanguage("en"));
    expect(await screen.findByText("Overview")).toBeTruthy();
    expect(document.documentElement.lang).toMatch(/en/);
  });
});
