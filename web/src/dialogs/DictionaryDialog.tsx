import { FileSpreadsheet, Upload, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { Axis, DictionaryMode, DictionaryPreview, DictionarySettings } from "../api/types";
import { Plot } from "../charts/Plot";
import { baseLayout, useChartTheme } from "../charts/theme";
import { Button, Callout, Dialog, Segmented, Spinner, useFilePicker } from "../components/ui";
import { useT } from "../i18n";
import { decodeMatrix, matrixRows } from "../lib/encoding";
import { useStore } from "../state/store";
import { rememberAssetName, useAssetNames } from "./useAssetNames";

const MODES: DictionaryMode[] = ["ideal", "ideal_reversed", "channel_pattern", "custom"];
const TABLE_ACCEPT = ".csv,.tsv,.txt,.xlsx,.xlsm";

// Cyclic-friendly diverging scale for phase in degrees.
const PHASE_SCALE: [number, string][] = [
  [0, "#2d1e3e"],
  [0.2, "#3f6ab0"],
  [0.4, "#9ecae1"],
  [0.5, "#f7f7f7"],
  [0.6, "#fdbb84"],
  [0.8, "#d6604d"],
  [1, "#2d1e3e"],
];

export function DictionaryDialog({ onClose }: { onClose: () => void }) {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const { updateProject, setStatus } = useStore.getState();
  const [draft, setDraft] = useState<DictionarySettings>(project.dbf_dictionary);
  const [axis, setAxis] = useState<Axis>("azimuth");
  const [preview, setPreview] = useState<DictionaryPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const names = useAssetNames([draft.azimuth_asset, draft.elevation_asset]);
  const needsFile = draft.mode === "custom" && !draft.azimuth_asset && !draft.elevation_asset;

  useEffect(() => {
    if (needsFile) {
      setPreview(null);
      setPreviewError(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    const timer = window.setTimeout(() => {
      api
        .dictionaryPreview({ ...project, dbf_dictionary: draft }, axis, controller.signal)
        .then((result) => {
          setPreview(result);
          setPreviewError(null);
        })
        .catch((error) => {
          if ((error as Error).name === "AbortError") return;
          setPreview(null);
          setPreviewError(errorMessage(error));
        })
        .finally(() => !controller.signal.aborted && setLoading(false));
    }, 80);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [project, draft, axis, needsFile]);

  const upload = (target: Axis) => async (file: File) => {
    setUploadError(null);
    try {
      const info = await api.uploadAsset(file);
      rememberAssetName(info.id, info.filename);
      setDraft((current) => ({
        ...current,
        mode: "custom",
        [target === "azimuth" ? "azimuth_asset" : "elevation_asset"]: info.id,
      }));
      setAxis(target);
    } catch (error) {
      setUploadError(t("status.uploadFailed", { message: errorMessage(error) }));
    }
  };
  const pickAz = useFilePicker(TABLE_ACCEPT, upload("azimuth"));
  const pickEl = useFilePicker(TABLE_ACCEPT, upload("elevation"));

  const apply = () => {
    updateProject({ dbf_dictionary: draft });
    setStatus("status.dictApplied", "success", { mode: t(`dict.${draft.mode}` as const) });
    onClose();
  };

  return (
    <Dialog
      title={t("dictDialog.title")}
      onClose={onClose}
      size="wide"
      footer={
        <>
          <span className="subtle">{t("dictDialog.qualityNote")}</span>
          <span className="spacer" />
          <Button onClick={onClose}>{t("common.cancel")}</Button>
          <Button variant="primary" disabled={needsFile} onClick={apply}>
            {t("dictDialog.apply")}
          </Button>
        </>
      }
    >
      <div className="two-col" style={{ gridTemplateColumns: "minmax(0, 5fr) minmax(0, 6fr)" }}>
        <div>
          <div className="section">
            <h3 className="section-title">{t("dictDialog.mode")}</h3>
            <div className="mode-cards" role="radiogroup">
              {MODES.map((mode) => (
                <button
                  key={mode}
                  type="button"
                  className="mode-card"
                  role="radio"
                  aria-checked={draft.mode === mode}
                  onClick={() => setDraft((current) => ({ ...current, mode }))}
                >
                  <span className="radio" />
                  <span>
                    <strong>{t(`dict.${mode}` as const)}</strong>
                    <span className="desc">{t(`dict.${mode}.desc` as const)}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>

          {draft.mode === "custom" && (
            <div className="section">
              <h3 className="section-title">{t("dictDialog.files")}</h3>
              {(["azimuth", "elevation"] as Axis[]).map((target) => {
                const asset = target === "azimuth" ? draft.azimuth_asset : draft.elevation_asset;
                const table = preview?.tables[target];
                return (
                  <div key={target} className={`file-slot ${asset ? "loaded" : ""}`}>
                    <FileSpreadsheet size={18} className="subtle" />
                    <div className="file-name">
                      <div style={{ fontWeight: 500 }}>
                        {t(target === "azimuth" ? "dictDialog.azFile" : "dictDialog.elFile")}
                      </div>
                      <div className="subtle" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                        {asset ? names[asset] : t("dictDialog.notLoaded")}
                        {asset && table
                          ? ` · ${t("dictDialog.tableInfo", { rows: table.rows, cols: table.columns.length, format: table.value_format })}`
                          : ""}
                      </div>
                    </div>
                    <Button size="sm" icon={<Upload size={13} />} onClick={target === "azimuth" ? pickAz : pickEl}>
                      {asset ? t("dictDialog.replace") : t("dictDialog.upload")}
                    </Button>
                    {asset && (
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<X size={14} />}
                        aria-label={t("dictDialog.clear")}
                        title={t("dictDialog.clear")}
                        onClick={() =>
                          setDraft((current) => ({
                            ...current,
                            [target === "azimuth" ? "azimuth_asset" : "elevation_asset"]: null,
                          }))
                        }
                      />
                    )}
                  </div>
                );
              })}
              {uploadError && <Callout tone="danger">{uploadError}</Callout>}
              <div className="form-grid">
                <label>{t("dictDialog.channelMode")}</label>
                <Segmented
                  value={draft.channel_mode}
                  options={[
                    { value: "virtual", label: t("dictDialog.virtual") },
                    { value: "physical", label: t("dictDialog.physical") },
                  ]}
                  onChange={(channel_mode) => setDraft((current) => ({ ...current, channel_mode }))}
                />
              </div>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={draft.phase_reversed}
                  onChange={(event) => setDraft((current) => ({ ...current, phase_reversed: event.target.checked }))}
                />
                {t("dictDialog.phaseReversed")}
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={draft.zero_phase_calibrated}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, zero_phase_calibrated: event.target.checked }))
                  }
                />
                {t("dictDialog.zeroCalibrated")}
              </label>
            </div>
          )}
        </div>

        <div className="section">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h3 className="section-title" style={{ flex: 1 }}>
              {t("dictDialog.preview")}
            </h3>
            {loading && <Spinner />}
            <Segmented
              label={t("dictDialog.previewAxis")}
              value={axis}
              options={[
                { value: "azimuth", label: t("axis.azimuth") },
                { value: "elevation", label: t("axis.elevation") },
              ]}
              onChange={setAxis}
            />
          </div>
          {needsFile && <Callout tone="info">{t("dictDialog.needFile")}</Callout>}
          {previewError && <Callout tone="danger">{previewError}</Callout>}
          {preview && !needsFile && <QualityCallout preview={preview} />}
          {preview && !needsFile && <PhaseMatrix preview={preview} />}
        </div>
      </div>
    </Dialog>
  );
}

function QualityCallout({ preview }: { preview: DictionaryPreview }) {
  const t = useT();
  const quality = preview.quality;
  const tone = quality.severity === "ok" ? "success" : quality.severity === "warning" ? "warning" : "danger";
  const title =
    quality.severity === "ok"
      ? t("dictDialog.qualityOk")
      : quality.severity === "warning"
        ? t("dictDialog.qualityWarning")
        : t("dictDialog.qualityDanger");
  return (
    <Callout tone={tone} title={title}>
      {t("dictDialog.qualityDetail", {
        ambiguous: quality.competitor_ambiguous_rows,
        zeros: quality.zero_norm_rows,
        rank: quality.non_neighbor_effective_rank,
        rankRows: quality.non_neighbor_rank_rows,
      })}
    </Callout>
  );
}

function PhaseMatrix({ preview }: { preview: DictionaryPreview }) {
  const t = useT();
  const theme = useChartTheme();
  const rows = useMemo(() => matrixRows(decodeMatrix(preview.phase_deg)), [preview]);
  const channels = useMemo(() => Array.from({ length: preview.channel_count }, (_, i) => i + 1), [preview]);
  const data = useMemo(
    () => [
      {
        type: "heatmap",
        x: channels,
        y: preview.angles,
        z: rows,
        zmin: -180,
        zmax: 180,
        colorscale: PHASE_SCALE,
        colorbar: { thickness: 10, outlinewidth: 0, tickfont: { size: 10, color: theme.textSecondary }, dtick: 90, ticksuffix: "°" },
        hovertemplate: "CH%{x}  %{y:+.0f}°<br>%{z:+.1f}°<extra></extra>",
      },
    ],
    [channels, preview, rows, theme],
  );
  const layout = useMemo(
    () =>
      baseLayout(theme, {
        margin: { l: 52, r: 8, t: 8, b: 40 },
        hovermode: "closest",
        xaxis: { title: { text: t("axis.channel") }, showgrid: false, zeroline: false },
        yaxis: { title: { text: t("axis.angle") }, dtick: 30, showgrid: false, zeroline: false },
      }),
    [theme, t],
  );
  return (
    <div>
      <div className="subtle" style={{ marginBottom: 6 }}>
        {t("dictDialog.phaseMatrix", { rows: preview.angles.length, cols: preview.channel_count })}
      </div>
      <div className="chart-box" style={{ height: 380 }}>
        <div className="chart-body">
          <Plot
            data={data}
            layout={layout}
            ariaLabel={t("dictDialog.phaseMatrix", { rows: preview.angles.length, cols: preview.channel_count })}
          />
        </div>
      </div>
    </div>
  );
}
