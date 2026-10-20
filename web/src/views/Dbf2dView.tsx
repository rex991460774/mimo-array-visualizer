import { Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { Dbf2dFrame, Project } from "../api/types";
import { Plot } from "../charts/Plot";
import { baseLayout, useChartTheme } from "../charts/theme";
import { Button, Spinner } from "../components/ui";
import { useT } from "../i18n";
import { decodeMatrix, matrixRows } from "../lib/encoding";
import { dbToMagnitude, fmt, fmtSigned } from "../lib/format";
import { dbfKey } from "../state/compute";
import { useStore } from "../state/store";
import { EmptyCapability } from "./EmptyCapability";

const FRAME_CACHE_LIMIT = 400;
const PREFETCH = 8;
const PLAY_FPS = 10;

// Perceptually ordered dark-to-bright scale (magma-like) for correlation maps.
const MAGMA: [number, string][] = [
  [0, "#000004"],
  [0.13, "#1c1044"],
  [0.25, "#4f127b"],
  [0.38, "#812581"],
  [0.5, "#b5367a"],
  [0.63, "#e55064"],
  [0.75, "#fb8761"],
  [0.88, "#fec287"],
  [1, "#fcfdbf"],
];

interface DecodedFrame {
  frame: Dbf2dFrame;
  rows: number[][];
}

function angleKey(az: number, el: number) {
  return `${az}|${el}`;
}

function wrapAngle(value: number, range: [number, number]) {
  return value > range[1] ? range[0] : value;
}

function useFrameCache(project: Project, enabled: boolean, maxBatch: number) {
  const key = dbfKey(project);
  const cache = useRef(new Map<string, DecodedFrame>());
  const inflight = useRef(new Set<string>());
  const [scan, setScan] = useState<{ az: number[]; el: number[] } | null>(null);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const projectRef = useRef(project);
  projectRef.current = project;

  useEffect(() => {
    cache.current.clear();
    inflight.current.clear();
    setError(null);
    setVersion((value) => value + 1);
  }, [key]);

  const request = useCallback(
    (angles: [number, number][]) => {
      if (!enabled) return;
      const pending = angles.filter(([az, el]) => {
        const id = angleKey(az, el);
        return !cache.current.has(id) && !inflight.current.has(id);
      });
      if (pending.length === 0) return;
      const requestKey = key;
      for (let start = 0; start < pending.length; start += maxBatch) {
        const chunk = pending.slice(start, start + maxBatch);
        chunk.forEach(([az, el]) => inflight.current.add(angleKey(az, el)));
        api
          .dbf2d(
            projectRef.current,
            chunk.map(([azimuth, elevation]) => ({ azimuth, elevation })),
          )
          .then((result) => {
            if (requestKey !== dbfKey(projectRef.current)) return;
            setScan((current) => current ?? { az: result.scan_azimuths, el: result.scan_elevations });
            for (const frame of result.frames) {
              const id = angleKey(frame.true_azimuth, frame.true_elevation);
              inflight.current.delete(id);
              cache.current.set(id, { frame, rows: matrixRows(decodeMatrix(frame.spectrum_db)) });
              while (cache.current.size > FRAME_CACHE_LIMIT) {
                const oldest = cache.current.keys().next().value;
                if (oldest === undefined) break;
                cache.current.delete(oldest);
              }
            }
            setError(null);
            setVersion((value) => value + 1);
          })
          .catch((reason) => {
            chunk.forEach(([az, el]) => inflight.current.delete(angleKey(az, el)));
            setError(errorMessage(reason));
          });
      }
    },
    [enabled, key, maxBatch],
  );

  const get = useCallback((az: number, el: number) => cache.current.get(angleKey(az, el)) ?? null, []);
  return { request, get, scan, version, error };
}

export function Dbf2dView() {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const config = useStore((state) => state.config)!;
  const evaluation = useStore((state) => state.evaluation);
  const available = evaluation?.capability.two_d ?? true;
  const azRange = project.fov.azimuth;
  const elRange = project.fov.elevation;
  const [trueAz, setTrueAz] = useState(0);
  const [trueEl, setTrueEl] = useState(0);
  const [playAz, setPlayAz] = useState(false);
  const [playEl, setPlayEl] = useState(false);
  const frames = useFrameCache(project, available, config.limits.max_2d_frames_per_request);
  const { request, get } = frames;

  // Show the most recent frame that is available while the next one loads.
  const current = get(trueAz, trueEl);
  const [shown, setShown] = useState<DecodedFrame | null>(null);
  useEffect(() => {
    if (current) setShown(current);
  }, [current, frames.version]);

  useEffect(() => {
    if (!available) return;
    const angles: [number, number][] = [[trueAz, trueEl]];
    if (playAz || playEl) {
      let az = trueAz;
      let el = trueEl;
      for (let i = 0; i < PREFETCH; i += 1) {
        if (playAz) az = wrapAngle(az + 1, azRange);
        if (playEl) el = wrapAngle(el + 1, elRange);
        angles.push([az, el]);
      }
    }
    const timer = window.setTimeout(() => request(angles), playAz || playEl ? 0 : 60);
    return () => window.clearTimeout(timer);
  }, [trueAz, trueEl, playAz, playEl, available, request, frames.version, azRange, elRange]);

  useEffect(() => {
    if (!playAz && !playEl) return;
    const timer = window.setInterval(() => {
      const nextAz = playAz ? wrapAngle(trueAz + 1, azRange) : trueAz;
      const nextEl = playEl ? wrapAngle(trueEl + 1, elRange) : trueEl;
      if (get(nextAz, nextEl)) {
        setTrueAz(nextAz);
        setTrueEl(nextEl);
      }
    }, 1000 / PLAY_FPS);
    return () => window.clearInterval(timer);
  }, [playAz, playEl, trueAz, trueEl, get, azRange, elRange]);

  // Keep the true angle inside the FOV when it changes.
  useEffect(() => {
    setTrueAz((value) => Math.min(Math.max(value, azRange[0]), azRange[1]));
    setTrueEl((value) => Math.min(Math.max(value, elRange[0]), elRange[1]));
  }, [azRange, elRange]);

  const loading = available && !current;

  return (
    <div className="dbf2d-layout">
      <section className="panel">
        <header className="panel-header">
          <div className="panel-heading">
            <span className="panel-title">{t("dbf2d.title")}</span>
            <span className="panel-subtitle">{t("dbf2d.hint")}</span>
          </div>
          {shown && available && (
            <div className="panel-tools readout">
              <span className="readout-item">
                <span className="readout-label">{t("dbf2d.peak")}</span>
                <span className="readout-value">
                  {fmtSigned(shown.frame.peak_azimuth)} / {fmtSigned(shown.frame.peak_elevation)}
                </span>
              </span>
              <span className="readout-item">
                <span className="readout-label">{t("dbf2d.delta")}</span>
                <span className="readout-value">
                  {fmtSigned(shown.frame.peak_azimuth - shown.frame.true_azimuth)} /{" "}
                  {fmtSigned(shown.frame.peak_elevation - shown.frame.true_elevation)}
                </span>
              </span>
              <span className="readout-item">
                <span className="readout-label">peak</span>
                <span className="readout-value">{fmt(shown.frame.peak_db, 2, " dB")}</span>
              </span>
            </div>
          )}
        </header>
        <div className="panel-body">
          {available && shown && frames.scan && (
            <Heatmap
              frame={shown}
              fov={project.fov}
              scanAz={frames.scan.az}
              scanEl={frames.scan.el}
              trueAz={trueAz}
              trueEl={trueEl}
              onPick={(az, el) => {
                setPlayAz(false);
                setPlayEl(false);
                setTrueAz(Math.min(Math.max(Math.round(az), azRange[0]), azRange[1]));
                setTrueEl(Math.min(Math.max(Math.round(el), elRange[0]), elRange[1]));
              }}
            />
          )}
          {loading && (
            <div className="loading-overlay">
              <Spinner /> {t("dbf2d.loading")}
            </div>
          )}
          {available && frames.error && (
            <div className="empty-state">
              <div className="empty-state-inner">
                <h3>{t("overview.error")}</h3>
                <p>{frames.error}</p>
              </div>
            </div>
          )}
          {!available && (
            <EmptyCapability
              title={t("empty.twoD")}
              body={t("empty.twoDBody")}
              actionView={evaluation?.capability.azimuth || evaluation?.capability.elevation ? "dbf1d" : "array"}
            />
          )}
        </div>
        {available && (
          <footer className="panel-footer">
            <div className="dbf2d-controls">
              <AxisScrubber
                label={t("dbf2d.trueAz")}
                range={azRange}
                value={trueAz}
                playing={playAz}
                playLabel={t("dbf2d.playAz")}
                pauseLabel={t("dbf2d.pauseAz")}
                onToggle={() => setPlayAz((value) => !value)}
                onChange={(value) => {
                  setPlayAz(false);
                  setTrueAz(value);
                }}
              />
              <AxisScrubber
                label={t("dbf2d.trueEl")}
                range={elRange}
                value={trueEl}
                playing={playEl}
                playLabel={t("dbf2d.playEl")}
                pauseLabel={t("dbf2d.pauseEl")}
                onToggle={() => setPlayEl((value) => !value)}
                onChange={(value) => {
                  setPlayEl(false);
                  setTrueEl(value);
                }}
              />
            </div>
            <Button
              size="sm"
              variant="ghost"
              icon={<RotateCcw size={14} />}
              onClick={() => {
                setPlayAz(false);
                setPlayEl(false);
                setTrueAz(0);
                setTrueEl(0);
              }}
            >
              {t("dbf2d.reset")}
            </Button>
          </footer>
        )}
      </section>
    </div>
  );
}

function AxisScrubber({
  label,
  range,
  value,
  playing,
  playLabel,
  pauseLabel,
  onToggle,
  onChange,
}: {
  label: string;
  range: [number, number];
  value: number;
  playing: boolean;
  playLabel: string;
  pauseLabel: string;
  onToggle: () => void;
  onChange: (value: number) => void;
}) {
  return (
    <div className="scrubber">
      <Button size="sm" variant={playing ? "default" : "primary"} icon={playing ? <Pause size={14} /> : <Play size={14} />} onClick={onToggle}>
        {playing ? pauseLabel : playLabel}
      </Button>
      <span className="subtle" style={{ whiteSpace: "nowrap" }}>
        {label}
      </span>
      <input
        type="range"
        className="slider"
        min={range[0]}
        max={range[1]}
        step={1}
        value={value}
        aria-label={label}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <span className="angle-value">{fmtSigned(value)}</span>
    </div>
  );
}

function Heatmap({
  frame,
  fov,
  scanAz,
  scanEl,
  trueAz,
  trueEl,
  onPick,
}: {
  frame: DecodedFrame;
  fov: { azimuth: [number, number]; elevation: [number, number] };
  scanAz: number[];
  scanEl: number[];
  trueAz: number;
  trueEl: number;
  onPick: (az: number, el: number) => void;
}) {
  const t = useT();
  const theme = useChartTheme();
  const display = useStore((state) => state.display);
  const magnitude = display === "magnitude";
  const z = useMemo(
    () =>
      frame.rows.map((row) =>
        row.map((value) => (magnitude ? dbToMagnitude(value) : Math.max(-40, Math.min(0, value)))),
      ),
    [frame, magnitude],
  );

  const data = useMemo(
    () => [
      {
        type: "heatmap",
        x: scanAz,
        y: scanEl,
        z,
        zmin: magnitude ? 0 : -40,
        zmax: magnitude ? 1 : 0,
        colorscale: MAGMA,
        colorbar: {
          title: { text: t(magnitude ? "axis.correlationMag" : "axis.correlationDb"), side: "right", font: { size: 11, color: theme.textSecondary } },
          thickness: 12,
          outlinewidth: 0,
          tickfont: { size: 10, color: theme.textSecondary },
          len: 0.9,
        },
        hovertemplate: magnitude
          ? "Az %{x:+.0f}°  El %{y:+.0f}°<br>%{z:.3f}<extra></extra>"
          : "Az %{x:+.0f}°  El %{y:+.0f}°<br>%{z:.2f} dB<extra></extra>",
      },
      {
        type: "scatter",
        mode: "markers",
        x: [frame.frame.peak_azimuth],
        y: [frame.frame.peak_elevation],
        marker: { symbol: "x-thin", size: 12, color: "#6ea6ff", line: { width: 2.5, color: "#6ea6ff" } },
        hoverinfo: "skip",
      },
    ],
    [scanAz, scanEl, z, frame, magnitude, theme, t],
  );

  const layout = useMemo(
    () =>
      baseLayout(theme, {
        margin: { l: 58, r: 8, t: 12, b: 46 },
        hovermode: "closest",
        shapes: [
          { type: "line", x0: trueAz, x1: trueAz, y0: scanEl[0], y1: scanEl[scanEl.length - 1], line: { color: "rgba(255,255,255,0.85)", width: 1 } },
          { type: "line", x0: scanAz[0], x1: scanAz[scanAz.length - 1], y0: trueEl, y1: trueEl, line: { color: "rgba(255,255,255,0.85)", width: 1 } },
          {
            type: "rect",
            x0: fov.azimuth[0],
            x1: fov.azimuth[1],
            y0: fov.elevation[0],
            y1: fov.elevation[1],
            line: { color: "rgba(255,255,255,0.55)", width: 1, dash: "dot" },
          },
        ],
        xaxis: { title: { text: t("axis.azAngle") }, range: [scanAz[0] - 0.5, scanAz[scanAz.length - 1] + 0.5], showgrid: false, zeroline: false },
        yaxis: { title: { text: t("axis.elAngle") }, range: [scanEl[0] - 0.5, scanEl[scanEl.length - 1] + 0.5], showgrid: false, zeroline: false },
      }),
    [theme, trueAz, trueEl, t, scanAz, scanEl, fov],
  );

  return (
    <div className="chart-body">
      <Plot data={data} layout={layout} onClick={(point) => onPick(point.x, point.y)} ariaLabel={t("dbf2d.title")} />
    </div>
  );
}
