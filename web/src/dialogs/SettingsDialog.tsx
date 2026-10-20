import { useState } from "react";
import type { BandPreset, FieldOfView, Project, Requirements } from "../api/types";
import { Button, Callout, Dialog, NumberInput, Segmented } from "../components/ui";
import { useT } from "../i18n";
import { parseNumber, trimNumber } from "../lib/format";
import { useStore } from "../state/store";

type Draft = Pick<Project, "band" | "fov" | "requirements" | "grid_step_lambda" | "frequency_ghz">;
type NumericRequirement =
  | "azimuth_resolution_deg"
  | "elevation_resolution_deg"
  | "max_abs_error_deg"
  | "min_peak_margin_db"
  | "max_psl_db";

const REQUIREMENT_DEFAULTS: Record<NumericRequirement, number> = {
  azimuth_resolution_deg: 2,
  elevation_resolution_deg: 5,
  max_abs_error_deg: 0.5,
  min_peak_margin_db: 3,
  max_psl_db: -10,
};

function positive(text: string, max = 1000) {
  const value = parseNumber(text, ["ghz", "°", "db"]);
  return value !== null && value > 0 && value <= max ? value : null;
}

export function SettingsDialog({ onClose }: { onClose: () => void }) {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const config = useStore((state) => state.config)!;
  const { updateProject } = useStore.getState();
  const [draft, setDraft] = useState<Draft>({
    band: project.band,
    fov: project.fov,
    requirements: project.requirements,
    grid_step_lambda: project.grid_step_lambda,
    frequency_ghz: project.frequency_ghz,
  });
  const bandValid = draft.band.start_ghz < draft.band.stop_ghz;
  const fovValid = (["azimuth", "elevation"] as const).every((axis) => {
    const [low, high] = draft.fov[axis];
    return low >= -90 && low < 0 && high > 0 && high <= 90;
  });

  const choosePreset = (preset: BandPreset) => {
    if (preset === "custom") {
      setDraft((current) => ({ ...current, band: { ...current.band, preset } }));
      return;
    }
    const values = config.band_presets[preset];
    setDraft((current) => ({
      ...current,
      band: { preset, start_ghz: values.start_ghz, stop_ghz: values.stop_ghz },
      frequency_ghz: values.design_ghz,
    }));
  };
  const setFov = (axis: keyof FieldOfView, edge: 0 | 1, value: number) =>
    setDraft((current) => {
      const range = [...current.fov[axis]] as [number, number];
      range[edge] = Math.round(value);
      return { ...current, fov: { ...current.fov, [axis]: range } };
    });
  const setRequirement = <K extends keyof Requirements>(key: K, value: Requirements[K]) =>
    setDraft((current) => ({ ...current, requirements: { ...current.requirements, [key]: value } }));

  const numericRow = (key: NumericRequirement, label: string, unit: string, parse: (text: string) => number | null) => {
    const value = draft.requirements[key];
    return (
      <>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={value !== null}
            onChange={(event) => setRequirement(key, event.target.checked ? REQUIREMENT_DEFAULTS[key] : null)}
          />
          {label}
        </label>
        <span className="range-input">
          <NumberInput
            style={{ width: 80 }}
            disabled={value === null}
            value={value ?? REQUIREMENT_DEFAULTS[key]}
            parse={parse}
            format={(v) => trimNumber(v, 3)}
            onCommit={(v) => setRequirement(key, v)}
          />
          <span className="subtle">{unit}</span>
        </span>
      </>
    );
  };

  return (
    <Dialog
      title={t("settings.title")}
      onClose={onClose}
      size="medium"
      footer={
        <>
          <span className="spacer" />
          <Button onClick={onClose}>{t("common.cancel")}</Button>
          <Button
            variant="primary"
            disabled={!bandValid || !fovValid}
            onClick={() => {
              updateProject(draft);
              onClose();
            }}
          >
            {t("common.apply")}
          </Button>
        </>
      }
    >
      <div className="section">
        <h3 className="section-title">{t("settings.band")}</h3>
        <p className="subtle" style={{ margin: 0 }}>
          {t("settings.bandHint")}
        </p>
        <Segmented
          label={t("top.band")}
          value={draft.band.preset}
          options={[
            { value: "60G", label: "60 GHz" },
            { value: "77G", label: "77 GHz" },
            { value: "92G", label: "92 GHz" },
            { value: "custom", label: t("top.bandCustom") },
          ]}
          onChange={choosePreset}
        />
        <div className="form-grid">
          <label>{t("settings.start")}</label>
          <NumberInput
            style={{ width: 90 }}
            value={draft.band.start_ghz}
            parse={(text) => positive(text)}
            format={(v) => trimNumber(v, 3)}
            onCommit={(v) => setDraft((c) => ({ ...c, band: { ...c.band, preset: "custom", start_ghz: v } }))}
          />
          <label>{t("settings.stop")}</label>
          <NumberInput
            style={{ width: 90 }}
            value={draft.band.stop_ghz}
            parse={(text) => positive(text)}
            format={(v) => trimNumber(v, 3)}
            onCommit={(v) => setDraft((c) => ({ ...c, band: { ...c.band, preset: "custom", stop_ghz: v } }))}
          />
          <label>{t("settings.design")}</label>
          <NumberInput
            style={{ width: 90 }}
            value={draft.frequency_ghz}
            parse={(text) => positive(text)}
            format={(v) => trimNumber(v, 3)}
            onCommit={(v) => setDraft((c) => ({ ...c, frequency_ghz: v }))}
          />
        </div>
        {!bandValid && <Callout tone="danger">{t("settings.invalidBand")}</Callout>}
        {draft.band.preset === "92G" && <Callout tone="warning">{t("settings.preset92Note")}</Callout>}
      </div>

      <div className="section">
        <h3 className="section-title">{t("settings.fov")}</h3>
        <p className="subtle" style={{ margin: 0 }}>
          {t("settings.fovHint")}
        </p>
        <div className="form-grid">
          {(["azimuth", "elevation"] as const).map((axis) => (
            <FovRow key={axis} label={t(axis === "azimuth" ? "axis.azimuth" : "axis.elevation")} value={draft.fov[axis]} onChange={(edge, v) => setFov(axis, edge, v)} />
          ))}
        </div>
        {!fovValid && <Callout tone="danger">{t("settings.invalidFov")}</Callout>}
      </div>

      <div className="section">
        <h3 className="section-title">{t("settings.requirements")}</h3>
        <p className="subtle" style={{ margin: 0 }}>
          {t("settings.requirementsHint")}
        </p>
        <div className="form-grid">
          {numericRow("azimuth_resolution_deg", t("settings.reqAzRes"), "°", (text) => positive(text, 180))}
          {numericRow("elevation_resolution_deg", t("settings.reqElRes"), "°", (text) => positive(text, 180))}
          {numericRow("max_abs_error_deg", t("settings.reqError"), "°", (text) => positive(text, 90))}
          {numericRow("min_peak_margin_db", t("settings.reqMargin"), "dB", (text) => {
            const value = parseNumber(text, ["db"]);
            return value !== null && value >= 0 && value <= 60 ? value : null;
          })}
          {numericRow("max_psl_db", t("settings.reqPsl"), "dB", (text) => {
            const value = parseNumber(text, ["db"]);
            return value !== null && value <= 0 && value >= -80 ? value : null;
          })}
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={draft.requirements.azimuth_unambiguous_fov}
            onChange={(event) => setRequirement("azimuth_unambiguous_fov", event.target.checked)}
          />
          {t("settings.reqUnambAz")}
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={draft.requirements.elevation_unambiguous_fov}
            onChange={(event) => setRequirement("elevation_unambiguous_fov", event.target.checked)}
          />
          {t("settings.reqUnambEl")}
        </label>
      </div>

      <div className="section">
        <h3 className="section-title">{t("settings.grid")}</h3>
        <p className="subtle" style={{ margin: 0 }}>
          {t("settings.gridHint")}
        </p>
        <Segmented
          label={t("settings.grid")}
          value={String(draft.grid_step_lambda)}
          options={config.limits.grid_steps_lambda.map((step) => ({
            value: String(step),
            label: step === 0 ? t("settings.gridFree") : `λ/${Math.round(1 / step)}`,
          }))}
          onChange={(value) => setDraft((c) => ({ ...c, grid_step_lambda: Number(value) }))}
        />
      </div>
    </Dialog>
  );
}

function FovRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: [number, number];
  onChange: (edge: 0 | 1, value: number) => void;
}) {
  const parse = (text: string) => {
    const v = parseNumber(text, ["°"]);
    return v !== null && v >= -90 && v <= 90 ? Math.round(v) : null;
  };
  return (
    <>
      <label>{label}</label>
      <span className="range-input">
        <NumberInput value={value[0]} parse={parse} onCommit={(v) => onChange(0, v)} />
        <span className="subtle">~</span>
        <NumberInput value={value[1]} parse={parse} onCommit={(v) => onChange(1, v)} />
        <span className="subtle">°</span>
      </span>
    </>
  );
}
