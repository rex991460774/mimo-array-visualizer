import { ApiError, api, errorMessage } from "../api/client";
import type { ImportResult, Project } from "../api/types";
import { downloadBlob, downloadJson, safeFilename } from "../lib/format";
import { useStore } from "./store";

function store() {
  return useStore.getState();
}

export async function saveProject(asNew = false): Promise<void> {
  const { project, projectId, markSaved, setStatus } = store();
  if (!project) return;
  try {
    let record;
    if (projectId && !asNew) {
      try {
        record = await api.updateProject(projectId, project);
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 404)) throw error;
        record = await api.createProject(project);
      }
    } else {
      record = await api.createProject(project);
    }
    markSaved(record.id, project);
    setStatus("status.saved", "success");
  } catch (error) {
    setStatus("overview.error", "error", undefined, errorMessage(error));
  }
}

export function newProject(): void {
  const { config, replaceProject, setStatus } = store();
  if (!config) return;
  replaceProject(structuredClone(config.default_project), null, false);
  setStatus("status.newProject");
}

export async function openProject(id: string): Promise<void> {
  const { replaceProject, setStatus } = store();
  try {
    const record = await api.getProject(id);
    replaceProject(record.project, record.id, true);
    setStatus("status.opened", "success", { name: record.project.name });
  } catch (error) {
    setStatus("overview.error", "error", undefined, errorMessage(error));
  }
}

/** Drop references to data files the server does not have. */
export function withoutMissingAssets(project: Project, missing: string[]): Project {
  if (missing.length === 0) return project;
  const gone = new Set(missing);
  const dictionary = { ...project.dbf_dictionary };
  if (dictionary.azimuth_asset && gone.has(dictionary.azimuth_asset)) dictionary.azimuth_asset = null;
  if (dictionary.elevation_asset && gone.has(dictionary.elevation_asset)) dictionary.elevation_asset = null;
  if (dictionary.mode === "custom" && !dictionary.azimuth_asset && !dictionary.elevation_asset) dictionary.mode = "ideal";
  return {
    ...project,
    dbf_dictionary: dictionary,
    element_pattern: project.element_pattern && gone.has(project.element_pattern.asset) ? null : project.element_pattern,
    channel_patterns: project.channel_patterns.filter((binding) => !gone.has(binding.asset)),
  };
}

export async function importFile(file: File): Promise<void> {
  const { replaceProject, setStatus } = store();
  try {
    let result: ImportResult;
    if (file.name.toLowerCase().endsWith(".zip")) {
      result = await api.importBundle(file);
    } else {
      let document: unknown;
      try {
        document = JSON.parse(await file.text());
      } catch {
        throw new Error("JSON parse error");
      }
      result = await api.importDocument(document);
    }
    const project = withoutMissingAssets(result.project, result.missing_assets);
    if (!project.name || project.name === "未命名阵列") {
      project.name = file.name.replace(/\.(mimo\.zip|zip|json)$/i, "");
    }
    replaceProject(project, null, false);
    if (result.missing_assets.length > 0) {
      setStatus("status.missingAssets", "error", { count: result.missing_assets.length });
    } else {
      setStatus("status.imported", "success", { name: file.name });
    }
  } catch (error) {
    setStatus("status.importFailed", "error", { message: errorMessage(error) });
  }
}

export async function exportLayout(): Promise<void> {
  const { project, setStatus } = store();
  if (!project) return;
  try {
    const document = await api.exportLayout(project);
    const filename = `${safeFilename(project.name)}.json`;
    downloadJson(document, filename);
    setStatus("status.exported", "success", { name: filename });
  } catch (error) {
    setStatus("overview.error", "error", undefined, errorMessage(error));
  }
}

export async function exportBundle(): Promise<void> {
  const { project, setStatus } = store();
  if (!project) return;
  try {
    const blob = await api.exportBundle(project);
    const filename = `${safeFilename(project.name)}.mimo.zip`;
    downloadBlob(blob, filename);
    setStatus("status.exported", "success", { name: filename });
  } catch (error) {
    setStatus("overview.error", "error", undefined, errorMessage(error));
  }
}
