import {
  Activity,
  Check,
  ChevronDown,
  Download,
  FileDown,
  FilePlus2,
  FileText,
  FolderOpen,
  Grid3x3,
  HelpCircle,
  Languages,
  LineChart,
  Map as MapIcon,
  Monitor,
  Moon,
  MoreHorizontal,
  Package,
  Radar,
  Save,
  Settings2,
  Sun,
  Target,
  Upload,
  Waves,
} from "lucide-react";
import type { ReactNode } from "react";
import { LANGUAGE_LABELS, useT } from "../i18n";
import { fmt, parseNumber, trimNumber } from "../lib/format";
import { exportBundle, exportLayout, importFile, newProject, saveProject } from "../state/actions";
import { type Language, type ThemeMode, useIsDirty, useStore, type ViewId } from "../state/store";
import { Button, Menu, MenuItem, NumberInput, Segmented, Spinner, useFilePicker } from "./ui";

export function TopBar() {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const projectId = useStore((state) => state.projectId);
  const language = useStore((state) => state.language);
  const theme = useStore((state) => state.theme);
  const { updateProject, openDialog, setLanguage, setTheme } = useStore.getState();
  const dirty = useIsDirty();
  const pickImport = useFilePicker(".json,.zip,application/json,application/zip", importFile);

  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          <Radar size={18} />
        </span>
        <span className="brand-name">{t("app.name")}</span>
        <span className="brand-divider" />
      </div>
      <div className="project-title">
        <input
          className="project-name-input"
          value={project.name}
          aria-label={t("project.name")}
          size={Math.max(8, Math.min(32, project.name.length + 1))}
          maxLength={120}
          onChange={(event) => updateProject({ name: event.target.value })}
          onBlur={(event) => !event.target.value.trim() && updateProject({ name: t("project.untitled") })}
        />
        <span className="save-state">
          <span className={`save-dot ${!projectId ? "local" : dirty ? "dirty" : ""}`} />
          <span className="save-state-text">
            {!projectId ? t("project.local") : dirty ? t("project.unsaved") : t("project.saved")}
          </span>
        </span>
      </div>
      <div className="topbar-spacer" />
      <div className="topbar-actions">
        <Button variant="ghost" icon={<FolderOpen size={16} />} onClick={() => openDialog("projects")}>
          <span className="btn-label">{t("menu.projects")}</span>
        </Button>
        <Button variant="ghost" icon={<Save size={16} />} onClick={() => saveProject()} title={`${t("menu.save")} (Ctrl+S)`}>
          <span className="btn-label">{t("menu.save")}</span>
        </Button>
        <Menu
          trigger={({ toggle }) => (
            <Button variant="ghost" icon={<Upload size={16} />} onClick={toggle}>
              <span className="btn-label">{t("menu.import")}</span>
              <ChevronDown size={14} />
            </Button>
          )}
        >
          {(close) => (
            <>
              <MenuItem icon={<FileText size={15} />} onSelect={() => { close(); pickImport(); }}>
                {t("menu.importLayout")}
              </MenuItem>
              <MenuItem icon={<Package size={15} />} onSelect={() => { close(); pickImport(); }}>
                {t("menu.importBundle")}
              </MenuItem>
            </>
          )}
        </Menu>
        <Menu
          trigger={({ toggle }) => (
            <Button variant="ghost" icon={<Download size={16} />} onClick={toggle}>
              <span className="btn-label">{t("menu.export")}</span>
              <ChevronDown size={14} />
            </Button>
          )}
        >
          {(close) => (
            <>
              <MenuItem icon={<FileDown size={15} />} onSelect={() => { close(); exportLayout(); }}>
                {t("menu.exportLayout")}
              </MenuItem>
              <MenuItem icon={<Package size={15} />} onSelect={() => { close(); exportBundle(); }}>
                {t("menu.exportBundle")}
              </MenuItem>
            </>
          )}
        </Menu>
        <Button variant="primary" icon={<FileText size={15} />} onClick={() => openDialog("report")}>
          <span className="btn-label">{t("menu.report")}</span>
        </Button>
        <Menu
          trigger={({ toggle }) => (
            <Button variant="ghost" icon={<MoreHorizontal size={18} />} onClick={toggle} aria-label={t("menu.more")} title={t("menu.more")} />
          )}
        >
          {(close) => (
            <>
              <MenuItem icon={<FilePlus2 size={15} />} onSelect={() => { close(); newProject(); }}>
                {t("menu.new")}
              </MenuItem>
              <MenuItem icon={<Save size={15} />} onSelect={() => { close(); saveProject(true); }}>
                {t("menu.saveAs")}
              </MenuItem>
              <MenuItem icon={<HelpCircle size={15} />} onSelect={() => { close(); openDialog("help"); }}>
                {t("menu.help")}
              </MenuItem>
              <div className="menu-sep" />
              <div className="menu-label">
                <Languages size={12} /> {t("menu.language")}
              </div>
              {(Object.keys(LANGUAGE_LABELS) as Language[]).map((code) => (
                <MenuItem key={code} checked={language === code} onSelect={() => { setLanguage(code); close(); }}>
                  {LANGUAGE_LABELS[code]}
                </MenuItem>
              ))}
              <div className="menu-sep" />
              <div className="menu-label">{t("menu.theme")}</div>
              {(
                [
                  ["system", <Monitor size={15} key="m" />],
                  ["light", <Sun size={15} key="s" />],
                  ["dark", <Moon size={15} key="d" />],
                ] as [ThemeMode, ReactNode][]
              ).map(([mode, icon]) => (
                <MenuItem key={mode} icon={icon} checked={theme === mode} onSelect={() => { setTheme(mode); close(); }}>
                  {t(`theme.${mode}` as const)}
                </MenuItem>
              ))}
            </>
          )}
        </Menu>
      </div>
    </header>
  );
}

