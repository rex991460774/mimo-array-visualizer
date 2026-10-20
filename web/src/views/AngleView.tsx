import { ImageDown } from "lucide-react";
import { useMemo } from "react";
import { api } from "../api/client";
import type { Axis, DbfBank } from "../api/types";
import { Plot } from "../charts/Plot";
import { baseLayout, useChartTheme } from "../charts/theme";
import { Button, Spinner } from "../components/ui";
import { useT } from "../i18n";
import { wire } from "../lib/encoding";
import { useDbfBank } from "../state/compute";
import { useExportJob } from "../state/jobs";
import { useStore } from "../state/store";
import { EmptyCapability } from "./EmptyCapability";

export function AngleView() {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const language = useStore((state) => state.language);
  const evaluation = useStore((state) => state.evaluation);
  const capability = evaluation?.capability ?? { azimuth: true, elevation: true, two_d: true };
  const az = useDbfBank("azimuth", capability.azimuth);
  const el = useDbfBank("elevation", capability.elevation);
  const exporter = useExportJob();

  return (
    <div className="stack" style={{ height: "100%" }}>
      <div className="panel" style={{ flex: "none" }}>
        <header className="panel-header">
          <div className="panel-heading">
            <span className="panel-title">{t("angle.title")}</span>
            <span className="panel-subtitle">{t("angle.subtitle")}</span>
          </div>
          <div className="panel-tools">
            {exporter.running && <Spinner />}
            {exporter.error && <span className="tone-bad">{exporter.error}</span>}
            <Button
              size="sm"
              icon={<ImageDown size={14} />}
              disabled={exporter.running || (!capability.azimuth && !capability.elevation)}
              onClick={() => exporter.start(() => api.createAngleErrorImage(project, 1.0, language))}
            >
              {t("angle.exportPng")}
            </Button>
          </div>
        </header>
      </div>
      <div className="angle-grid" style={{ flex: 1 }}>
        <AnglePanel axis="azimuth" kind="error" state={az} available={capability.azimuth} />
        <AnglePanel axis="elevation" kind="error" state={el} available={capability.elevation} />
        <AnglePanel axis="azimuth" kind="margin" state={az} available={capability.azimuth} />
        <AnglePanel axis="elevation" kind="margin" state={el} available={capability.elevation} />
      </div>
    </div>
  );
}

function AnglePanel({
  axis,
  kind,
  state,
  available,
}: {
  axis: Axis;
  kind: "error" | "margin";
  state: { data: DbfBank | null; loading: boolean; error: string | null };
  available: boolean;
}) {
  const t = useT();
  const axisLabel = t(axis === "azimuth" ? "axis.azimuth" : "axis.elevation");
  return (
    <section className="panel">
      <header className="panel-header" style={{ minHeight: 40 }}>
        <span className="panel-title">
          {t(kind === "error" ? "angle.errorChart" : "angle.marginChart", { axis: axisLabel })}
        </span>
        {state.loading && (
          <span className="panel-tools">
            <Spinner />
          </span>
        )}
      </header>
      <div className="panel-body">
        {available && state.data && <AngleChart bank={state.data} kind={kind} />}
        {available && state.error && <div className="empty-state"><p>{state.error}</p></div>}
        {!available && <EmptyCapability title={t(axis === "azimuth" ? "empty.azimuth" : "empty.elevation")} />}
      </div>
    </section>
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
          shapes: band,
          xaxis: { title: { text: t("axis.trueAngle") }, range: [x[0], x[x.length - 1]], dtick: x[x.length - 1] - x[0] > 90 ? 30 : 10 },
          yaxis: { title: { text: t("axis.error") }, range: [-limit, limit], zeroline: true },
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
        shapes: [
          ...band,
          { type: "line", xref: "paper", x0: 0, x1: 1, y0: threshold, y1: threshold, line: { color: theme.danger, width: 1.2, dash: "dash" } },
        ],
        xaxis: { title: { text: t("axis.trueAngle") }, range: [x[0], x[x.length - 1]], dtick: x[x.length - 1] - x[0] > 90 ? 30 : 10 },
        yaxis: { title: { text: t("axis.margin") }, range: [0, top * 1.04], rangemode: "tozero" },
      }),
    };
  }, [bank, kind, theme, threshold, left, right, t]);

  return (
    <div className="chart-body">
      <Plot data={data} layout={layout} />
    </div>
  );
}
