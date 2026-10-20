import { useMemo } from "react";
import type { Axis, DbfBank } from "../api/types";
import { Plot } from "../charts/Plot";
import { baseLayout, useChartTheme } from "../charts/theme";
import { cutSummary, errorText, marginText, noFoldText } from "../components/Overview";
import { Spinner } from "../components/ui";
import { useT } from "../i18n";
import { wire } from "../lib/encoding";
import { trimNumber } from "../lib/format";
import { useDbfBank } from "../state/compute";
import { useStore } from "../state/store";
import { EmptyCapability } from "./EmptyCapability";

export function AngleView() {
  const evaluation = useStore((state) => state.evaluation);
  const capability = evaluation?.capability ?? { azimuth: true, elevation: true, two_d: true };
  return (
    <div className="angle-grid">
      <AngleAxisPanel axis="azimuth" available={capability.azimuth} />
      <AngleAxisPanel axis="elevation" available={capability.elevation} />
    </div>
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
      <Plot data={data} layout={layout} />
    </div>
  );
}
