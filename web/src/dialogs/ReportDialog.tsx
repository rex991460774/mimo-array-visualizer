import { Download, FileText, ImageDown } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import type { Job, ReportOptions } from "../api/types";
import { Button, Callout, Dialog, NumberInput, Segmented } from "../components/ui";
import { LANGUAGE_LABELS, translate, useT } from "../i18n";
import { parseNumber, trimNumber } from "../lib/format";
import { useExportJob } from "../state/jobs";
import { type Language, useStore } from "../state/store";

type RangeKey = "azimuth_focus" | "elevation_focus" | "azimuth_hold" | "elevation_hold";

function angleParser(text: string) {
  const value = parseNumber(text, ["°"]);
  return value !== null && value >= -90 && value <= 90 ? value : null;
}

export function ReportDialog({ onClose }: { onClose: () => void }) {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const language = useStore((state) => state.language);
  const capability = useStore((state) => state.evaluation?.capability) ?? { azimuth: true, elevation: true, two_d: true };
  const [options, setOptions] = useState<ReportOptions>(() => ({
    title: translate(language, "reportDialog.defaultTitle"),
    azimuth_focus: { start: -70, stop: 70 },
    elevation_focus: { start: -15, stop: 15 },
    azimuth_hold: { start: -70, stop: 70 },
    elevation_hold: { start: -15, stop: 15 },
    azimuth_hold_stride_frames: 1,
    elevation_hold_stride_frames: 1,
    error_limit_deg: 1,
    spectrum_floor_db: -40,
    include_raw_data: true,
    include_spectrum_db: true,
    include_spectrum_magnitude: false,
    language,
  }));
  const report = useExportJob();
  const image = useExportJob();
  const set = <K extends keyof ReportOptions>(key: K, value: ReportOptions[K]) =>
    setOptions((current) => ({ ...current, [key]: value }));
  const setRange = (key: RangeKey, edge: "start" | "stop", value: number) =>
    setOptions((current) => {
      const range = { ...current[key], [edge]: value };
      if (range.start > range.stop) {
        if (edge === "start") range.stop = range.start;
        else range.start = range.stop;
      }
      return { ...current, [key]: range };
    });
  const noOutput = !options.include_spectrum_db && !options.include_spectrum_magnitude;

  const rangeRow = (key: RangeKey, label: string) => (
    <>
      <label>{label}</label>
      <span className="range-input">
        <NumberInput value={options[key].start} parse={angleParser} format={(v) => trimNumber(v, 1)} onCommit={(v) => setRange(key, "start", v)} aria-label={`${label} ${t("reportDialog.start")}`} />
        <span className="subtle">~</span>
        <NumberInput value={options[key].stop} parse={angleParser} format={(v) => trimNumber(v, 1)} onCommit={(v) => setRange(key, "stop", v)} aria-label={`${label} ${t("reportDialog.stop")}`} />
        <span className="subtle">°</span>
      </span>
    </>
  );

  const strideRow = (key: "azimuth_hold_stride_frames" | "elevation_hold_stride_frames") => (
    <>
      <label>{t("reportDialog.stride")}</label>
      <NumberInput
        style={{ width: 72 }}
        value={options[key]}
        parse={(text) => {
          const value = parseNumber(text);
          return value !== null && Number.isInteger(value) && value >= 1 && value <= 180 ? value : null;
        }}
        onCommit={(value) => set(key, value)}
      />
    </>
  );

  return (
    <Dialog
      title={t("reportDialog.title")}
      onClose={onClose}
      size="medium"
      footer={
        <>
          <span className="subtle" style={{ fontSize: 12 }}>
            {t("reportDialog.note")}
          </span>
          <span className="spacer" />
          <Button onClick={onClose}>{t("reportDialog.close")}</Button>
          <Button
            variant="primary"
            icon={<FileText size={15} />}
            disabled={report.running || noOutput || (!capability.azimuth && !capability.elevation)}
            onClick={() => report.start(() => api.createReport(project, options))}
          >
            {report.running ? t("reportDialog.generating") : t("reportDialog.generate")}
          </Button>
        </>
      }
    >
      <div className="section">
        <div className="form-grid">
          <label htmlFor="report-title">{t("reportDialog.reportTitle")}</label>
          <input
            id="report-title"
            className="input"
            maxLength={100}
            value={options.title}
            onChange={(event) => set("title", event.target.value)}
          />
          <label>{t("reportDialog.language")}</label>
          <Segmented
            value={options.language}
            options={(Object.keys(LANGUAGE_LABELS) as Language[]).map((code) => ({ value: code, label: LANGUAGE_LABELS[code] }))}
            onChange={(value) => set("language", value)}
          />
        </div>
      </div>

      <div className="two-col section">
        {(["azimuth", "elevation"] as const).map((axis) => (
          <div key={axis} className="panel" style={{ padding: 14, opacity: capability[axis] ? 1 : 0.6 }}>
            <div style={{ fontWeight: 600, marginBottom: 10 }}>{t(axis === "azimuth" ? "axis.azimuth" : "axis.elevation")}</div>
            {capability[axis] ? (
              <div className="form-grid">
                {rangeRow(`${axis}_focus`, t("reportDialog.focus"))}
                {rangeRow(`${axis}_hold`, t("reportDialog.hold"))}
                {strideRow(`${axis}_hold_stride_frames`)}
              </div>
            ) : (
              <p className="subtle" style={{ margin: 0 }}>
                {t("reportDialog.unavailableAxis")}
              </p>
            )}
          </div>
        ))}
      </div>

      <div className="section">
        <div className="form-grid">
          <label>{t("reportDialog.errorLimit")}</label>
          <NumberInput
            style={{ width: 72 }}
            value={options.error_limit_deg}
            parse={(text) => {
              const value = parseNumber(text, ["°"]);
              return value !== null && value > 0 && value <= 30 ? value : null;
            }}
            format={(v) => trimNumber(v, 2)}
            onCommit={(value) => set("error_limit_deg", value)}
          />
          <label>{t("reportDialog.floor")}</label>
          <span className="range-input">
            <NumberInput
              value={options.spectrum_floor_db}
              parse={(text) => {
                const value = parseNumber(text, ["db"]);
                return value !== null && value >= -120 && value <= -10 ? value : null;
              }}
              onCommit={(value) => set("spectrum_floor_db", value)}
            />
            <span className="subtle">dB</span>
          </span>
        </div>
        <label className="checkbox">
          <input type="checkbox" checked={options.include_spectrum_db} onChange={(e) => set("include_spectrum_db", e.target.checked)} />
          {t("reportDialog.outputDb")}
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={options.include_spectrum_magnitude} onChange={(e) => set("include_spectrum_magnitude", e.target.checked)} />
          {t("reportDialog.outputMag")}
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={options.include_raw_data} onChange={(e) => set("include_raw_data", e.target.checked)} />
          {t("reportDialog.rawData")}
        </label>
        {noOutput && <Callout tone="warning">{t("reportDialog.needOutput")}</Callout>}
        <JobStatus state={report} />
      </div>

      <div className="section">
        <h3 className="section-title">{t("reportDialog.imageTitle")}</h3>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="subtle" style={{ flex: 1 }}>
            {t("reportDialog.imageHint")}
          </span>
          <Button
            icon={<ImageDown size={15} />}
            disabled={image.running || (!capability.azimuth && !capability.elevation)}
            onClick={() => image.start(() => api.createAngleErrorImage(project, options.error_limit_deg, options.language))}
          >
            {t("reportDialog.generateImage")}
          </Button>
        </div>
        <JobStatus state={image} />
      </div>
    </Dialog>
  );
}

