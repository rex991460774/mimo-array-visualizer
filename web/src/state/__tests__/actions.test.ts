import { beforeEach, describe, expect, it, vi } from "vitest";
import { jsonResponse, project, resetStore } from "../../__tests__/fixtures";
import {
  exportBundle,
  exportLayout,
  importFile,
  newProject,
  openProject,
  openShareFromLocation,
  saveProject,
  shareUrl,
  withoutMissingAssets,
} from "../actions";
import { projectSnapshot, useStore } from "../store";

const s = () => useStore.getState();
const fetchMock = vi.fn<typeof fetch>();
const ID = "c".repeat(32);

function record(revision: number, overrides = {}) {
  return { id: ID, created_at: "2026-10-20T16:00:00+00:00", updated_at: "2026-10-20T16:30:00+00:00", revision, project: s().project, ...overrides };
}

beforeEach(() => {
  resetStore();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("saveProject", () => {
  it("creates a new library project and marks it saved", async () => {
    fetchMock.mockImplementation(async () => jsonResponse(record(1)));
    await saveProject();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/projects");
    expect(s()).toMatchObject({ projectId: ID, projectRevision: 1, savedSnapshot: projectSnapshot(s().project!) });
    expect(s().status).toMatchObject({ key: "status.saved", tone: "success" });
  });

  it("updates with the revision the copy is based on", async () => {
    useStore.setState({ projectId: ID, projectRevision: 4 });
    fetchMock.mockImplementation(async () => jsonResponse(record(5)));
    await saveProject();
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe(`/api/projects/${ID}`);
    expect(JSON.parse(init!.body as string).base_revision).toBe(4);
    expect(s().projectRevision).toBe(5);
  });

  it("409 opens the conflict dialog and writes nothing", async () => {
    useStore.setState({ projectId: ID, projectRevision: 1 });
    fetchMock.mockImplementation(async () => jsonResponse({ detail: "Project was saved by someone else" }, 409));
    await saveProject();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(s().dialog).toBe("saveConflict");
    expect(s().status).toMatchObject({ key: "conflict.status", tone: "error" });
    expect(s().projectRevision).toBe(1);
    expect(s().savedSnapshot).toBeNull();
  });

  it("overwrite sends no base revision", async () => {
    useStore.setState({ projectId: ID, projectRevision: 1 });
    fetchMock.mockImplementation(async () => jsonResponse(record(3)));
    await saveProject(false, true);
    expect(JSON.parse(fetchMock.mock.calls[0][1]!.body as string).base_revision).toBeNull();
  });

  it("asNew always creates", async () => {
    useStore.setState({ projectId: ID, projectRevision: 1 });
    fetchMock.mockImplementation(async () => jsonResponse(record(1, { id: "d".repeat(32) })));
    await saveProject(true);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/projects");
    expect(s().projectId).toBe("d".repeat(32));
  });

  it("a project deleted on the server (404) is recreated", async () => {
    useStore.setState({ projectId: ID, projectRevision: 1 });
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: "Project not found." }, 404))
      .mockResolvedValueOnce(jsonResponse(record(1, { id: "e".repeat(32) })));
    await saveProject();
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([`/api/projects/${ID}`, "/api/projects"]);
    expect(s().projectId).toBe("e".repeat(32));
  });

  it.each([
    [507, { detail: "cannot write" }, "磁盘已满"],
    [413, { detail: "Request body exceeds 16 MB." }, "Request body exceeds 16 MB."],
  ])("HTTP %d is reported with a readable detail", async (status, body, fragment) => {
    fetchMock.mockImplementation(async () => jsonResponse(body, status));
    await saveProject();
    expect(s().status).toMatchObject({ key: "overview.error", tone: "error" });
    expect(s().status!.detail).toContain(fragment);
    expect(s().projectId).toBeNull();
  });

  it("server down is reported with the offline message", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await saveProject();
    expect(s().status!.detail).toContain("无法连接到服务器");
  });
});

describe("open / new", () => {
  it("openProject loads the record with its revision", async () => {
    const p = project({ name: "Remote" });
    fetchMock.mockImplementation(async () => jsonResponse({ ...record(6), project: p }));
    await openProject(ID);
    expect(s()).toMatchObject({ projectId: ID, projectRevision: 6 });
    expect(s().project!.name).toBe("Remote");
    expect(s().status).toMatchObject({ key: "status.opened", params: { name: "Remote" } });
  });

  it("openProject failure keeps the current project", async () => {
    const before = s().project;
    fetchMock.mockImplementation(async () => jsonResponse({ detail: "Project not found." }, 404));
    await openProject(ID);
    expect(s().project).toBe(before);
    expect(s().status!.detail).toBe("Project not found.");
  });

  it("newProject restores the server default", () => {
    s().updateProject({ name: "edited" });
    newProject();
    expect(s().project).toEqual(project());
    expect(s().status!.key).toBe("status.newProject");
  });
});

