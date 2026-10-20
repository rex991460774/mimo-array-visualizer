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
  ImageDown,
  Languages,
  LineChart,
  Map as MapIcon,
  Monitor,
  Moon,
  MoreHorizontal,
  Package,
  Radar,
  Save,
  Sun,
  Target,
  Upload,
  Waves,
} from "lucide-react";
import { type ReactNode, useEffect } from "react";
import { api } from "../api/client";
import { LANGUAGE_LABELS, useT } from "../i18n";
import { fmt, parseNumber, trimNumber } from "../lib/format";
import { exportBundle, exportLayout, importFile, newProject, saveProject } from "../state/actions";
import { useExportJob } from "../state/jobs";
import { type Language, type ThemeMode, useIsDirty, useStore, type ViewId } from "../state/store";
import { Button, Menu, MenuItem, NumberInput, Segmented, Spinner, useFilePicker } from "./ui";

/** Angle-error PNG export from the top bar, reporting progress in the status bar. */
function useAngleImageExport() {
  const job = useExportJob();
  const setStatus = useStore((state) => state.setStatus);
  const status = job.job?.status;
  useEffect(() => {
    if (status === "running" || status === "queued") setStatus("status.imageGenerating");
    else if (status === "succeeded") setStatus("status.exported", "success", { name: job.job?.download_name ?? "" });
    else if (status === "failed") setStatus("status.exportFailed", "error", { message: job.job?.error ?? "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);
  useEffect(() => {
    if (job.error) setStatus("status.exportFailed", "error", { message: job.error });
  }, [job.error, setStatus]);
  return job;
}

export function TopBar() {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const projectId = useStore((state) => state.projectId);
  const language = useStore((state) => state.language);
  const theme = useStore((state) => state.theme);
  const { updateProject, openDialog, setLanguage, setTheme } = useStore.getState();
  const dirty = useIsDirty();
  const pickImport = useFilePicker(".json,.zip,application/json,application/zip", importFile);
  const capability = useStore((state) => state.evaluation?.capability);
  const angleImage = useAngleImageExport();

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
            <Button variant="ghost" icon={angleImage.running ? <Spinner /> : <Download size={16} />} onClick={toggle}>
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
              <div className="menu-sep" />
              <MenuItem
                icon={<ImageDown size={15} />}
                disabled={angleImage.running || (capability !== undefined && !capability.azimuth && !capability.elevation)}
                onSelect={() => {
                  close();
                  angleImage.start(() => api.createAngleErrorImage(project, 1.0, language));
                }}
              >
                {t("menu.exportAngleImage")}
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

function fovText(range: [number, number]): string {
  return range[0] === -range[1] ? `±${range[1]}°` : `${range[0]}~${range[1]}°`;
}

function ParamItem({
  label,
  children,
  onClick,
  title,
  dot,
}: {
  label: string;
  children: ReactNode;
  onClick?: () => void;
  title?: string;
  dot?: "on" | "warn" | "off";
}) {
  const body = (
    <>
      <span className="param-label">
        {dot && <span className={`chip-dot ${dot === "off" ? "" : dot}`} />}
        {label}
      </span>
      <span className="param-value">{children}</span>
    </>
  );
  return onClick ? (
    <button type="button" className="param param-button" onClick={onClick} title={title}>
      {body}
    </button>
  ) : (
    <label className="param" title={title}>
      {body}
    </label>
  );
}

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
  const patternDot = !pattern || (pattern.amplitude === "ideal" && pattern.phase === "ideal")
    ? "off"
    : pattern.amplitude === "mixed" || pattern.phase === "mixed"
      ? "warn"
      : "on";
  const band = project.band;
  const bandLabel = band.preset === "custom" ? t("top.bandCustom") : band.preset;

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
      <div className="param-strip" aria-label={t("top.settings")}>
        <Menu
          align="left"
          trigger={({ toggle }) => (
            <ParamItem label={t("top.band")} onClick={toggle}>
              {bandLabel}
              <span className="param-sub">
                {trimNumber(band.start_ghz, 2)}–{trimNumber(band.stop_ghz, 2)} GHz
              </span>
              <ChevronDown size={12} className="subtle" />
            </ParamItem>
          )}
        >
          {(close) => (
            <>
              {(["60G", "77G", "92G"] as const).map((preset) => {
                const values = config.band_presets[preset];
                return (
                  <MenuItem
                    key={preset}
                    checked={band.preset === preset}
                    onSelect={() => {
                      updateProject({
                        band: { preset, start_ghz: values.start_ghz, stop_ghz: values.stop_ghz },
                        frequency_ghz: values.design_ghz,
                      });
                      close();
                    }}
                  >
                    {preset}
                    <span className="subtle" style={{ marginLeft: 8 }}>
                      {values.start_ghz}–{values.stop_ghz} GHz
                    </span>
                  </MenuItem>
                );
              })}
              <div className="menu-sep" />
              <MenuItem
                checked={band.preset === "custom"}
                onSelect={() => {
                  close();
                  openDialog("settings");
                }}
              >
                {t("top.bandCustom")}…
              </MenuItem>
            </>
          )}
        </Menu>
        <ParamItem label={t("top.design")} title={t("top.designTitle")}>
          <NumberInput
            className="param-input"
            value={project.frequency_ghz}
            parse={(text) => {
              const value = parseNumber(text, ["ghz", "g"]);
              return value !== null && value > 0 && value <= 1000 ? value : null;
            }}
            format={(value) => trimNumber(value, 6)}
            invalidTitle={t("top.invalidFrequency")}
            onCommit={(value) => updateProject({ frequency_ghz: value })}
            style={{ width: 52 }}
          />
          <span className="param-unit">GHz</span>
        </ParamItem>
        <ParamItem label={t("top.margin")} title={t("top.marginTitle")}>
          <NumberInput
            className="param-input"
            value={project.ambiguity_margin_db}
            parse={(text) => {
              const value = parseNumber(text, ["db"]);
              return value !== null && value >= 0 && value <= 60 ? value : null;
            }}
            format={(value) => trimNumber(value, 3)}
            invalidTitle={t("top.invalidMargin")}
            onCommit={(value) => updateProject({ ambiguity_margin_db: value })}
            style={{ width: 36 }}
          />
          <span className="param-unit">dB</span>
        </ParamItem>
        <ParamItem label={t("top.fov")} onClick={() => openDialog("settings")} title={t("top.settings")}>
          Az {fovText(project.fov.azimuth)}
          <span className="param-sub">El {fovText(project.fov.elevation)}</span>
        </ParamItem>
        <ParamItem label={t("top.dictionary")} onClick={() => openDialog("dictionary")} dot={dictMode !== "ideal" ? "on" : "off"}>
          {t(`dict.${dictMode}` as const)}
        </ParamItem>
        <ParamItem label={t("top.ampPhase")} onClick={() => openDialog("patterns")} dot={patternDot}>
          {t("top.ampPhaseValue", {
            amplitude: t(`state.${pattern?.amplitude ?? "ideal"}` as const),
            phase: t(`state.${pattern?.phase ?? "ideal"}` as const),
          })}
        </ParamItem>
        <div className="param param-static">
          <span className="param-label">{t("top.display")}</span>
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
