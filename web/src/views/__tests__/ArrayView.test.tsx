import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CONFIG, EVALUATION, jsonResponse, resetStore } from "../../__tests__/fixtures";
import { useStore } from "../../state/store";
import { ArrayView } from "../ArrayView";

// Plotly does not run in jsdom; the virtual-array chart is replaced by a stub.
vi.mock("../VirtualPlot", () => ({ VirtualPlot: () => <div data-testid="virtual-plot" /> }));

const s = () => useStore.getState();
const LIMIT = CONFIG.limits.coordinate_lambda;
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  resetStore();
  useStore.setState({ evaluation: EVALUATION });
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

async function openTable() {
  render(<ArrayView />);
  await userEvent.click(screen.getByRole("button", { name: /坐标表/ }));
  return screen.getAllByRole("table")[0];
}

function cells(table: HTMLElement): HTMLInputElement[] {
  return within(table).getAllByRole("textbox") as HTMLInputElement[];
}

describe("ArrayView smoke", () => {
  it("renders both panels, element counts and the stubbed plot", () => {
    render(<ArrayView />);
    expect(screen.getByText("Tx 8")).toBeTruthy();
    expect(screen.getByText("Rx 8")).toBeTruthy();
    expect(screen.getByTestId("virtual-plot")).toBeTruthy();
    expect(screen.getByLabelText("Physical array editor")).toBeTruthy();
  });

  it("add Tx appends an element and selects it", async () => {
    render(<ArrayView />);
    await userEvent.click(document.querySelector(".panel-toolbar button")!);
    expect(s().project!.layout.tx).toHaveLength(9);
    expect(s().status?.key).toBe("status.added");
  });

  it("refuses to exceed the Tx limit", async () => {
    const tx = Array.from({ length: CONFIG.limits.max_tx }, (_, i) => ({ x: i, y: 0 }));
    s().updateProject({ layout: { ...s().project!.layout, tx } });
    render(<ArrayView />);
    fireEvent.click(document.querySelector(".panel-toolbar button")!);
    expect(s().project!.layout.tx).toHaveLength(CONFIG.limits.max_tx);
    expect(s().status?.key).toBe("physical.limit");
  });
});

describe("coordinate table (regressions for the ±500λ bug)", () => {
  it.each(["500.01", "-500.01", "-1e6", "1e309"])("rejects %s λ and keeps the old value", async (text) => {
    const table = await openTable();
    const x = cells(table)[0];
    await userEvent.clear(x);
    await userEvent.type(x, text);
    expect(x.getAttribute("aria-invalid")).toBe("true");
    expect(x.title).toBe(text === "1e309" ? "请输入十进制数字，如 76.5 或 7.65e1；不支持千分位逗号（1,000）和 0x 等写法" : `坐标需在 ±${LIMIT} λ 以内`);
    await userEvent.keyboard("{Enter}");
    expect(s().project!.layout.tx[0]).toEqual({ x: 0, y: 0 });
    expect(s().past).toHaveLength(0);
  });

  it.each(["1,000", "0x10", "0b1"])("rejects ambiguous input %s with the 'not a number' hint", async (text) => {
    const table = await openTable();
    const x = cells(table)[0];
    await userEvent.clear(x);
    await userEvent.type(x, text);
    expect(x.title).toContain("不支持千分位逗号");
    await userEvent.keyboard("{Enter}");
    expect(s().past).toHaveLength(0);
  });

  it("accepts exactly 500 λ (element is renumbered to the end)", async () => {
    const table = await openTable();
    const x = cells(table)[0];
    await userEvent.clear(x);
    await userEvent.type(x, `${LIMIT}{Enter}`);
    expect(s().project!.layout.tx.at(-1)).toEqual({ x: LIMIT, y: 0 });
    expect(s().past).toHaveLength(1);
  });

  it("accepts a decimal comma and keeps typed values unsnapped", async () => {
    const table = await openTable();
    const y = cells(table)[1];
    await userEvent.clear(y);
    await userEvent.type(y, "0,123{Enter}");
    expect(s().project!.layout.tx[0]).toEqual({ x: 0, y: 0.123 });
  });

  it("Escape cancels a coordinate edit (round 2 N3)", async () => {
    const table = await openTable();
    const x = cells(table)[0];
    await userEvent.clear(x);
    await userEvent.type(x, "7{Escape}");
    expect(s().project!.layout.tx[0]).toEqual({ x: 0, y: 0 });
    expect(s().past).toHaveLength(0);
  });

  it("in mm the limit is converted with the design wavelength", async () => {
    // The table shows λ (columns 0–1) and mm (columns 2–3) side by side.
    const table = await openTable();
    const x = cells(table)[2];
    const mmPerLambda = 299.792458 / s().project!.frequency_ghz;
    await userEvent.clear(x);
    await userEvent.type(x, `${(LIMIT * mmPerLambda + 1).toFixed(1)}mm`);
    expect(x.getAttribute("aria-invalid")).toBe("true");
    await userEvent.clear(x);
    await userEvent.type(x, "-3.8934mm");
    await userEvent.keyboard("{Enter}");
    expect(s().project!.layout.tx[0].x).toBeCloseTo(-1, 3);
  });
});

describe("toolbar", () => {
  it("undo and redo buttons follow the history", async () => {
    render(<ArrayView />);
    const undo = screen.getByRole("button", { name: /撤销/ }) as HTMLButtonElement;
    expect(undo.disabled).toBe(true);
    s().commitLayout({ ...s().project!.layout, rx: [{ x: -1, y: -5 }, ...s().project!.layout.rx.slice(1)] });
    await screen.findByRole("button", { name: /撤销/ });
    expect((screen.getByRole("button", { name: /撤销/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("auto layout failure is reported", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ detail: "tx_count: too large" }, 422));
    render(<ArrayView />);
    const trigger = screen.getByRole("button", { name: /自动排阵/ });
    await userEvent.click(trigger);
    const apply = screen.getAllByRole("button", { name: /应用|生成|自动排阵/ }).at(-1)!;
    await userEvent.click(apply);
    await vi.waitFor(() => expect(s().status?.key).toBe("overview.error"));
    expect(s().status?.detail).toBe("tx_count: too large");
  });
});
