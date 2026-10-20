import { GitCompare, RefreshCw } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { AngleMetrics, Axis, BandSweep, CompareItem, PerformanceSummary, ProjectSummary, RequirementCheck } from "../api/types";
import { errorText, marginText, noFoldText, StatusIcon } from "../components/Overview";
import { Button, Callout, Spinner } from "../components/ui";
import { type Translate, useT } from "../i18n";
import { wire } from "../lib/encoding";
import { fmt, trimNumber } from "../lib/format";
import { evaluationKey } from "../state/compute";
import { useStore } from "../state/store";

const MAX_PICK = 7;

type Summary = Partial<PerformanceSummary>;

function angleOf(summary: Summary, axis: Axis): AngleMetrics | null {
  const value = summary.angle?.[axis];
  return value && !("error" in value) ? value : null;
}

function checkStatus(summary: Summary, key: RequirementCheck["key"], axis: Axis | null) {
  return summary.requirements?.find((check) => check.key === key && check.axis === axis)?.status;
}

function cellClass(status: string | undefined) {
  return status === "fail" ? "cell-fail" : status === "pass" ? "cell-pass" : "";
}

interface MetricRow {
  label: string;
  render: (summary: Summary) => ReactNode;
  status?: (summary: Summary) => string | undefined;
}

function metricRows(t: Translate): MetricRow[] {
  const rows: MetricRow[] = [];
  for (const axis of ["azimuth", "elevation"] as Axis[]) {
    const name = t(axis === "azimuth" ? "axis.azimuth" : "axis.elevation");
    rows.push(
      {
        label: t("band.resolution", { axis: name }),
        render: (s) => fmt(wire(s.resolution?.[axis].value ?? null), 2, "°"),
        status: (s) => checkStatus(s, "resolution", axis),
      },
      {
        label: t("band.noFold", { axis: name }),
        render: (s) => (angleOf(s, axis) ? noFoldText(angleOf(s, axis)!) : "—"),
        status: (s) => checkStatus(s, "unambiguous_fov", axis),
      },
      {
        label: t("band.maxError", { axis: name }),
        render: (s) => (angleOf(s, axis) ? errorText(wire(angleOf(s, axis)!.focus_max_abs_error)) : "—"),
        status: (s) => checkStatus(s, "max_error", axis),
      },
      {
        label: t("band.margin", { axis: name }),
        render: (s) => (angleOf(s, axis) ? marginText(angleOf(s, axis)!, t) : "—"),
        status: (s) => checkStatus(s, "peak_margin", axis),
      },
    );
  }
  rows.push(
    {
      label: t("band.psl"),
      render: (s) => fmt(wire(s.psl_db ?? null), 1, " dB"),
      status: (s) => checkStatus(s, "psl", null),
    },
    {
      label: t("band.checks"),
      render: (s) => {
        const applicable = (s.requirements ?? []).filter((check) => check.status !== "na");
        if (applicable.length === 0) return "—";
        const passed = applicable.filter((check) => check.status === "pass").length;
        return (
          <span className={`badge ${passed === applicable.length ? "ok" : "bad"}`}>
            {t("overview.passCount", { passed, total: applicable.length })}
          </span>
        );
      },
    },
  );
  return rows;
}

export function BandView() {
  return (
    <div className="stack">
      <BandPanel />
      <ComparePanel />
    </div>
  );
}