function JobStatus({
  state,
}: {
  state: { job: Job | null; error: string | null; running: boolean; cancel: () => void; download: () => void };
}) {
  const t = useT();
  const { job, error } = state;
  if (error) return <Callout tone="danger" title={t("reportDialog.failed")}>{error}</Callout>;
  if (!job) return null;
  if (job.status === "failed") return <Callout tone="danger" title={t("reportDialog.failed")}>{job.error}</Callout>;
  if (job.status === "cancelled") return <Callout>{t("reportDialog.cancelled")}</Callout>;
  if (job.status === "succeeded") {
    return (
      <Callout tone="success" title={t("reportDialog.done")}>
        <span className="mono">{job.download_name}</span>{" "}
        <Button size="sm" variant="ghost" icon={<Download size={13} />} onClick={state.download}>
          {t("reportDialog.download")}
        </Button>
      </Callout>
    );
  }
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span className="subtle" style={{ flex: 1 }}>
          {job.message || t("reportDialog.generating")} · {job.progress}%
        </span>
        <Button size="sm" variant="ghost" onClick={state.cancel}>
          {t("reportDialog.cancel")}
        </Button>
      </div>
      <div className="progress">
        <div style={{ width: `${Math.max(3, job.progress)}%` }} />
      </div>
    </div>
  );
}
