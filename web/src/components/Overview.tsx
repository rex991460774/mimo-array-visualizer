import { AlertTriangle, CheckCircle2, ChevronRight, MinusCircle, Settings2, XCircle } from "lucide-react";
import type { AngleMetrics, Axis, CutReason, Evaluation, LayoutCheck, RequirementCheck } from "../api/types";
import type { ReactNode } from "react";
import { type Translate, useT } from "../i18n";
import { wire } from "../lib/encoding";
import { fmt, fmtSigned, trimNumber } from "../lib/format";
import { useStore } from "../state/store";
import { Button, Callout, Spinner } from "./ui";

function cutReason(reason: CutReason, t: Translate): string {
  return reason ? t(`cut.${reason}` as const) : "—";
}

export function cutSummary(metrics: AngleMetrics, t: Translate): string {
  const negative = cutReason(metrics.negative_cut_reason, t);
  const positive = cutReason(metrics.positive_cut_reason, t);
  return negative === positive ? negative : t("cut.pair", { negative, positive });
}

export function noFoldText(metrics: AngleMetrics): string {
  const left = wire(metrics.no_fold_left);
  const right = wire(metrics.no_fold_right);
  const width = wire(metrics.no_fold_width);
  if (left === null || right === null || !Number.isFinite(left) || !Number.isFinite(right)) return "—";
  return `${fmtSigned(left)} ~ ${fmtSigned(right)}  (${fmt(width, 0, "°")})`;
}

export function marginText(metrics: AngleMetrics, t: Translate): string {
  const width = wire(metrics.no_fold_width) ?? 0;
  const limited = ["boundary_limited", "unreliable"];
  if (
    width <= 0 &&
    (limited.includes(metrics.negative_cut_reason ?? "") || limited.includes(metrics.positive_cut_reason ?? ""))
  ) {
    return t("overview.unavailable");
  }
  const margin = wire(metrics.min_peak_margin_db);
  if (margin === Number.POSITIVE_INFINITY) return t("overview.noCompetitor");
  return fmt(margin, 1, " dB");
}

