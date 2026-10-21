import { useMemo } from "react";
import type { Axis, DbfBank, NoiseAccuracy } from "../api/types";
import { Plot } from "../charts/Plot";
import { baseLayout, useChartTheme } from "../charts/theme";
import { cutSummary, errorText, marginText, noFoldText } from "../components/Overview";
import { NumberInput, Segmented, Spinner } from "../components/ui";
import { useT } from "../i18n";
import { wire } from "../lib/encoding";
import { parseNumber, trimNumber } from "../lib/format";
import { snrOf, useDbfBank, useNoiseAccuracy } from "../state/compute";
import { type AngleMode, useStore } from "../state/store";
import { EmptyCapability } from "./EmptyCapability";

const SNR_RANGE: [number, number] = [-20, 40];

export function AngleView() {
  const t = useT();
  const evaluation = useStore((state) => state.evaluation);
  const mode = useStore((state) => state.angleMode);
  const setAngleMode = useStore((state) => state.setAngleMode);
  const capability = evaluation?.capability ?? { azimuth: true, elevation: true, two_d: true };
  const Panel = mode === "noise" ? NoiseAxisPanel : AngleAxisPanel;
  return (
    <div className="angle-view">
      <div className="angle-mode-bar">
        <Segmented<AngleMode>
          label={t("angle.mode")}
          value={mode}
          onChange={setAngleMode}
          options={[
            { value: "ideal", label: t("angle.modeIdeal") },
            { value: "noise", label: t("angle.modeNoise") },
          ]}
        />
        {mode === "noise" ? <SnrInput /> : <span className="angle-mode-hint subtle">{t("angle.idealHint")}</span>}
      </div>
      <div className="angle-grid">
        <Panel axis="azimuth" available={capability.azimuth} />
        <Panel axis="elevation" available={capability.elevation} />
      </div>
    </div>
  );
}

function SnrInput() {
  const t = useT();
  const snr = useStore((state) => snrOf(state.project!));
  const updateProject = useStore((state) => state.updateProject);
  const parse = (text: string) => {
    const value = parseNumber(text, ["db"]);
    return value !== null && value >= SNR_RANGE[0] && value <= SNR_RANGE[1] ? value : null;
  };
  return (
    <label className="angle-snr" title={t("angle.snrHint")}>
      <span className="readout-label">{t("angle.snr")}</span>
      <NumberInput
        className="input num"
        aria-label={t("angle.snr")}
        value={snr}
        parse={parse}
        format={(value) => trimNumber(value, 1)}
        invalidTitle={t("angle.snrHint")}
        onCommit={(value) => updateProject({ noise: { snr_db: value } })}
        style={{ width: 56 }}
      />
      <span className="subtle">dB</span>
      <span className="angle-snr-hint subtle">{t("angle.snrHint")}</span>
    </label>
  );
}

function AngleAxisPanel({ axis, available }: { axis: Axis; available: boolean }) {
  const t = useT();
  const bank = useDbfBank(axis, available);
  const fov = useStore((state) => state.project!.fov[axis]);
  const threshold = useStore((state) => state.project!.ambiguity_margin_db);
  const axisLabel = t(axis === "azimuth" ? "axis.azimuth" : "axis.elevation");
  return (
    <section className="panel">
      <header className="panel-header">
        <div className="panel-heading">
          <span className="panel-title">{t("angle.panelTitle", { axis: axisLabel })}</span>
          <span className="panel-subtitle">
            {t("overview.fov", { low: fov[0], high: fov[1] })} · {t("angle.subtitle")}
          </span>
        </div>
        <div className="panel-tools">{available && bank.loading && <Spinner />}</div>
      </header>
      {available && (
        <div className="panel-toolbar">
          <span className="toolbar-legend">
            <span className="legend-swatch band" />
            {t("angle.noFold")}
          </span>
          <span className="toolbar-legend">
            <span className="legend-line threshold" />
            {t("angle.threshold", { value: trimNumber(threshold, 1) })}
          </span>
          <span className="toolbar-legend">
            <span className="legend-swatch capped" />
            {t("angle.clipped")}
          </span>
        </div>
      )}
      <div className="panel-body">
        {available && bank.data && (
          <div className="angle-stack">
            <div className="angle-chart">
              <span className="angle-chart-label">{t("axis.error")}</span>
              <AngleChart bank={bank.data} kind="error" />
            </div>
            <div className="angle-chart">
              <span className="angle-chart-label">{t("axis.margin")}</span>
              <AngleChart bank={bank.data} kind="margin" />
            </div>
          </div>
        )}
        {available && !bank.data && bank.loading && (
          <div className="loading-overlay">
            <Spinner /> {t("dbf.loading")}
          </div>
        )}
        {available && bank.error && !bank.loading && (
          <div className="empty-state">
            <div className="empty-state-inner">
              <h3>{t("overview.error")}</h3>
              <p>{bank.error}</p>
            </div>
          </div>
        )}
        {!available && <EmptyCapability title={t(axis === "azimuth" ? "empty.azimuth" : "empty.elevation")} />}
      </div>
      {available && (
        <footer className="panel-footer">
          {bank.data ? <AngleReadout bank={bank.data} /> : <span className="subtle">{t("dbf.loading")}</span>}
        </footer>
      )}
    </section>
  );
}

