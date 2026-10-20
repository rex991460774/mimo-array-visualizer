import { create } from "zustand";
import type { Evaluation, Layout, Project, ServerConfig } from "../api/types";
import { type ElementRef, layoutsEqual, renumber } from "../lib/geometry";
import type { MessageKey } from "../i18n/messages";

export type ViewId = "array" | "dbf1d" | "dbf2d" | "angle" | "band";
export type Language = "zh" | "en" | "ja";
export type ThemeMode = "system" | "light" | "dark";
export type DisplayMode = "db" | "magnitude";
export type CoordUnit = "lambda" | "mm";
export type DialogId = "dictionary" | "patterns" | "report" | "projects" | "help" | "settings" | "share" | "saveConflict" | null;

export interface StatusMessage {
  key: MessageKey;
  params?: Record<string, string | number>;
  tone: "info" | "success" | "error";
  /** Free text that does not come from the message catalogue (server errors). */
  detail?: string;
  at: number;
}

const MAX_HISTORY = 50;
const STORAGE_KEY = "mimo-array-workbench:v1";

interface PersistedState {
  project: Project;
  projectId: string | null;
  projectRevision: number | null;
  savedSnapshot: string | null;
  language: Language;
  theme: ThemeMode;
  display: DisplayMode;
  view: ViewId;
  coordUnit: CoordUnit;
}

function readPersisted(): Partial<PersistedState> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Partial<PersistedState>) : {};
  } catch {
    return {};
  }
}

function writePersisted(state: PersistedState): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // storage unavailable (private mode / quota): the session still works
  }
}

function detectLanguage(): Language {
  const lang = (navigator.language || "zh").toLowerCase();
  if (lang.startsWith("ja")) return "ja";
  if (lang.startsWith("en")) return "en";
  return "zh";
}

function withDefaults(draft: Project, defaults: Project): Project {
  return {
    ...defaults,
    ...draft,
    band: draft.band ?? defaults.band,
    fov: draft.fov ?? defaults.fov,
    grid_step_lambda: draft.grid_step_lambda ?? defaults.grid_step_lambda,
    requirements: { ...defaults.requirements, ...(draft.requirements ?? {}) },
  };
}

function layoutWithin(layout: Layout, limit: number): boolean {
  return [...layout.tx, ...layout.rx].every(
    (point) => Number.isFinite(point.x) && Number.isFinite(point.y) && Math.abs(point.x) <= limit && Math.abs(point.y) <= limit,
  );
}

export function projectSnapshot(project: Project): string {
  return JSON.stringify(project);
}

interface AppState {
  config: ServerConfig | null;
  project: Project | null;
  projectId: string | null;
  /** Library revision the current project was loaded from or last saved as. */
  projectRevision: number | null;
  savedSnapshot: string | null;
  past: Layout[];
  future: Layout[];
  selection: ElementRef | null;
  deleteMode: boolean;
  view: ViewId;
  dialog: DialogId;
  language: Language;
  theme: ThemeMode;
  display: DisplayMode;
  coordUnit: CoordUnit;
  status: StatusMessage | null;
  evaluation: Evaluation | null;
  evaluationError: string | null;
  evaluating: boolean;

  initialize(config: ServerConfig): void;
  setStatus(key: MessageKey, tone?: StatusMessage["tone"], params?: StatusMessage["params"], detail?: string): void;
  updateProject(update: Partial<Project>): void;
  replaceProject(project: Project, projectId: string | null, saved: boolean, revision?: number | null): void;
  markSaved(projectId: string, project: Project, revision: number): void;
  commitLayout(layout: Layout, selection?: ElementRef | null): void;
  undo(): void;
  redo(): void;
  select(selection: ElementRef | null): void;
  setDeleteMode(on: boolean): void;
  setView(view: ViewId): void;
  openDialog(dialog: DialogId): void;
  setLanguage(language: Language): void;
  setTheme(theme: ThemeMode): void;
  setDisplay(display: DisplayMode): void;
  setCoordUnit(unit: CoordUnit): void;
  setEvaluation(evaluation: Evaluation | null, error: string | null): void;
  setEvaluating(evaluating: boolean): void;
}

const persisted = typeof window === "undefined" ? {} : readPersisted();