/** Angle errors are refined to 0.002°: show sub-degree precision where it matters. */
export function errorText(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${value < 1 ? value.toFixed(3) : value.toFixed(2)}°`;
}

export function axisName(axis: Axis | null, t: Translate): string {
  if (!axis) return "";
  return t(axis === "azimuth" ? "axis.azimuth" : "axis.elevation");
}

export function requirementLabel(check: RequirementCheck, t: Translate): string {
  return t(`req.${check.key}` as const, { axis: axisName(check.axis, t) });
}

export function requirementValue(check: RequirementCheck, t: Translate): string {
  const actual = wire(check.actual);
  const target = wire(check.target);
  switch (check.key) {
    case "resolution":
      return `${fmt(actual, 2, "°")} / ≤ ${fmt(target, 2, "°")}`;
    case "unambiguous_fov":
      return `${fmt(actual, 0, "°")} / ${fmt(target, 0, "°")}`;
    case "max_error":
      return `${errorText(actual)} / ≤ ${fmt(target, 3, "°")}`;
    case "peak_margin":
      return `${actual === Number.POSITIVE_INFINITY ? t("overview.noCompetitor") : fmt(actual, 1, " dB")} / ≥ ${fmt(target, 1, " dB")}`;
    case "psl":
      return `${fmt(actual, 1, " dB")} / ≤ ${fmt(target, 1, " dB")}`;
    default:
      return "";
  }
}

export function StatusIcon({ status }: { status: RequirementCheck["status"] }) {
  if (status === "pass") return <CheckCircle2 size={14} className="tone-ok" />;
  if (status === "fail") return <XCircle size={14} className="tone-bad" />;
  return <MinusCircle size={14} className="subtle" />;
}

export function Overview() {
  const t = useT();
  const evaluation = useStore((state) => state.evaluation);
  const evaluating = useStore((state) => state.evaluating);
  const error = useStore((state) => state.evaluationError);
  // A failed evaluation keeps the previous result: show it as stale, not as current.
  const stale = Boolean(error && evaluation);
  return (
    <aside className={`overview${stale ? " is-stale" : ""}`} aria-label={t("overview.title")}>
      <div className="overview-section">
        <h2>
          {t("overview.title")}
          {evaluating && <Spinner />}
        </h2>
        {error && (
          <div style={{ marginBottom: 10 }}>
            <Callout tone="danger" title={t("overview.error")}>
              {error}
              {stale && <div style={{ marginTop: 4 }}>{t("overview.stale")}</div>}
            </Callout>
          </div>
        )}
        {evaluation ? <Kpis evaluation={evaluation} /> : !error && <p className="subtle">{t("overview.computing")}</p>}
      </div>
      {evaluation && (
        <>
          <RequirementSection evaluation={evaluation} />
          <div className="overview-section">
            <h2>{t("overview.angleTitle")}</h2>
            <AngleTable evaluation={evaluation} />
          </div>
          <PatternMetrics evaluation={evaluation} />
          {(evaluation.notes.length > 0 || evaluation.layout_checks.length > 0) && (
            <div className="overview-section">
              <h2>{t("overview.notes")}</h2>
              <ul className="notes">
                {evaluation.layout_checks.map((check, index) => (
                  <li key={`layout${index}`} className={check.code === "coincident" ? "bad" : ""}>
                    <AlertTriangle size={14} />
                    {layoutCheckText(check, t)}
                  </li>
                ))}
                {evaluation.notes.map((note) => (
                  <li key={note}>
                    <AlertTriangle size={14} />
                    {t(`note.${note}` as never)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </aside>
  );
}

function layoutCheckText(check: LayoutCheck, t: Translate): string {
  if (check.code === "design_outside_band") return t("layout.design_outside_band");
  return t(`layout.${check.code}` as const, {
    a: check.a ?? "",
    b: check.b ?? "",
    lambda: trimNumber(check.distance_lambda ?? 0, 3),
    mm: trimNumber(check.distance_mm ?? 0, 2),
  });
}

function Kpis({ evaluation }: { evaluation: Evaluation }) {
  const t = useT();
  const { summary, resolution } = evaluation;
  const utilization = Math.round(summary.utilization * 100);
  const resolutionKpi = (axis: Axis) => {
    const value = wire(resolution[axis].value);
    const estimate = wire(resolution[axis].estimate);
    return {
      value: fmt(value, 2, "°"),
      sub: estimate !== null && value !== null ? t("overview.resolutionSub", { value: fmt(estimate, 2, "°") }) : undefined,
    };
  };
  const az = resolutionKpi("azimuth");
  const el = resolutionKpi("elevation");
  return (
    <div className="kpi-grid">
      <Kpi label={t("overview.channels")} value={`${summary.tx_count}T × ${summary.rx_count}R`} />
      <Kpi
        label={t("overview.virtual")}
        value={`${summary.unique_count}/${summary.virtual_count}`}
        sub={`${utilization}%`}
        tone={utilization < 85 ? "warn" : undefined}
      />
      <Kpi
        label={t("overview.azAperture")}
        value={fmt(summary.x_aperture_mm, 1, " mm")}
        sub={`${fmt(summary.x_aperture_lambda, 2)} λ`}
      />
      <Kpi
        label={t("overview.elAperture")}
        value={fmt(summary.y_aperture_mm, 1, " mm")}
        sub={`${fmt(summary.y_aperture_lambda, 2)} λ`}
      />
      <Kpi label={t("overview.azResolution")} value={az.value} sub={az.sub} title={t("overview.resolutionTitle")} />
      <Kpi label={t("overview.elResolution")} value={el.value} sub={el.sub} title={t("overview.resolutionTitle")} />
    </div>
  );
}

function Kpi({
  label,
  value,
  sub,
  tone,
  title,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "warn";
  title?: string;
}) {
  return (
    <div className="kpi" title={title}>
      <span className="kpi-label" title={label}>
        {label}
      </span>
      <span className={`kpi-value ${tone ? `tone-${tone}` : ""}`}>{value}</span>
      {sub && <span className="kpi-sub">{sub}</span>}
    </div>
  );
}

function RequirementSection({ evaluation }: { evaluation: Evaluation }) {
  const t = useT();
  const openDialog = useStore((state) => state.openDialog);
  const checks = evaluation.requirements;
  const applicable = checks.filter((check) => check.status !== "na");
  const passed = applicable.filter((check) => check.status === "pass").length;
  return (
    <div className="overview-section">
      <h2>
        {t("overview.requirements")}
        {applicable.length > 0 && (
          <span className={`badge ${passed === applicable.length ? "ok" : "bad"}`}>
            {t("overview.passCount", { passed, total: applicable.length })}
          </span>
        )}
        <span style={{ flex: 1 }} />
        <Button size="sm" variant="ghost" icon={<Settings2 size={13} />} onClick={() => openDialog("settings")}>
          {t("overview.edit")}
        </Button>
      </h2>
      {checks.length === 0 ? (
        <p className="subtle" style={{ margin: 0 }}>
          {t("overview.requirementsNone")}
        </p>
      ) : (
        <ul className="checks">
          {checks.map((check, index) => (
            <li key={index}>
              <StatusIcon status={check.status} />
              <span className="check-label">{requirementLabel(check, t)}</span>
              <span className="check-value num">{check.status === "na" ? t("req.na") : requirementValue(check, t)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const AXES: Axis[] = ["azimuth", "elevation"];

/** Side-by-side azimuth / elevation angle evaluation: the two axes are compared row by row. */
function AngleTable({ evaluation }: { evaluation: Evaluation }) {
  const t = useT();
  const results = AXES.map((axis) => {
    const result = evaluation.angle[axis];
    return result && !("error" in result) ? result : null;
  });
  const failures = AXES.flatMap((axis) => {
    const result = evaluation.angle[axis];
    return result && "error" in result ? [{ axis, error: result.error }] : [];
  });
  const row = (label: string, cell: (metrics: AngleMetrics) => ReactNode) => (
    <tr>
      <th scope="row">{label}</th>
      {results.map((metrics, index) => (
        <td key={AXES[index]}>{metrics ? cell(metrics) : "—"}</td>
      ))}
    </tr>
  );
  return (
    <>
      <table className="angle-table">
        <thead>
          <tr>
            <th>
              <span className="sr-only">{t("band.metric")}</span>
            </th>
            {AXES.map((axis) => (
              <th key={axis} scope="col">
                {axisName(axis, t)}
                {!evaluation.capability[axis] && <span className="badge">{t("overview.noAperture")}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">{t("top.fov")}</th>
            {AXES.map((axis) => (
              <td key={axis}>
                {fmtSigned(evaluation.fov[axis][0])} ~ {fmtSigned(evaluation.fov[axis][1])}
              </td>
            ))}
          </tr>
          {row(t("overview.noFold"), (metrics) => {
            const left = wire(metrics.no_fold_left);
            const right = wire(metrics.no_fold_right);
            if (left === null || right === null || !Number.isFinite(left) || !Number.isFinite(right)) return "—";
            return (
              <>
                {fmtSigned(left)} ~ {fmtSigned(right)}
                <span className="cell-sub">{fmt(wire(metrics.no_fold_width), 0, "°")}</span>
              </>
            );
          })}
          {row(t("overview.focusError"), (metrics) => errorText(wire(metrics.focus_max_abs_error)))}
          {row(t("overview.peakMargin"), (metrics) => marginText(metrics, t))}
          {row(t("overview.cutReason"), (metrics) => <span className="cell-text">{cutSummary(metrics, t)}</span>)}
        </tbody>
      </table>
      {failures.map(({ axis, error }) => (
        <div key={axis} style={{ marginTop: 8 }}>
          <Callout tone="danger" title={axisName(axis, t)}>
            {error}
          </Callout>
        </div>
      ))}
    </>
  );
}

function PatternMetrics({ evaluation }: { evaluation: Evaluation }) {
  const t = useT();
  const m = evaluation.metrics;
  const at = (value: number | null, angle: number | null) =>
    value === null || !Number.isFinite(value) ? "—" : `${fmt(value, 1, " dB")}${angle === null ? "" : ` @ ${fmtSigned(angle, 1)}`}`;
  const sidelobeAt = `Az ${fmtSigned(wire(m.sidelobe_azimuth), 1)}, El ${fmtSigned(wire(m.sidelobe_elevation), 1)}`;
  return (
    <div className="overview-section">
      <details className="collapsible">
        <summary>
          <ChevronRight size={14} className="chevron" />
          <h2 style={{ margin: 0 }}>{t("overview.patternTitle")}</h2>
        </summary>
        <dl className="metric-list" style={{ marginTop: 10 }}>
          <dt>{t("overview.az3db")}</dt>
          <dd>{fmt(wire(m.azimuth_3db_beamwidth), 2, "°")}</dd>
          <dt>{t("overview.el3db")}</dt>
          <dd>{fmt(wire(m.elevation_3db_beamwidth), 2, "°")}</dd>
          <dt>{t("overview.azPsl")}</dt>
          <dd>{fmt(wire(m.azimuth_psl_db), 2, " dB")}</dd>
          <dt>{t("overview.elPsl")}</dt>
          <dd>{fmt(wire(m.elevation_psl_db), 2, " dB")}</dd>
          <dt>{t("overview.psl2d")}</dt>
          <dd title={sidelobeAt}>{fmt(wire(m.psl_db), 2, " dB")}</dd>
          <dt>{t("overview.islr")}</dt>
          <dd>{fmt(wire(m.azimuth_islr_db), 2, " dB")}</dd>
          <dt>{t("overview.firstSidelobe")}</dt>
          <dd>{at(wire(m.azimuth_first_sidelobe_db), wire(m.azimuth_first_sidelobe_angle))}</dd>
          <dt>{t("overview.grating")}</dt>
          <dd>{at(wire(m.azimuth_grating_lobe_db), wire(m.azimuth_grating_lobe_angle))}</dd>
        </dl>
      </details>
    </div>
  );
}