function AngleReadout({ bank }: { bank: DbfBank }) {
  const t = useT();
  const metrics = bank.metrics;
  // The cut reason only matters when the no-fold range stops short of the FOV.
  const truncated = metrics.negative_cut_reason !== "data_boundary" || metrics.positive_cut_reason !== "data_boundary";
  return (
    <div className="readout">
      <span className="readout-item">
        <span className="readout-label">{t("overview.noFold")}</span>
        <span className="readout-value">{noFoldText(metrics)}</span>
      </span>
      <span className="readout-item">
        <span className="readout-label">{t("overview.focusError")}</span>
        <span className="readout-value">{errorText(wire(metrics.focus_max_abs_error))}</span>
      </span>
      <span className="readout-item">
        <span className="readout-label">{t("overview.peakMargin")}</span>
        <span className="readout-value">{marginText(metrics, t)}</span>
      </span>
      {truncated && (
        <span className="readout-item">
          <span className="readout-label">{t("overview.cutReason")}</span>
          <span className="readout-value" style={{ fontWeight: 500 }}>{cutSummary(metrics, t)}</span>
        </span>
      )}
    </div>
  );
}

function AngleChart({ bank, kind }: { bank: DbfBank; kind: "error" | "margin" }) {
  const t = useT();
  const theme = useChartTheme();
  const threshold = useStore((state) => state.project!.ambiguity_margin_db);
  const metrics = bank.metrics;
  const left = wire(metrics.no_fold_left);
  const right = wire(metrics.no_fold_right);

  const { data, layout } = useMemo(() => {
    const x = bank.true_angles;
    const band =
      left !== null && right !== null && right > left
        ? [{ type: "rect", xref: "x", yref: "paper", x0: left, x1: right, y0: 0, y1: 1, fillcolor: theme.band, line: { width: 0 }, layer: "below" }]
        : [];
    const xaxis = {
      range: [x[0], x[x.length - 1]],
      dtick: x[x.length - 1] - x[0] > 90 ? 30 : 10,
      ...(kind === "margin" ? { title: { text: t("axis.trueAngle") } } : {}),
    };
    // Captions sit above the plot area; only the lower chart carries the x title.
    // A fixed left margin keeps the two stacked x axes aligned.
    const margin = { l: 52, r: 16, t: 26, b: kind === "margin" ? 44 : 26 };
    if (kind === "error") {
      const y = bank.frames.errors;
      // Scale to the errors inside the no-fold range so small errors stay readable;
      // folded errors outside it may clip (same rule as the PDF report).
      const inRange = y.filter(
        (value, i) =>
          Number.isFinite(value) && (left === null || right === null || right <= left || (x[i] >= left && x[i] <= right)),
      );
      const spread = Math.max(0, ...inRange.map((value) => Math.abs(value)));
      const limit = Math.min(Math.max(spread * 1.25, 0.1), 180);
      return {
        data: [
          {
            type: "scatter",
            mode: "lines",
            x,
            y,
            line: { color: theme.line, width: 1.8 },
            name: t("angle.errorSeries"),
            hovertemplate: "%{x:+.0f}°  %{y:+.3f}°<extra></extra>",
          },
        ],
        layout: baseLayout(theme, {
          margin,
          shapes: band,
          xaxis,
          yaxis: { automargin: false, range: [-limit, limit], zeroline: true },
        }),
      };
    }
    const raw = bank.frames.margins_db.map((value) => wire(value));
    const finite = raw.filter((value): value is number => value !== null && Number.isFinite(value));
    const top = Math.max(threshold * 2, 6, ...finite) * 1.1;
    const y = raw.map((value) => (value === null ? null : value === Number.POSITIVE_INFINITY ? top : value));
    const capped = raw.map((value) => value === Number.POSITIVE_INFINITY);
    return {
      data: [
        {
          type: "scatter",
          mode: "lines",
          x,
          y,
          line: { color: theme.secondary, width: 1.8 },
          name: t("angle.marginSeries"),
          hovertemplate: "%{x:+.0f}°  %{y:.2f} dB<extra></extra>",
        },
        {
          type: "scatter",
          mode: "markers",
          x: x.filter((_, i) => capped[i]),
          y: x.filter((_, i) => capped[i]).map(() => top),
          marker: { size: 4, color: theme.secondary, symbol: "triangle-up" },
          hovertemplate: `%{x:+.0f}°  ${t("overview.noCompetitor")}<extra></extra>`,
        },
      ],
      layout: baseLayout(theme, {
        margin,
        shapes: [
          ...band,
          { type: "line", xref: "paper", x0: 0, x1: 1, y0: threshold, y1: threshold, line: { color: theme.danger, width: 1.2, dash: "dash" } },
        ],
        xaxis,
        yaxis: { automargin: false, range: [0, top * 1.04], rangemode: "tozero" },
      }),
    };
  }, [bank, kind, theme, threshold, left, right, t]);

  return (
    <div className="chart-body">
      <Plot
        data={data}
        layout={layout}
        ariaLabel={`${t(bank.axis === "azimuth" ? "axis.azimuth" : "axis.elevation")} ${t(kind === "error" ? "axis.error" : "axis.margin")}`}
      />
    </div>
  );
}

