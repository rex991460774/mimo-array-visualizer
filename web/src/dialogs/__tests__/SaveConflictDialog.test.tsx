import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { jsonResponse, resetStore } from "../../__tests__/fixtures";
import { useStore } from "../../state/store";
import { SaveConflictDialog } from "../SaveConflictDialog";

const ID = "f".repeat(32);
const fetchMock = vi.fn<typeof fetch>();
const s = () => useStore.getState();

function stored(revision: number, id = ID) {
  return { id, created_at: "2026-10-20T15:00:00+00:00", updated_at: "2026-10-20T16:30:00+00:00", revision, project: s().project };
}

beforeEach(() => {
  resetStore();
  useStore.setState({ projectId: ID, projectRevision: 1, dialog: "saveConflict" });
  s().updateProject({ name: "Case4" });
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

function open() {
  const onClose = vi.fn(() => s().openDialog(null));
  render(<SaveConflictDialog onClose={onClose} />);
  return onClose;
}

describe("SaveConflictDialog", () => {
  it("names the project and shows when the other copy was saved", async () => {
    fetchMock.mockImplementation(async () => jsonResponse(stored(2)));
    open();
    expect(screen.getByRole("dialog", { name: "项目已被他人修改" })).toBeTruthy();
    expect(screen.getByText(/「Case4」/)).toBeTruthy();
    await waitFor(() => expect(screen.getByText(/「Case4」/).textContent).not.toContain("—"));
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/projects/${ID}`);
  });

  it("shows — when the stored time cannot be loaded", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    open();
    await Promise.resolve();
    expect(screen.getByText(/「Case4」/).textContent).toContain("—");
  });

  it("is localised", () => {
    useStore.setState({ language: "en" });
    fetchMock.mockImplementation(async () => jsonResponse(stored(2)));
    open();
    expect(screen.getByRole("dialog", { name: "Project changed by someone else" })).toBeTruthy();
  });

  it("cancel closes without saving", async () => {
    fetchMock.mockImplementation(async () => jsonResponse(stored(2)));
    const onClose = open();
    await userEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(onClose).toHaveBeenCalled();
    expect(fetchMock.mock.calls.every(([, init]) => !init?.method)).toBe(true);
  });

  it("overwrite saves without a base revision", async () => {
    fetchMock.mockImplementation(async (_path, init) => jsonResponse(init?.method === "PUT" ? stored(3) : stored(2)));
    open();
    await userEvent.click(screen.getByRole("button", { name: /覆盖对方的修改/ }));
    await waitFor(() => expect(s().projectRevision).toBe(3));
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT")!;
    expect(JSON.parse(put[1]!.body as string).base_revision).toBeNull();
    expect(s().status?.key).toBe("status.saved");
  });

  it("save as new creates a copy with the localised suffix", async () => {
    const NEW = "1".repeat(32);
    fetchMock.mockImplementation(async (_path, init) => jsonResponse(init?.method === "POST" ? stored(1, NEW) : stored(2)));
    open();
    await userEvent.click(screen.getByRole("button", { name: /另存为新项目/ }));
    await waitFor(() => expect(s().projectId).toBe(NEW));
    expect(s().project!.name).toBe("Case4（副本）");
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")!;
    expect(post[0]).toBe("/api/projects");
  });

  // Defect R5-3: "save as new" renames the working copy before saving
  // (SaveConflictDialog.tsx:62) and never undoes it, so a failed save still
  // leaves the project renamed to "…（副本）" and each retry appends another suffix.
  it.fails("a failed 'save as new' leaves the project name unchanged", async () => {
    fetchMock.mockImplementation(async (_path, init) =>
      init?.method === "POST" ? jsonResponse({ detail: "cannot write" }, 507) : jsonResponse(stored(2)),
    );
    open();
    await userEvent.click(screen.getByRole("button", { name: /另存为新项目/ }));
    await waitFor(() => expect(s().status?.key).toBe("overview.error"));
    expect(s().project!.name).toBe("Case4");
  });
});
