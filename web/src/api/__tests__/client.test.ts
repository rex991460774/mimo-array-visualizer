import { beforeEach, describe, expect, it, vi } from "vitest";
import { jsonResponse, project, resetStore } from "../../__tests__/fixtures";
import { useStore } from "../../state/store";
import { ApiError, api, errorMessage } from "../client";

const fetchMock = vi.fn<typeof fetch>();
beforeEach(() => {
  resetStore();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

async function rejection(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    return error as ApiError;
  }
  throw new Error("expected the request to fail");
}

describe("request error mapping", () => {
  it("returns parsed JSON on success", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ version: "1.0.0" }));
    await expect(api.config()).resolves.toEqual({ version: "1.0.0" });
    expect(fetchMock).toHaveBeenCalledWith("/api/config", {});
  });

  it("returns undefined for 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(api.deleteProject("x")).resolves.toBeUndefined();
  });

  it.each([
    [409, "Project was saved by someone else at T (revision 2); your copy is based on revision 1."],
    [413, "Request body exceeds 16 MB."],
    [422, "无法读取 XLSX/XLSM 文件（文件已损坏或不是 Excel 工作簿）：x.xlsx"],
    [507, "The server cannot write to its data directory (disk full or not writable)."],
  ])("HTTP %d keeps the server's detail and status", async (status, detail) => {
    fetchMock.mockImplementation(async () => jsonResponse({ detail }, status));
    const error = await rejection(api.listProjects());
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(status);
    expect(error.message).toBe(detail);
  });

  it("falls back to the status text when the body is not JSON", async () => {
    fetchMock.mockResolvedValue(new Response("Internal Server Error", { status: 500, statusText: "Internal Server Error" }));
    const error = await rejection(api.listProjects());
    expect(error.message).toBe("Internal Server Error");
    expect(error.status).toBe(500);
  });

  it("falls back to HTTP <status> when there is neither detail nor status text", async () => {
    fetchMock.mockResolvedValue(new Response("", { status: 502 }));
    expect((await rejection(api.listProjects())).message).toBe("HTTP 502");
  });

  it("joins the messages of a FastAPI validation array instead of dropping them", async () => {
    fetchMock.mockImplementation(async () =>
      jsonResponse({ detail: [{ msg: "bad" }, { msg: "worse" }, { loc: ["x"] }] }, 422, "Unprocessable Entity"),
    );
    expect((await rejection(api.listProjects())).message).toBe("bad; worse");
  });

  it("falls back to the status text for an unusable detail", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ detail: { nested: true } }, 422, "Unprocessable Entity"));
    expect((await rejection(api.listProjects())).message).toBe("Unprocessable Entity");
  });

  it("maps a failed fetch (server down) to status 0", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await rejection(api.config());
    expect(error).toMatchObject({ status: 0, message: "network" });
  });

  it("re-throws AbortError unchanged so callers can ignore it", async () => {
    const abort = new DOMException("aborted", "AbortError");
    fetchMock.mockRejectedValue(abort);
    await expect(api.evaluate(project())).rejects.toBe(abort);
  });
});

describe("request shapes", () => {
  it("updateProject sends base_revision, or null to overwrite", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ id: "p", revision: 2 }));
    const p = project();
    await api.updateProject("p", p, 1);
    await api.updateProject("p", p);
    const bodies = fetchMock.mock.calls.map(([, init]) => JSON.parse(init!.body as string));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/projects/p");
    expect(fetchMock.mock.calls[0][1]!.method).toBe("PUT");
    expect(bodies[0].base_revision).toBe(1);
    expect(bodies[1].base_revision).toBeNull();
  });

  it("post sends JSON with the abort signal", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({}));
    const controller = new AbortController();
    await api.evaluate(project(), controller.signal);
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/evaluate");
    expect(init).toMatchObject({ method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal });
    expect(JSON.parse(init!.body as string).project.name).toBe(project().name);
  });

  it("uploads use multipart form data with the file name", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ id: "a" }));
    await api.uploadAsset(new File(["theta,gain\n0,0\n"], "p.csv"));
    const body = fetchMock.mock.calls[0][1]!.body as FormData;
    expect((body.get("file") as File).name).toBe("p.csv");
  });

  it("share ids are URL-encoded", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({}));
    await api.getShare("../x");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/shares/..%2Fx");
  });

  it("jobDownloadUrl is a plain path", () => {
    expect(api.jobDownloadUrl("j1")).toBe("/api/jobs/j1/download");
  });
});

describe("exportBundle (blob responses)", () => {
  it("returns the blob on success", async () => {
    fetchMock.mockResolvedValue(new Response("PK", { status: 200 }));
    const blob = await api.exportBundle(project());
    expect(blob.size).toBe(2);
  });

  it("maps network failure to status 0", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    expect((await rejection(api.exportBundle(project()))).status).toBe(0);
  });

  it("keeps a string detail on HTTP errors", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ detail: "Asset not found: 'x'" }, 404));
    const error = await rejection(api.exportBundle(project()));
    expect(error).toMatchObject({ status: 404, message: "Asset not found: 'x'" });
  });

  // Regression R5-1: postForBlob parsed `detail` without request()'s type check,
  // so exportBundle showed "[object Object]" for a FastAPI 422 array.
  it("a non-string detail never becomes \"[object Object]\"", async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ detail: [{ msg: "bad" }] }, 422, "Unprocessable Entity"));
    const error = await rejection(api.exportBundle(project()));
    expect(error.message).toBe("bad");
    fetchMock.mockImplementation(async () => jsonResponse({ detail: { nested: true } }, 422, "Unprocessable Entity"));
    expect((await rejection(api.exportBundle(project()))).message).toBe("Unprocessable Entity");
  });
});

describe("errorMessage localisation", () => {
  it.each([
    ["zh", "无法连接到服务器"],
    ["en", "server"],
    ["ja", "サーバー"],
  ] as const)("status 0 (offline) is translated [%s] (round 3 R3-5)", (language, fragment) => {
    useStore.setState({ language });
    const text = errorMessage(new ApiError("network", 0));
    expect(text).not.toBe("network");
    expect(text).toContain(fragment);
  });

  it("507 maps to the localised storage message", () => {
    expect(errorMessage(new ApiError("The server cannot write…", 507))).toContain("磁盘已满");
    useStore.setState({ language: "en" });
    expect(errorMessage(new ApiError("x", 507))).toContain("disk full");
  });

  it("429 maps to the localised busy message", () => {
    expect(errorMessage(new ApiError("The server is busy…", 429))).toContain("其他导出任务");
    useStore.setState({ language: "en" });
    expect(errorMessage(new ApiError("x", 429))).toContain("busy with other exports");
  });

  it("other ApiErrors and plain errors pass their message through", () => {
    expect(errorMessage(new ApiError("Request body exceeds 16 MB.", 413))).toBe("Request body exceeds 16 MB.");
    expect(errorMessage(new Error("JSON parse error"))).toBe("JSON parse error");
    expect(errorMessage("text")).toBe("text");
  });

  it("never leaks internal exception class names (round 3 R3-6)", () => {
    const text = errorMessage(new ApiError("无法读取 XLSX/XLSM 文件（文件已损坏或结构不完整）：x.xlsx", 422));
    expect(text).not.toMatch(/KeyError|BadZipFile|Traceback/);
  });
});