/** Degrees with precision that suits the magnitude (accuracies span 0.001° to tens of degrees). */
function degText(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  const digits = value < 0.1 ? 3 : value < 10 ? 2 : 1;
  return `${value.toFixed(digits)}°`;
}

function percentText(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${trimNumber(value * 100, 1)}%`;
}

function NoiseAxisPanel({ axis, available }: { axis: Axis; available: boolean }) {
  const t = useT();
  const result = useNoiseAccuracy(axis, available);
  const fov = useStore((state) => state.project!.fov[axis]);
  const axisLabel = t(axis === "azimuth" ? "axis.azimuth" : "axis.elevation");
  const data = result.data;
  return (
    <section className="panel">
      <header className="panel-header">
        <div className="panel-heading">
          <span className="panel-title">{t("angle.panelTitle", { axis: axisLabel })}</span>
          <span className="panel-subtitle">
            {t("overview.fov", { low: fov[0], high: fov[1] })} · {t("angle.noiseSubtitle", { trials: data?.trials ?? 200 })}
          </span>
        </div>
        <div className="panel-tools">{available && result.loading && <Spinner />}</div>
      </header>
      {available && (
        <div className="panel-toolbar">
          <span className="toolbar-legend">
            <span className="legend-line series" />
            {t("angle.rmseSeries")}
          </span>
          <span className="toolbar-legend">
            <span className="legend-line bound" />
            {t("angle.crbSeries")}
          </span>
          {data && data.summary.ambiguous_count > 0 && (
            <span className="toolbar-legend">
              <span className="legend-swatch ambiguous" />
              {t("angle.ambiguousShade")}
            </span>
          )}
        </div>
      )}
      <div className="panel-body">
        {available && data && (
          <div className="angle-stack">
            <div className="angle-chart">
              <span className="angle-chart-label">{t("angle.rmseChart")}</span>
              <RmseChart result={data} />
            </div>
            <div className="angle-chart">
              <span className="angle-chart-label">{t("angle.outlierChart")}</span>
              <OutlierChart result={data} />
            </div>
          </div>
        )}
        {available && !data && result.loading && (
          <div className="loading-overlay">
            <Spinner /> {t("dbf.loading")}
          </div>
        )}
        {available && result.error && !result.loading && (
          <div className="empty-state">
            <div className="empty-state-inner">
              <h3>{t("overview.error")}</h3>
              <p>{result.error}</p>
            </div>
          </div>
        )}
        {!available && <EmptyCapability title={t(axis === "azimuth" ? "empty.azimuth" : "empty.elevation")} />}
      </div>
      {available && (
        <footer className="panel-footer">
          {data ? <NoiseReadout result={data} /> : <span className="subtle">{t("dbf.loading")}</span>}
        </footer>
      )}
    </section>
  );
}

function NoiseReadout({ result }: { result: NoiseAccuracy }) {
  const t = useT();
  const summary = result.summary;
  const threshold = wire(summary.threshold_snr_db);
  const thresholdText =
    threshold === null
      ? t("angle.thresholdAbove", { value: summary.sweep_max_db })
      : threshold <= summary.sweep_min_db
        ? t("angle.thresholdBelow", { value: summary.sweep_min_db })
        : `${trimNumber(threshold, 1)} dB`;
  return (
    <div className="readout">
      <span className="readout-item">
        <span className="readout-label">{t("angle.boresightRmse")}</span>
        <span className="readout-value">{degText(wire(summary.boresight_rmse))}</span>
        <span className="subtle">{t("angle.crbValue", { value: degText(wire(summary.boresight_crb)) })}</span>
      </span>
      <span className="readout-item">
        <span className="readout-label">{t("angle.maxRmse")}</span>
        <span className="readout-value">{degText(wire(summary.max_rmse))}</span>
      </span>
      <span className="readout-item">
        <span className="readout-label">{t("angle.outlierAtSnr")}</span>
        <span className="readout-value">{percentText(wire(summary.max_outlier_rate))}</span>
      </span>
      <span className="readout-item">
        <span className="readout-label">{t("angle.thresholdSnr", { value: trimNumber(summary.outlier_limit * 100, 1) })}</span>
        <span className="readout-value">{thresholdText}</span>
      </span>
      {summary.ambiguous_count > 0 && (
        <span className="readout-item subtle">{t("angle.ambiguousNote", { count: summary.ambiguous_count })}</span>
      )}
    </div>
  );
}

function RmseChart({ result }: { result: NoiseAccuracy }) {
  const t = useT();
  const theme = useChartTheme();
  const { data, layout } = useMemo(() => {
    const x = result.true_angles;
    const rmse = result.rmse.map(wire);
    const crb = result.crb.map(wire);
    const finite = [...rmse, ...crb].filter((value): value is number => value !== null && Number.isFinite(value));
    const top = Math.max(...finite, 1e-3) * 1.15;
    const step = x.length > 1 ? x[1] - x[0] : 1;
    const shading = result.ambiguous.flatMap((ambiguous, i) =>
      ambiguous
        ? [{ type: "rect", xref: "x", yref: "paper", x0: x[i] - step / 2, x1: x[i] + step / 2, y0: 0, y1: 1, fillcolor: theme.danger, opacity: 0.12, line: { width: 0 }, layer: "below" }]
        : [],
    );
    const hover = x.map((_, i) =>
      t("angle.noiseHover", {
        rmse: degText(rmse[i]),
        crb: degText(crb[i]),
        bias: degText(wire(result.bias[i])),
        outlier: percentText(wire(result.outlier_rate[i])),
      }),
    );
    return {
      data: [
        {
          type: "scatter",
          mode: "lines+markers",
          x,
          y: rmse,
          line: { color: theme.line, width: 1.8 },
          marker: { size: 4, color: theme.line },
          name: t("angle.rmseSeries"),
          text: hover,
          hovertemplate: "%{x:+.0f}°  %{text}<extra></extra>",
        },
        {
          type: "scatter",
          mode: "lines",
          x,
          y: crb,
          line: { color: theme.secondary, width: 1.4, dash: "dash" },
          name: t("angle.crbSeries"),
          hoverinfo: "skip",
        },
      ],
      layout: baseLayout(theme, {
        margin: { l: 52, r: 16, t: 26, b: 44 },
        shapes: shading,
        xaxis: { range: [x[0], x[x.length - 1]], dtick: x[x.length - 1] - x[0] > 90 ? 30 : 10, title: { text: t("axis.trueAngle") } },
        yaxis: { automargin: false, range: [0, top], rangemode: "tozero" },
      }),
    };
  }, [result, theme, t]);
  return (
    <div className="chart-body">
      <Plot data={data} layout={layout} ariaLabel={`${t(result.axis === "azimuth" ? "axis.azimuth" : "axis.elevation")} ${t("angle.rmseChart")}`} />
    </div>
  );
}

function OutlierChart({ result }: { result: NoiseAccuracy }) {
  const t = useT();
  const theme = useChartTheme();
  const { data, layout } = useMemo(() => {
    const x = result.sweep.snr_db;
    const percent = (values: (typeof result.sweep.max_outlier_rate)[number][]) =>
      values.map((value) => {
        const number = wire(value);
        return number === null ? null : number * 100;
      });
    const threshold = wire(result.summary.threshold_snr_db);
    const limit = result.summary.outlier_limit * 100;
    const vertical = (at: number, color: string, dash: string) => ({
      type: "line",
      xref: "x",
      yref: "paper",
      x0: at,
      x1: at,
      y0: 0,
      y1: 1,
      line: { color, width: 1.2, dash },
    });
    return {
      data: [
        {
          type: "scatter",
          mode: "lines",
          x,
          y: percent(result.sweep.max_outlier_rate),
          line: { color: theme.line, width: 1.8 },
          name: t("angle.maxOutlierSeries"),
          hovertemplate: `${t("angle.maxOutlierSeries")} %{x:.0f} dB  %{y:.1f}%<extra></extra>`,
        },
        {
          type: "scatter",
          mode: "lines",
          x,
          y: percent(result.sweep.mean_outlier_rate),
          line: { color: theme.secondary, width: 1.4, dash: "dot" },
          name: t("angle.meanOutlierSeries"),
          hovertemplate: `${t("angle.meanOutlierSeries")} %{x:.0f} dB  %{y:.1f}%<extra></extra>`,
        },
      ],
      layout: baseLayout(theme, {
        margin: { l: 52, r: 16, t: 26, b: 44 },
        showlegend: true,
        legend: {
          x: 1,
          xanchor: "right",
          y: 0.98,
          yanchor: "top",
          bgcolor: "rgba(0,0,0,0)",
          font: { size: 11, color: theme.textSecondary },
        },
        shapes: [
          { type: "line", xref: "paper", x0: 0, x1: 1, y0: limit, y1: limit, line: { color: theme.danger, width: 1.2, dash: "dash" } },
          vertical(result.snr_db, theme.accent, "solid"),
          ...(threshold !== null ? [vertical(threshold, theme.success, "dot")] : []),
        ],
        annotations: [
          {
            x: result.snr_db,
            y: 1,
            xref: "x",
            yref: "paper",
            text: t("angle.currentSnr"),
            showarrow: false,
            xanchor: "left",
            yanchor: "top",
            font: { size: 11, color: theme.accent },
          },
          ...(threshold !== null
            ? [
                {
                  x: threshold,
                  y: 0.5,
                  xref: "x",
                  yref: "paper",
                  text: t("angle.thresholdMarker", { value: trimNumber(threshold, 1) }),
                  showarrow: false,
                  xanchor: "left",
                  textangle: -90,
                  font: { size: 11, color: theme.success },
                },
              ]
            : []),
        ],
        xaxis: { range: [x[0], x[x.length - 1]], dtick: 10, title: { text: t("axis.snr") } },
        yaxis: { automargin: false, range: [0, 100], ticksuffix: "%" },
      }),
    };
  }, [result, theme, t]);
  return (
    <div className="chart-body">
      <Plot data={data} layout={layout} ariaLabel={`${t(result.axis === "azimuth" ? "axis.azimuth" : "axis.elevation")} ${t("angle.outlierChart")}`} />
    </div>
  );
}