describe("withoutMissingAssets", () => {
  const withAssets = () =>
    project({
      dbf_dictionary: { ...project().dbf_dictionary, mode: "custom", azimuth_asset: "A", elevation_asset: "B" },
      element_pattern: { asset: "E", swap_axes: false } as never,
      channel_patterns: [
        { channel: "Tx1", kind: "phase", plane: "horizontal", asset: "C", column_index: 0, column: "c" },
        { channel: "Tx2", kind: "phase", plane: "horizontal", asset: "D", column_index: 1, column: "d" },
      ],
    });

  it("returns the same object when nothing is missing", () => {
    const p = withAssets();
    expect(withoutMissingAssets(p, [])).toBe(p);
  });

  it("drops each missing reference and falls back to the ideal dictionary", () => {
    const result = withoutMissingAssets(withAssets(), ["A", "B", "E", "C"]);
    expect(result.dbf_dictionary).toMatchObject({ mode: "ideal", azimuth_asset: null, elevation_asset: null });
    expect(result.element_pattern).toBeNull();
    expect(result.channel_patterns.map((b) => b.asset)).toEqual(["D"]);
  });

  it("keeps custom mode while one dictionary file remains", () => {
    const result = withoutMissingAssets(withAssets(), ["A"]);
    expect(result.dbf_dictionary).toMatchObject({ mode: "custom", azimuth_asset: null, elevation_asset: "B" });
  });
});

describe("importFile", () => {
  it("imports a layout JSON and names the project after the file", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ project: project({ name: "" }), missing_assets: [] }));
    await importFile(new File(['{"tx":[]}'], "ti.json"));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/import/document");
    expect(s().project!.name).toBe("ti");
    expect(s().status).toMatchObject({ key: "status.imported", tone: "success" });
  });

  it("imports a .mimo.zip bundle through the bundle endpoint", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ project: project({ name: "未命名阵列" }), missing_assets: ["X"] }));
    await importFile(new File(["PK"], "case.mimo.zip"));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/import/bundle");
    expect(s().project!.name).toBe("case");
    expect(s().status).toMatchObject({ key: "status.missingAssets", params: { count: 1 } });
  });

  it("broken JSON never reaches the server", async () => {
    await importFile(new File(["{not json"], "broken.json"));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(s().status).toMatchObject({ key: "status.importFailed", params: { message: "JSON parse error" } });
  });

  it("a rejected zip bomb shows the server's reason (round 2 N1)", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ detail: "Bundle contents are too large." }, 422));
    const before = s().project;
    await importFile(new File(["PK"], "bomb.zip"));
    expect(s().project).toBe(before);
    expect(s().status!.params!.message).toBe("Bundle contents are too large.");
  });
});

describe("exports and shares", () => {
  beforeEach(() => {
    Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => {} });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  it("exportLayout downloads <name>.json with a safe file name", async () => {
    s().updateProject({ name: "a/b" });
    fetchMock.mockImplementation(async () => jsonResponse({ tx: [] }));
    await exportLayout();
    expect(s().status).toMatchObject({ key: "status.exported", params: { name: "a_b.json" } });
  });

  it("exportBundle failure is reported", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ detail: "Asset not found: 'x'" }, 404));
    await exportBundle();
    expect(s().status).toMatchObject({ key: "overview.error", detail: "Asset not found: 'x'" });
  });

  it("exportBundle downloads <name>.mimo.zip", async () => {
    fetchMock.mockResolvedValue(new Response("PK"));
    await exportBundle();
    expect(s().status!.params!.name).toBe(`${project().name}.mimo.zip`);
  });

  it("shareUrl uses the page origin", () => {
    expect(shareUrl("AbCdEfGhIjKl")).toBe(`${window.location.origin}/s/AbCdEfGhIjKl`);
  });

  it("openShareFromLocation loads /s/<id> and clears the path", async () => {
    window.history.replaceState(null, "", "/s/AbCdEfGhIjKl");
    fetchMock.mockImplementation(async () => jsonResponse({ project: project({ name: "Shared" }), missing_assets: [] }));
    await openShareFromLocation();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/shares/AbCdEfGhIjKl");
    expect(window.location.pathname).toBe("/");
    expect(s().project!.name).toBe("Shared");
    expect(s().status!.key).toBe("share.opened");
  });

  it("ignores paths that are not share links", async () => {
    window.history.replaceState(null, "", "/s/short");
    await openShareFromLocation();
    expect(fetchMock).not.toHaveBeenCalled();
    window.history.replaceState(null, "", "/");
  });

  it("asks before replacing unsaved edits and keeps them when declined", async () => {
    s().updateProject({ name: "my unsaved work" });
    window.history.replaceState(null, "", "/s/AbCdEfGhIjKl");
    fetchMock.mockImplementation(async () => jsonResponse({ project: project({ name: "Shared" }), missing_assets: [] }));
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    await openShareFromLocation();
    expect(confirm).toHaveBeenCalled();
    expect(s().project!.name).toBe("my unsaved work");
  });

  it("an unknown share id reports share.notFound", async () => {
    window.history.replaceState(null, "", "/s/AbCdEfGhIjKl");
    fetchMock.mockImplementation(async () => jsonResponse({ detail: "Share link not found." }, 404));
    await openShareFromLocation();
    expect(s().status).toMatchObject({ key: "share.notFound", detail: "Share link not found." });
  });
});