export const useStore = create<AppState>((set, get) => ({
  config: null,
  project: null,
  projectId: persisted.projectId ?? null,
  projectRevision: persisted.projectRevision ?? null,
  savedSnapshot: persisted.savedSnapshot ?? null,
  past: [],
  future: [],
  selection: null,
  deleteMode: false,
  view: persisted.view ?? "array",
  dialog: null,
  language: persisted.language ?? (typeof navigator === "undefined" ? "zh" : detectLanguage()),
  theme: persisted.theme ?? "system",
  display: persisted.display ?? "db",
  coordUnit: persisted.coordUnit ?? "lambda",
  status: null,
  evaluation: null,
  evaluationError: null,
  evaluating: false,

  initialize(config) {
    const draft = persisted.project;
    const usable = draft && draft.version === 2 && draft.layout;
    // Drafts saved before bands/FOV existed: fill new fields from the defaults.
    const project = usable ? withDefaults(draft, config.default_project) : config.default_project;
    set({ config, project });
  },

  setStatus(key, tone = "info", params, detail) {
    set({ status: { key, tone, params, detail, at: Date.now() } });
  },

  updateProject(update) {
    const project = get().project;
    if (!project) return;
    set({ project: { ...project, ...update } });
  },

  replaceProject(project, projectId, saved, revision = null) {
    set({
      project,
      projectId,
      projectRevision: projectId ? revision : null,
      savedSnapshot: saved ? projectSnapshot(project) : null,
      past: [],
      future: [],
      selection: null,
      deleteMode: false,
      evaluation: null,
      evaluationError: null,
    });
  },

  markSaved(projectId, project, revision) {
    set({ projectId, projectRevision: revision, savedSnapshot: projectSnapshot(project) });
  },

  commitLayout(layout, selection) {
    const { project, past, selection: current, config } = get();
    if (!project) return;
    // Every edit path (drag, keys, table, inspector) ends here: refuse layouts
    // the server would reject instead of showing metrics for an invalid array.
    const limit = config?.limits.coordinate_lambda;
    if (limit !== undefined && !layoutWithin(layout, limit)) {
      get().setStatus("physical.outOfRange", "error", { limit });
      return;
    }
    const ordered = renumber(layout, selection === undefined ? current : selection);
    if (layoutsEqual(ordered.layout, project.layout)) {
      set({ selection: ordered.follow });
      return;
    }
    set({
      project: { ...project, layout: ordered.layout },
      past: [...past, project.layout].slice(-MAX_HISTORY),
      future: [],
      selection: ordered.follow,
    });
  },

  undo() {
    const { project, past, future } = get();
    if (!project || past.length === 0) {
      get().setStatus("status.nothingToUndo");
      return;
    }
    const previous = past[past.length - 1];
    set({
      project: { ...project, layout: previous },
      past: past.slice(0, -1),
      future: [project.layout, ...future].slice(0, MAX_HISTORY),
      selection: null,
    });
    get().setStatus("status.undo");
  },

  redo() {
    const { project, past, future } = get();
    if (!project || future.length === 0) {
      get().setStatus("status.nothingToRedo");
      return;
    }
    const [next, ...rest] = future;
    set({
      project: { ...project, layout: next },
      past: [...past, project.layout].slice(-MAX_HISTORY),
      future: rest,
      selection: null,
    });
    get().setStatus("status.redo");
  },

  select(selection) {
    set({ selection });
  },
  setDeleteMode(on) {
    set({ deleteMode: on, selection: on ? null : get().selection });
  },
  setView(view) {
    set({ view });
  },
  openDialog(dialog) {
    set({ dialog });
  },
  setLanguage(language) {
    set({ language });
  },
  setTheme(theme) {
    set({ theme });
  },
  setDisplay(display) {
    set({ display });
  },
  setCoordUnit(coordUnit) {
    set({ coordUnit });
  },
  setEvaluation(evaluation, error) {
    set({ evaluation, evaluationError: error });
  },
  setEvaluating(evaluating) {
    set({ evaluating });
  },
}));

// Persist the working draft and preferences so a browser reload keeps the session.
useStore.subscribe((state) => {
  if (!state.project) return;
  writePersisted({
    project: state.project,
    projectId: state.projectId,
    projectRevision: state.projectRevision,
    savedSnapshot: state.savedSnapshot,
    language: state.language,
    theme: state.theme,
    display: state.display,
    view: state.view,
    coordUnit: state.coordUnit,
  });
});

export function useIsDirty(): boolean {
  return useStore((state) =>
    state.project ? state.savedSnapshot !== projectSnapshot(state.project) : false,
  );
}
