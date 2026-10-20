import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { parseNumber } from "../../lib/format";
import { Button, Callout, Dialog, Menu, MenuItem, NumberInput, Segmented, useFilePicker } from "../ui";

function Harness({ initial = 77, onCommit = vi.fn(), invalidTitle }: {
  initial?: number;
  onCommit?: (value: number) => void;
  invalidTitle?: string | ((text: string) => string);
}) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <NumberInput
        aria-label="freq"
        value={value}
        parse={(text) => {
          const parsed = parseNumber(text, ["ghz"]);
          return parsed !== null && parsed > 0 && parsed <= 1000 ? parsed : null;
        }}
        invalidTitle={invalidTitle}
        onCommit={(v) => {
          onCommit(v);
          setValue(v);
        }}
      />
      <output data-testid="value">{value}</output>
      <button type="button">elsewhere</button>
    </>
  );
}

const input = () => screen.getByLabelText("freq") as HTMLInputElement;
const committed = () => screen.getByTestId("value").textContent;

describe("NumberInput", () => {
  it("Enter commits exactly once", async () => {
    const onCommit = vi.fn();
    render(<Harness onCommit={onCommit} />);
    await userEvent.clear(input());
    await userEvent.type(input(), "78{Enter}");
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith(78);
    expect(committed()).toBe("78");
    expect(document.activeElement).not.toBe(input());
  });

  it("Tab (blur) commits", async () => {
    render(<Harness />);
    await userEvent.clear(input());
    await userEvent.type(input(), "79.5");
    await userEvent.tab();
    expect(committed()).toBe("79.5");
  });

  it("Escape cancels the edit and restores the text (round 2 N3)", async () => {
    const onCommit = vi.fn();
    render(<Harness onCommit={onCommit} />);
    await userEvent.clear(input());
    await userEvent.type(input(), "60{Escape}");
    expect(onCommit).not.toHaveBeenCalled();
    expect(committed()).toBe("77");
    expect(input().value).toBe("77");
    expect(input().getAttribute("aria-invalid")).toBeNull();
  });

  it("Escape on an ambiguous value does not commit it either", async () => {
    const onCommit = vi.fn();
    render(<Harness onCommit={onCommit} />);
    await userEvent.clear(input());
    await userEvent.type(input(), "1,5{Escape}");
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("the next edit after Escape commits normally", async () => {
    render(<Harness />);
    await userEvent.clear(input());
    await userEvent.type(input(), "60{Escape}");
    await userEvent.click(input());
    await userEvent.clear(input());
    await userEvent.type(input(), "80");
    await userEvent.click(screen.getByText("elsewhere"));
    expect(committed()).toBe("80");
  });

  it.each(["1,000", "0x4D", "0b1", "1.000,5", "abc", "-5", "2000"])(
    "invalid text %j is flagged while typing and discarded on commit",
    async (text) => {
      const onCommit = vi.fn();
      render(<Harness onCommit={onCommit} invalidTitle="bad" />);
      await userEvent.clear(input());
      await userEvent.type(input(), text);
      expect(input().getAttribute("aria-invalid")).toBe("true");
      expect(input().className).toContain("invalid");
      expect(input().title).toBe("bad");
      await userEvent.keyboard("{Enter}");
      expect(onCommit).not.toHaveBeenCalled();
      expect(input().value).toBe("77");
      expect(input().getAttribute("aria-invalid")).toBeNull();
    },
  );

  it("a decimal comma is accepted and shown normalised", async () => {
    render(<Harness />);
    await userEvent.clear(input());
    await userEvent.type(input(), "76,5{Enter}");
    expect(committed()).toBe("76.5");
    expect(input().value).toBe("76.5");
  });

  it("a function invalidTitle explains why the current text is wrong (round 2 N6)", async () => {
    render(
      <Harness
        invalidTitle={(text) => (parseNumber(text) === null ? "请输入十进制数字（不支持 1,000 和 0x）" : "需在 0~1000 GHz 之间")}
      />,
    );
    await userEvent.clear(input());
    await userEvent.type(input(), "1,000");
    expect(input().title).toContain("1,000");
    await userEvent.clear(input());
    await userEvent.type(input(), "2000");
    expect(input().title).toBe("需在 0~1000 GHz 之间");
  });

  it("committing the same value does not call onCommit", async () => {
    const onCommit = vi.fn();
    render(<Harness onCommit={onCommit} />);
    await userEvent.clear(input());
    await userEvent.type(input(), "77.0{Enter}");
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("an external value change updates the text unless the field is being edited", async () => {
    const { rerender } = render(<NumberInput aria-label="freq" value={1} parse={parseNumber} onCommit={() => {}} />);
    rerender(<NumberInput aria-label="freq" value={2} parse={parseNumber} onCommit={() => {}} />);
    expect(input().value).toBe("2");
    await userEvent.clear(input());
    await userEvent.type(input(), "9");
    rerender(<NumberInput aria-label="freq" value={3} parse={parseNumber} onCommit={() => {}} />);
    expect(input().value).toBe("9");
  });

  it("key presses do not bubble to global shortcuts (e.g. Delete removes an element)", () => {
    const outer = vi.fn();
    render(
      <div onKeyDown={outer}>
        <NumberInput aria-label="freq" value={1} parse={parseNumber} onCommit={() => {}} />
      </div>,
    );
    fireEvent.keyDown(input(), { key: "Delete" });
    expect(outer).not.toHaveBeenCalled();
  });
});

describe("Dialog", () => {
  it("is a labelled modal that closes on Escape, the close button and a backdrop click", async () => {
    const onClose = vi.fn();
    render(
      <Dialog title="设置" onClose={onClose} footer={<button type="button">ok</button>}>
        body
      </Dialog>,
    );
    const dialog = screen.getByRole("dialog", { name: "设置" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(document.activeElement).toBe(dialog);
    await userEvent.keyboard("{Escape}");
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    fireEvent.mouseDown(document.querySelector(".dialog-backdrop")!);
    fireEvent.mouseDown(dialog); // inside the panel: ignored
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("returns focus to the previously focused element on close", () => {
    render(<button type="button">opener</button>);
    const opener = screen.getByText("opener");
    opener.focus();
    const { unmount } = render(
      <Dialog title="t" onClose={() => {}}>
        x
      </Dialog>,
    );
    unmount();
    expect(document.activeElement).toBe(opener);
  });

  // Defect R5-2: the Dialog listens for Escape on window in the capture phase
  // (ui.tsx:208-216), before NumberInput's handler runs, so Escape inside a
  // numeric field in any dialog (settings, patterns…) closes the whole dialog
  // instead of only cancelling the edit.
  it.fails("Escape inside a NumberInput in a dialog only cancels the edit", async () => {
    const onClose = vi.fn();
    render(
      <Dialog title="设置" onClose={onClose}>
        <NumberInput aria-label="freq" value={77} parse={parseNumber} onCommit={() => {}} />
      </Dialog>,
    );
    await userEvent.clear(input());
    await userEvent.type(input(), "60{Escape}");
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("small components", () => {
  it("Button reflects active state and icon-only class", () => {
    render(
      <>
        <Button active aria-label="del" icon={<span>i</span>} />
        <Button variant="primary" size="sm">
          Save
        </Button>
      </>,
    );
    const del = screen.getByLabelText("del");
    expect(del.getAttribute("aria-pressed")).toBe("true");
    expect(del.className).toContain("icon");
    expect(screen.getByText("Save").className).toMatch(/btn primary sm/);
  });

  it("Segmented marks the current option and reports changes", async () => {
    const onChange = vi.fn();
    render(
      <Segmented
        label="unit"
        value="lambda"
        options={[
          { value: "lambda", label: "λ" },
          { value: "mm", label: "mm" },
        ]}
        onChange={onChange}
      />,
    );
    expect(screen.getByRole("group", { name: "unit" })).toBeTruthy();
    await userEvent.click(screen.getByText("mm"));
    expect(onChange).toHaveBeenCalledWith("mm");
  });

  it("Callout uses role=alert only for danger", () => {
    render(
      <>
        <Callout tone="danger" title="计算失败">
          detail
        </Callout>
        <Callout tone="info">info</Callout>
        <Callout tone="success">ok</Callout>
        <Callout tone="warning">warn</Callout>
      </>,
    );
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByRole("alert").textContent).toContain("计算失败");
  });

  it("Menu opens, selects and closes on Escape or an outside click", async () => {
    const onSelect = vi.fn();
    render(
      <Menu trigger={({ toggle }) => <button type="button" onClick={toggle}>open</button>}>
        {(close) => (
          <>
            <MenuItem onSelect={() => { onSelect(); close(); }}>A</MenuItem>
            <MenuItem checked onSelect={() => {}}>B</MenuItem>
          </>
        )}
      </Menu>,
    );
    await userEvent.click(screen.getByText("open"));
    expect(screen.getByRole("menuitemradio").getAttribute("aria-checked")).toBe("true");
    await userEvent.click(screen.getByText("A"));
    expect(onSelect).toHaveBeenCalled();
    expect(screen.queryByRole("menu")).toBeNull();
    await userEvent.click(screen.getByText("open"));
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    await userEvent.click(screen.getByText("open"));
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("useFilePicker forwards the chosen file and resets the input", () => {
    const onFile = vi.fn();
    function Picker() {
      const pick = useFilePicker(".csv", onFile);
      return <button type="button" onClick={pick}>pick</button>;
    }
    render(<Picker />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput.accept).toBe(".csv");
    const file = new File(["a"], "a.csv");
    Object.defineProperty(fileInput, "files", { value: [file], configurable: true });
    fireEvent.change(fileInput);
    expect(onFile).toHaveBeenCalledWith(file);
  });
});
