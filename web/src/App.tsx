import { RefreshCw } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import { ControlBar, StatusBar, TopBar } from "./components/Chrome";
import { Overview } from "./components/Overview";
import { Button, Spinner, useFilePicker } from "./components/ui";
import { translate, useT } from "./i18n";
import { exportLayout, importFile, saveProject } from "./state/actions";
import { useEvaluationSync } from "./state/compute";
import { type ThemeMode, useStore, type ViewId } from "./state/store";
import { ArrayView } from "./views/ArrayView";

const DbfView = lazy(() => import("./views/DbfView").then((m) => ({ default: m.DbfView })));
const Dbf2dView = lazy(() => import("./views/Dbf2dView").then((m) => ({ default: m.Dbf2dView })));
const AngleView = lazy(() => import("./views/AngleView").then((m) => ({ default: m.AngleView })));
const DictionaryDialog = lazy(() => import("./dialogs/DictionaryDialog").then((m) => ({ default: m.DictionaryDialog })));
const PatternsDialog = lazy(() => import("./dialogs/PatternsDialog").then((m) => ({ default: m.PatternsDialog })));
const ReportDialog = lazy(() => import("./dialogs/ReportDialog").then((m) => ({ default: m.ReportDialog })));
const ProjectsDialog = lazy(() => import("./dialogs/ProjectsDialog").then((m) => ({ default: m.ProjectsDialog })));
const HelpDialog = lazy(() => import("./dialogs/HelpDialog").then((m) => ({ default: m.HelpDialog })));

const VIEW_KEYS: Record<string, ViewId> = { "1": "array", "2": "dbf1d", "3": "dbf2d", "4": "angle" };

function useThemeAttribute(theme: ThemeMode) {
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
  }, [theme]);
}

function isTextInput(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (!element) return false;
  const tag = element.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || element.isContentEditable;
}

function useShortcuts(pickImport: () => void) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const state = useStore.getState();
      if (state.dialog) return;
      const mod = event.ctrlKey || event.metaKey;
      const key = event.key.toLowerCase();
      if (mod && key === "s") {
        event.preventDefault();
        saveProject();
        return;
      }
      if (mod && key === "o") {
        event.preventDefault();
        pickImport();
        return;
      }
      if (mod && key === "e") {
        event.preventDefault();
        exportLayout();
        return;
      }
      if (isTextInput(event.target)) return;
      if (mod && key === "z" && !event.shiftKey) {
        event.preventDefault();
        state.undo();
      } else if (mod && (key === "y" || (key === "z" && event.shiftKey))) {
        event.preventDefault();
        state.redo();
      } else if (!mod && !event.altKey && VIEW_KEYS[event.key]) {
        state.setView(VIEW_KEYS[event.key]);
      } else if ((event.key === "Delete" || event.key === "Backspace") && state.view === "array") {
        const { selection, project } = state;
        if (!selection || !project) {
          if (event.key === "Delete") state.setDeleteMode(!state.deleteMode);
          return;
        }
        if (project.layout[selection.kind].length <= 1) {
          state.setStatus("physical.lastElement", "error", { kind: selection.kind === "tx" ? "Tx" : "Rx" });
          return;
        }
        const name = `${selection.kind === "tx" ? "Tx" : "Rx"}${selection.index + 1}`;
        state.commitLayout(
          { ...project.layout, [selection.kind]: project.layout[selection.kind].filter((_, i) => i !== selection.index) },
          null,
        );
        state.setStatus("status.deleted", "success", { name });
      } else if (event.key === "Escape") {
        if (state.deleteMode) state.setDeleteMode(false);
        else if (state.selection) state.select(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pickImport]);
}

function Boot({ onReady }: { onReady: () => void }) {
  const language = useStore((state) => state.language);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => {
    setFailed(false);
    api.config().then(
      (config) => {
        useStore.getState().initialize(config);
        onReady();
      },
      () => setFailed(true),
    );
  }, [onReady]);
  useEffect(load, [load]);
  return (
    <div className="boot">
      {failed ? (
        <>
          <p>{translate(language, "app.offline")}</p>
          <Button icon={<RefreshCw size={14} />} onClick={load}>
            {translate(language, "app.retry")}
          </Button>
        </>
      ) : (
        <>
          <Spinner />
          <p className="subtle">{translate(language, "app.loading")}</p>
        </>
      )}
    </div>
  );
}

function Workbench() {
  const t = useT();
  const view = useStore((state) => state.view);
  const dialog = useStore((state) => state.dialog);
  const openDialog = useStore((state) => state.openDialog);
  const language = useStore((state) => state.language);
  const pickImport = useFilePicker(".json,.zip,application/json,application/zip", importFile);
  useEvaluationSync();
  useShortcuts(pickImport);
  useEffect(() => {
    document.documentElement.lang = language === "zh" ? "zh-CN" : language;
    document.title = t("app.name");
  }, [language, t]);
  const close = useCallback(() => openDialog(null), [openDialog]);

  return (
    <div className="app">
      <TopBar />
      <ControlBar />
      <div className="workspace">
        <main className="workspace-main">
          <Suspense fallback={<Spinner />}>
            {view === "array" && <ArrayView />}
            {view === "dbf1d" && <DbfView />}
            {view === "dbf2d" && <Dbf2dView />}
            {view === "angle" && <AngleView />}
          </Suspense>
        </main>
        <Overview />
      </div>
      <StatusBar />
      <Suspense fallback={null}>
        {dialog === "dictionary" && <DictionaryDialog onClose={close} />}
        {dialog === "patterns" && <PatternsDialog onClose={close} />}
        {dialog === "report" && <ReportDialog onClose={close} />}
        {dialog === "projects" && <ProjectsDialog onClose={close} />}
        {dialog === "help" && <HelpDialog onClose={close} />}
      </Suspense>
    </div>
  );
}

export function App() {
  const theme = useStore((state) => state.theme);
  const [ready, setReady] = useState(false);
  useThemeAttribute(theme);
  const onReady = useCallback(() => setReady(true), []);
  return ready ? <Workbench /> : <Boot onReady={onReady} />;
}
