import { ApiError, api, errorMessage } from "../api/client";
import type { ImportResult, Project } from "../api/types";
import { translate } from "../i18n";
import { downloadBlob, downloadJson, safeFilename } from "../lib/format";
import { projectSnapshot, useStore } from "./store";

function store() {
  return useStore.getState();
}

/**
 * Save to the shared library. Updates send the revision this copy is based on;
 * if someone else saved in between, nothing is written and the conflict dialog
 * asks whether to save as a new project or overwrite (`overwrite = true`).
 */
export async function saveProject(asNew = false, overwrite = false, name?: string): Promise<void> {
  const { project: current, projectId, projectRevision, markSaved, setStatus, openDialog, updateProject } = store();
  if (!current) return;
  // A new name (e.g. "… (copy)") is applied only once the save succeeds, so a
  // failed or retried save neither renames the project nor stacks suffixes.
  const project = name === undefined ? current : { ...current, name };
  try {
    let record;
    if (projectId && !asNew) {
      try {
        record = await api.updateProject(projectId, project, overwrite ? undefined : (projectRevision ?? undefined));
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          setStatus("conflict.status", "error");
          openDialog("saveConflict");
          return;
        }
        if (!(error instanceof ApiError && error.status === 404)) throw error;
        record = await api.createProject(project);
      }
    } else {
      record = await api.createProject(project);
    }
    if (name !== undefined) updateProject({ name });
    markSaved(record.id, project, record.revision);
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
    replaceProject(record.project, record.id, true, record.revision);
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

const SHARE_PATH = /^\/s\/([0-9A-Za-z]{12})\/?$/;

/** Absolute share-link URL for an ID on this server. */
export function shareUrl(id: string): string {
  return `${window.location.origin}/s/${id}`;
}

/**
 * Open the configuration behind a `/s/<id>` link. The path is dropped right
 * away so a reload keeps the recipient's own edits instead of re-opening the
 * snapshot.
 */
export async function openShareFromLocation(): Promise<void> {
  const match = SHARE_PATH.exec(window.location.pathname);
  if (!match) return;
  window.history.replaceState(null, "", "/");
  const { project, savedSnapshot, config, language, replaceProject, setView, setStatus } = store();
  try {
    const record = await api.getShare(match[1]);
    const shared = withoutMissingAssets(record.project, record.missing_assets);
    if (project && config) {
      const current = projectSnapshot(project);
      const unsaved = current !== savedSnapshot && current !== projectSnapshot(config.default_project);
      if (unsaved && current !== projectSnapshot(shared) && !window.confirm(translate(language, "share.confirmReplace"))) {
        return;
      }
    }
    replaceProject(shared, null, false);
    setView("array");
    if (record.missing_assets.length > 0) {
      setStatus("status.missingAssets", "error", { count: record.missing_assets.length });
    } else {
      setStatus("share.opened", "success", { name: shared.name });
    }
  } catch (error) {
    setStatus("share.notFound", "error", undefined, errorMessage(error));
  }
}
