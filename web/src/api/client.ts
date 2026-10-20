import { translate } from "../i18n";
import { useStore } from "../state/store";
import type {
  AssetInfo,
  BandSweep,
  CompareItem,
  Axis,
  ChannelPatternBinding,
  Dbf2dResult,
  DbfBank,
  DictionaryPreview,
  ElementPatternPreview,
  Evaluation,
  ImportResult,
  Job,
  Layout,
  PatternKind,
  PatternPlane,
  Project,
  ProjectRecord,
  ProjectSummary,
  ReportOptions,
  ShareCreated,
  ShareRecord,
  ServerConfig,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiError("network", 0);
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // keep status text
    }
    throw new ApiError(detail || `HTTP ${response.status}`, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

async function postForBlob(path: string, body: unknown): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("network", 0);
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      // keep status text
    }
    throw new ApiError(detail, response.status);
  }
  return response.blob();
}

function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file, file.name);
  return request<T>(path, { method: "POST", body: form });
}

export const api = {
  config: () => request<ServerConfig>("/api/config"),
  autoLayout: (tx_count: number, rx_count: number) =>
    post<Layout>("/api/layout/auto", { tx_count, rx_count }),
  evaluate: (project: Project, signal?: AbortSignal) =>
    post<Evaluation>("/api/evaluate", { project }, signal),
  band: (project: Project, signal?: AbortSignal) => post<BandSweep>("/api/band", { project }, signal),
  compare: (projects: Project[]) => post<CompareItem[]>("/api/compare", { projects }),
  dbfBank: (project: Project, axis: Axis, signal?: AbortSignal) =>
    post<DbfBank>("/api/dbf/bank", { project, axis }, signal),
  dbf2d: (project: Project, frames: { azimuth: number; elevation: number }[], signal?: AbortSignal) =>
    post<Dbf2dResult>("/api/dbf/2d", { project, frames }, signal),
  uploadAsset: (file: File) => upload<AssetInfo>("/api/assets", file),
  assetInfo: (id: string) => request<AssetInfo>(`/api/assets/${id}`),
  elementPatternPreview: (asset: string, swap_axes: boolean) =>
    post<ElementPatternPreview>("/api/element-pattern/preview", { asset, swap_axes }),
  resolveChannelPatterns: (body: {
    project: Project;
    asset: string;
    kind: PatternKind;
    plane: PatternPlane;
    target: "physical" | "virtual";
    channel?: string | null;
  }) => post<ChannelPatternBinding[]>("/api/channel-patterns/resolve", body),
  dictionaryPreview: (project: Project, axis: Axis, signal?: AbortSignal) =>
    post<DictionaryPreview>("/api/dictionary/preview", { project, axis }, signal),
  importDocument: (document: unknown) => post<ImportResult>("/api/import/document", { document }),
  importBundle: (file: File) => upload<ImportResult>("/api/import/bundle", file),
  exportLayout: (project: Project) => post<Record<string, unknown>>("/api/export/layout", { project }),
  exportBundle: (project: Project) => postForBlob("/api/export/bundle", { project }),
  listProjects: () => request<ProjectSummary[]>("/api/projects"),
  getProject: (id: string) => request<ProjectRecord>(`/api/projects/${id}`),
  createProject: (project: Project) => post<ProjectRecord>("/api/projects", { project }),
  /** Without baseRevision the stored project is overwritten unconditionally. */
  updateProject: (id: string, project: Project, baseRevision?: number) =>
    request<ProjectRecord>(`/api/projects/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, base_revision: baseRevision ?? null }),
    }),
  deleteProject: (id: string) => request<void>(`/api/projects/${id}`, { method: "DELETE" }),
  createShare: (project: Project) => post<ShareCreated>("/api/shares", { project }),
  getShare: (id: string) => request<ShareRecord>(`/api/shares/${encodeURIComponent(id)}`),
  createReport: (project: Project, options: ReportOptions) =>
    post<Job>("/api/reports", { project, options }),
  createAngleErrorImage: (project: Project, error_limit_deg: number, language: string) =>
    post<Job>("/api/angle-error-image", { project, error_limit_deg, language }),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  cancelJob: (id: string) => post<Job>(`/api/jobs/${id}/cancel`, {}),
  jobDownloadUrl: (id: string) => `/api/jobs/${id}/download`,
};

export function errorMessage(error: unknown): string {
  // Status 0 means the request never reached the server (stopped, restarting, offline).
  if (error instanceof ApiError && error.status === 0) return translate(useStore.getState().language, "app.offline");
  if (error instanceof ApiError && error.status === 507) return translate(useStore.getState().language, "app.storageError");
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return String(error);
}