function BandPanel() {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const key = evaluationKey(project);
  const [sweep, setSweep] = useState<BandSweep | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    const timer = window.setTimeout(() => {
      api
        .band(project, controller.signal)
        .then((result) => {
          setSweep(result);
          setError(null);
        })
        .catch((reason) => {
          if ((reason as Error).name !== "AbortError") setError(errorMessage(reason));
        })
        .finally(() => !controller.signal.aborted && setLoading(false));
    }, 150);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const rows = metricRows(t);
  const roleLabel = (role: string) =>
    role
      .split("+")
      .map((part) => t(`band.role.${part}` as "band.role.start"))
      .join(" / ");

  return (
    <section className="panel">
      <header className="panel-header">
        <div className="panel-heading">
          <span className="panel-title">
            {t("band.title")}
            {sweep && (
              <span className="subtle" style={{ fontWeight: 400, marginLeft: 8 }}>
                {trimNumber(sweep.band.start_ghz, 3)}–{trimNumber(sweep.band.stop_ghz, 3)} GHz
              </span>
            )}
          </span>
          <span className="panel-subtitle">{t("band.subtitle")}</span>
        </div>
        <div className="panel-tools">{loading && <Spinner />}</div>
      </header>
      <div style={{ padding: 12 }} className="stack">
        {error && <Callout tone="danger">{error}</Callout>}
        {sweep && !sweep.design_in_band && <Callout tone="warning">{t("layout.design_outside_band")}</Callout>}
        {sweep?.uses_single_frequency_data && <Callout tone="info">{t("band.singleFrequency")}</Callout>}
        {sweep && (
          <div className="table-wrap">
            <table className="table metric-table">
              <thead>
                <tr>
                  <th>{t("band.metric")}</th>
                  {sweep.points.map((point) => (
                    <th key={point.frequency_ghz} className="num">
                      {trimNumber(point.frequency_ghz, 3)} GHz
                      <div className="subtle" style={{ fontWeight: 400 }}>
                        {roleLabel(point.role)}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{t("band.wavelength")}</td>
                  {sweep.points.map((point) => (
                    <td key={point.frequency_ghz} className="num">
                      {fmt(point.wavelength_mm, 3, " mm")}
                    </td>
                  ))}
                </tr>
                {rows.map((row) => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    {sweep.points.map((point) => (
                      <td key={point.frequency_ghz} className={`num ${cellClass(row.status?.(point))}`}>
                        {row.status?.(point) && <StatusIcon status={row.status(point) as "pass"} />} {row.render(point)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

function ComparePanel() {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const projectId = useStore((state) => state.projectId);
  const [library, setLibrary] = useState<ProjectSummary[] | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [results, setResults] = useState<CompareItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.listProjects().then(
      (items) => setLibrary(items.filter((item) => item.id !== projectId)),
      (reason) => setError(errorMessage(reason)),
    );
  }, [projectId]);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const records = await Promise.all(picked.map((id) => api.getProject(id)));
      setResults(await api.compare([project, ...records.map((record) => record.project)]));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  };

  const rows = metricRows(t);
  return (
    <section className="panel">
      <header className="panel-header">
        <div className="panel-heading">
          <span className="panel-title">{t("compare.title")}</span>
          <span className="panel-subtitle">{t("compare.subtitle")}</span>
        </div>
        <div className="panel-tools">
          {loading && <Spinner />}
          <Button size="sm" variant="primary" icon={results ? <RefreshCw size={13} /> : <GitCompare size={13} />} onClick={run} disabled={loading}>
            {t("compare.run")}
          </Button>
        </div>
      </header>
      <div style={{ padding: 12 }} className="stack">
        {error && <Callout tone="danger">{error}</Callout>}
        {library && library.length === 0 && <p className="subtle" style={{ margin: 0 }}>{t("compare.empty")}</p>}
        {library && library.length > 0 && (
          <div className="pick-list">
            <span className="subtle">{t("compare.pickHint")}</span>
            {library.map((item) => (
              <label key={item.id} className="checkbox pick-item">
                <input
                  type="checkbox"
                  checked={picked.includes(item.id)}
                  disabled={!picked.includes(item.id) && picked.length >= MAX_PICK}
                  onChange={(event) =>
                    setPicked((current) =>
                      event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id),
                    )
                  }
                />
                {item.name || t("project.untitled")}
                <span className="subtle">
                  {item.tx_count}T{item.rx_count}R · {item.frequency_ghz} GHz
                </span>
              </label>
            ))}
          </div>
        )}
        {results && (
          <div className="table-wrap">
            <table className="table metric-table">
              <thead>
                <tr>
                  <th>{t("band.metric")}</th>
                  {results.map((item, index) => (
                    <th key={index} className="num">
                      {item.name}
                      {index === 0 && <div className="subtle" style={{ fontWeight: 400 }}>{t("compare.current")}</div>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{t("compare.band")}</td>
                  {results.map((item, index) => (
                    <td key={index} className="num">
                      {trimNumber(item.band.start_ghz, 2)}–{trimNumber(item.band.stop_ghz, 2)} GHz
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>{t("compare.design")}</td>
                  {results.map((item, index) => (
                    <td key={index} className="num">{trimNumber(item.design_ghz, 3)} GHz</td>
                  ))}
                </tr>
                <tr>
                  <td>{t("compare.channels")}</td>
                  {results.map((item, index) => (
                    <td key={index} className="num">{item.tx_count}T × {item.rx_count}R</td>
                  ))}
                </tr>
                <tr>
                  <td>{t("compare.fov")}</td>
                  {results.map((item, index) => (
                    <td key={index} className="num">
                      Az {item.fov.azimuth[0]}~{item.fov.azimuth[1]}° · El {item.fov.elevation[0]}~{item.fov.elevation[1]}°
                    </td>
                  ))}
                </tr>
                {rows.map((row) => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    {results.map((item, index) => (
                      <td key={index} className={`num ${item.error ? "" : cellClass(row.status?.(item))}`}>
                        {item.error ? (
                          index === 0 || row === rows[0] ? <span className="tone-bad">{item.error}</span> : "—"
                        ) : (
                          <>
                            {row.status?.(item) && <StatusIcon status={row.status(item) as "pass"} />} {row.render(item)}
                          </>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
