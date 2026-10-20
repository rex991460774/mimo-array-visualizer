import { AlertTriangle, ChevronRight } from "lucide-react";
import type { AngleMetrics, Axis, CutReason, Evaluation } from "../api/types";
import { type Translate, useT } from "../i18n";
import { wire } from "../lib/encoding";
import { fmt, fmtSigned } from "../lib/format";
import { useStore } from "../state/store";
import { Callout, Spinner } from "./ui";

function cutReason(reason: CutReason, t: Translate): string {
  return reason ? t(`cut.${reason}` as const) : "—";
}

export function cutSummary(metrics: AngleMetrics, t: Translate): string {
  const negative = cutReason(metrics.negative_cut_reason, t);
  const positive = cutReason(metrics.positive_cut_reason, t);
  return negative === positive ? negative : t("cut.pair", { negative, positive });
}

function noFoldText(metrics: AngleMetrics): string {
  const left = wire(metrics.no_fold_left);
  const right = wire(metrics.no_fold_right);
  const width = wire(metrics.no_fold_width);
  if (left === null || right === null || !Number.isFinite(left) || !Number.isFinite(right)) return "—";
  return `${fmtSigned(left)} ~ ${fmtSigned(right)}  (${fmt(width, 0, "°")})`;
}

function marginText(metrics: AngleMetrics, t: Translate): string {
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

function gradeTone(grade: string): string {
  if (grade === "Good") return "ok";
  if (grade === "Acceptable") return "";
  if (grade === "Risky") return "warn";
  return "bad";
}

export function Overview() {
  const t = useT();
  const evaluation = useStore((state) => state.evaluation);
  const evaluating = useStore((state) => state.evaluating);
  const error = useStore((state) => state.evaluationError);
  return (
    <aside className="overview" aria-label={t("overview.title")}>
      <div className="overview-section">
        <h3>
          {t("overview.title")}
          {evaluating && <Spinner />}
        </h3>
        {error && (
          <div style={{ marginBottom: 10 }}>
            <Callout tone="danger" title={t("overview.error")}>
              {error}
            </Callout>
          </div>
        )}
        {evaluation ? <Kpis evaluation={evaluation} /> : !error && <p className="subtle">{t("overview.computing")}</p>}
      </div>
      {evaluation && (
        <>
          <div className="overview-section">
            <h3>{t("overview.angleTitle")}</h3>
            <AngleCard axis="azimuth" evaluation={evaluation} />
            <AngleCard axis="elevation" evaluation={evaluation} />
          </div>
          <PatternMetrics evaluation={evaluation} />
          {evaluation.notes.length > 0 && (
            <div className="overview-section">
              <h3>{t("overview.notes")}</h3>
              <ul className="notes">
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

function Kpis({ evaluation }: { evaluation: Evaluation }) {
  const t = useT();
  const { summary, metrics } = evaluation;
  const utilization = Math.round(summary.utilization * 100);
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
        sub={`${fmt(summary.x_aperture_lambda, 1)} λ`}
      />
      <Kpi
        label={t("overview.elAperture")}
        value={fmt(summary.y_aperture_mm, 1, " mm")}
        sub={`${fmt(summary.y_aperture_lambda, 1)} λ`}
      />
      <Kpi label={t("overview.azResolution")} value={fmt(wire(metrics.azimuth_resolution), 2, "°")} />
      <Kpi label={t("overview.elResolution")} value={fmt(wire(metrics.elevation_resolution), 2, "°")} />
    </div>
  );
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "warn" }) {
  return (
    <div className="kpi">
      <span className="kpi-label" title={label}>
        {label}
      </span>
      <span className={`kpi-value ${tone ? `tone-${tone}` : ""}`}>{value}</span>
      {sub && <span className="kpi-sub">{sub}</span>}
    </div>
  );
}

function AngleCard({ axis, evaluation }: { axis: Axis; evaluation: Evaluation }) {
  const t = useT();
  const result = evaluation.angle[axis];
  const title = t(axis === "azimuth" ? "axis.azimuth" : "axis.elevation");
  return (
    <div className="axis-card">
      <div className="axis-card-title">
        {title}
        {!evaluation.capability[axis] && <span className="badge">{t("overview.noAperture")}</span>}
      </div>
      {result && "error" in result ? (
        <Callout tone="danger">{result.error}</Callout>
      ) : result ? (
        <dl className="metric-list">
          <dt>{t("overview.noFold")}</dt>
          <dd>{noFoldText(result)}</dd>
          <dt>{t("overview.maxError")}</dt>
          <dd>{fmt(wire(result.no_fold_max_abs_error), 1, "°")}</dd>
          <dt>{t("overview.peakMargin")}</dt>
          <dd>{marginText(result, t)}</dd>
          <dt>{t("overview.cutReason")}</dt>
          <dd>{cutSummary(result, t)}</dd>
        </dl>
      ) : null}
    </div>
  );
}

function PatternMetrics({ evaluation }: { evaluation: Evaluation }) {
  const t = useT();
  const m = evaluation.metrics;
  const at = (value: number | null, angle: number | null, prefix = "") =>
    value === null || !Number.isFinite(value) ? "—" : `${fmt(value, 1, " dB")}${angle === null ? "" : ` @ ${prefix}${fmtSigned(angle, 1)}`}`;
  return (
    <div className="overview-section">
      <details className="collapsible">
        <summary>
          <ChevronRight size={14} className="chevron" />
          <h3 style={{ margin: 0 }}>{t("overview.patternTitle")}</h3>
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
          <dd title={`Az ${wire(m.sidelobe_azimuth)}°, El ${wire(m.sidelobe_elevation)}°`}>
            {fmt(wire(m.psl_db), 2, " dB")}
          </dd>
          <dt>{t("overview.islr")}</dt>
          <dd>{fmt(wire(m.azimuth_islr_db), 2, " dB")}</dd>
          <dt>{t("overview.firstSidelobe")}</dt>
          <dd>{at(wire(m.azimuth_first_sidelobe_db), wire(m.azimuth_first_sidelobe_angle))}</dd>
          <dt>{t("overview.grating")}</dt>
          <dd>{at(wire(m.azimuth_grating_lobe_db), wire(m.azimuth_grating_lobe_angle))}</dd>
          <dt>{t("overview.frontRadar")}</dt>
          <dd>
            <span className={`badge ${gradeTone(m.front_radar_status)}`}>
              {t(`grade.${m.front_radar_status}` as never)}
            </span>
          </dd>
          <dt>{t("overview.ambiguity")}</dt>
          <dd>
            <span className={`badge ${m.elevation_ambiguity_level === "High" ? "bad" : m.elevation_ambiguity_level === "Medium" ? "warn" : "ok"}`}>
              {t(`level.${m.elevation_ambiguity_level}` as never)}
            </span>
          </dd>
        </dl>
      </details>
    </div>
  );
}