const VIEWS: { id: ViewId; icon: ReactNode; key: "view.array" | "view.dbf1d" | "view.dbf2d" | "view.angle" | "view.band" }[] = [
  { id: "array", icon: <Grid3x3 size={15} />, key: "view.array" },
  { id: "dbf1d", icon: <LineChart size={15} />, key: "view.dbf1d" },
  { id: "dbf2d", icon: <MapIcon size={15} />, key: "view.dbf2d" },
  { id: "angle", icon: <Target size={15} />, key: "view.angle" },
  { id: "band", icon: <Waves size={15} />, key: "view.band" },
];

export function ControlBar() {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const config = useStore((state) => state.config)!;
  const view = useStore((state) => state.view);
  const display = useStore((state) => state.display);
  const evaluation = useStore((state) => state.evaluation);
  const { setView, updateProject, setDisplay, openDialog } = useStore.getState();
  const dictMode = project.dbf_dictionary.mode;
  const pattern = evaluation?.pattern_status;
  const patternActive = pattern && (pattern.amplitude !== "ideal" || pattern.phase !== "ideal");

  return (
    <nav className="controlbar">
      <div className="view-tabs" role="tablist" aria-label="Views">
        {VIEWS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            className="view-tab"
            aria-selected={view === item.id}
            onClick={() => setView(item.id)}
          >
            {item.icon}
            {t(item.key)}
          </button>
        ))}
      </div>
      <div className="controlbar-group">
        <Segmented
          label={t("top.band")}
          value={project.band.preset}
          options={[
            { value: "60G", label: "60G", title: "57–64 GHz" },
            { value: "77G", label: "77G", title: "76–81 GHz" },
            { value: "92G", label: "92G" },
            { value: "custom", label: t("top.bandCustom") },
          ]}
          onChange={(preset) => {
            if (preset === "custom") {
              openDialog("settings");
              return;
            }
            const values = config.band_presets[preset];
            updateProject({
              band: { preset, start_ghz: values.start_ghz, stop_ghz: values.stop_ghz },
              frequency_ghz: values.design_ghz,
            });
          }}
        />
        <label className="field" title={t("top.designTitle")}>
          <span className="field-label">{t("top.frequency")}</span>
          <NumberInput
            className=""
            value={project.frequency_ghz}
            parse={(text) => {
              const value = parseNumber(text, ["ghz", "g"]);
              return value !== null && value > 0 && value <= 1000 ? value : null;
            }}
            format={(value) => trimNumber(value, 6)}
            invalidTitle={t("top.invalidFrequency")}
            onCommit={(value) => updateProject({ frequency_ghz: value })}
            style={{ width: 58 }}
          />
          <span className="field-unit">GHz</span>
        </label>
        <label className="field" title={t("top.marginTitle")}>
          <span className="field-label">{t("top.margin")}</span>
          <NumberInput
            className=""
            value={project.ambiguity_margin_db}
            parse={(text) => {
              const value = parseNumber(text, ["db"]);
              return value !== null && value >= 0 && value <= 60 ? value : null;
            }}
            format={(value) => trimNumber(value, 3)}
            invalidTitle={t("top.invalidMargin")}
            onCommit={(value) => updateProject({ ambiguity_margin_db: value })}
            style={{ width: 42 }}
          />
          <span className="field-unit">dB</span>
        </label>
        <button type="button" className="chip-button" onClick={() => openDialog("dictionary")}>
          <span className={`chip-dot ${dictMode !== "ideal" ? "on" : ""}`} />
          <span className="chip-label">{t("top.dictionary")}</span>
          <span className="chip-value">{t(`dict.${dictMode}` as const)}</span>
        </button>
        <button type="button" className="chip-button" onClick={() => openDialog("patterns")}>
          <span className={`chip-dot ${patternActive ? (pattern?.amplitude === "mixed" || pattern?.phase === "mixed" ? "warn" : "on") : ""}`} />
          <span className="chip-label">{t("top.ampPhase")}</span>
          <span className="chip-value">
            {t("top.ampPhaseValue", {
              amplitude: t(`state.${pattern?.amplitude ?? "ideal"}` as const),
              phase: t(`state.${pattern?.phase ?? "ideal"}` as const),
            })}
          </span>
        </button>
        <Button
          variant="ghost"
          icon={<Settings2 size={16} />}
          onClick={() => openDialog("settings")}
          title={t("top.settings")}
          aria-label={t("top.settings")}
        />
        <Segmented
          label={t("top.display")}
          value={display}
          options={[
            { value: "db", label: t("display.db") },
            { value: "magnitude", label: t("display.magnitude") },
          ]}
          onChange={setDisplay}
        />
      </div>
    </nav>
  );
}

export function StatusBar() {
  const t = useT();
  const status = useStore((state) => state.status);
  const evaluating = useStore((state) => state.evaluating);
  const config = useStore((state) => state.config);
  const evaluation = useStore((state) => state.evaluation);
  const project = useStore((state) => state.project);
  const language = useStore((state) => state.language);
  const separator = language === "en" ? ": " : "：";
  const text = status
    ? `${t(status.key, status.params)}${status.detail ? `${separator}${status.detail}` : ""}`
    : t("status.ready");
  return (
    <footer className="statusbar">
      <span className={`status-text ${status?.tone === "error" ? "error" : status?.tone === "success" ? "success" : ""}`} role="status">
        {status?.tone === "success" && <Check size={12} style={{ verticalAlign: -1, marginRight: 4 }} />}
        {text}
      </span>
      {evaluating && (
        <span className="status-meta">
          <Spinner /> {t("status.computing")}
        </span>
      )}
      {project && evaluation && (
        <span className="status-meta mono">
          <Activity size={12} />λ = {fmt(evaluation.wavelength_mm, 3)} mm @ {trimNumber(project.frequency_ghz, 3)} GHz
        </span>
      )}
      {config && <span className="status-meta subtle">v{config.version}</span>}
    </footer>
  );
}
