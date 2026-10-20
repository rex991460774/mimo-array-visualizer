import { Pause, Play, RotateCcw } from "lucide-react";
import { useMemo } from "react";
import type { Axis, DbfBank } from "../api/types";
import { Plot } from "../charts/Plot";
import { baseLayout, useChartTheme } from "../charts/theme";
import { Button, Segmented, Spinner } from "../components/ui";
import { useT } from "../i18n";
import { decodeMatrix, matrixRow, wire } from "../lib/encoding";
import { dbToMagnitude, fmt, fmtSigned } from "../lib/format";
import { useDbfBank } from "../state/compute";
import { type DisplayMode, useStore } from "../state/store";
import { EmptyCapability } from "./EmptyCapability";
import { PLAYBACK_SPEEDS, usePlayback } from "./usePlayback";

export function displayValues(values: number[], mode: DisplayMode): number[] {
  return mode === "magnitude"
    ? values.map(dbToMagnitude)
    : values.map((value) => Math.max(-40, Math.min(0, Number.isFinite(value) ? value : -40)));
}

export function DbfView() {
  const evaluation = useStore((state) => state.evaluation);
  const capability = evaluation?.capability ?? { azimuth: true, elevation: true, two_d: true };
  return (
    <div className="dbf-grid">
      <DbfAxisPanel axis="azimuth" available={capability.azimuth} />
      <DbfAxisPanel axis="elevation" available={capability.elevation} />
    </div>
  );
}

function DbfAxisPanel({ axis, available }: { axis: Axis; available: boolean }) {
  const t = useT();
  const bank = useDbfBank(axis, available);
  const count = bank.data?.true_angles.length ?? 181;
  const center = bank.data ? Math.max(0, bank.data.true_angles.findIndex((angle) => angle === 0)) : 90;
  const playback = usePlayback(count, center);
  const axisLabel = t(axis === "azimuth" ? "axis.azimuth" : "axis.elevation");

  return (
    <section className="panel">
      <header className="panel-header">
        <div className="panel-heading">
          <span className="panel-title">{t("dbf.title", { axis: axisLabel })}</span>
          {bank.data && (
            <span className="panel-subtitle num">
              {t("dbf.frame", { frame: playback.index + 1, total: count })}
            </span>
          )}
        </div>
        <div className="panel-tools">
          <Segmented
            label={t("dbf.speed")}
            value={String(playback.fps)}
            options={PLAYBACK_SPEEDS.map((fps) => ({ value: String(fps), label: `${fps / 20}×` }))}
            onChange={(value) => playback.setFps(Number(value))}
          />
        </div>
      </header>
      <div className="panel-body">
        {available && bank.data && <SpectrumChart bank={bank.data} frame={playback.index} onSeek={playback.seek} />}
        {available && bank.loading && (
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
      {available && bank.data && (
        <footer className="panel-footer">
          <div className="scrubber">
            <Button
              size="sm"
              variant="primary"
              icon={playback.playing ? <Pause size={14} /> : <Play size={14} />}
              onClick={playback.toggle}
            >
              {playback.playing ? t("dbf.pause") : playback.index > 0 && playback.index < count - 1 && playback.index !== center ? t("dbf.resume") : t("dbf.play")}
            </Button>
            <Button size="sm" variant="ghost" icon={<RotateCcw size={14} />} onClick={playback.reset} title={t("dbf.stop")} aria-label={t("dbf.stop")} />
            <input
              type="range"
              className="slider"
              min={0}
              max={count - 1}
              value={playback.index}
              aria-label={t("dbf.sliderLabel", { axis: axisLabel })}
              onChange={(event) => {
                playback.setPlaying(false);
                playback.seek(Number(event.target.value));
              }}
            />
            <span className="angle-value">{fmtSigned(bank.data.true_angles[playback.index], 0)}</span>
          </div>
          <FrameReadout bank={bank.data} frame={playback.index} />
        </footer>
      )}
    </section>
  );
}

function FrameReadout({ bank, frame }: { bank: DbfBank; frame: number }) {
  const t = useT();
  const margin = wire(bank.frames.margins_db[frame]);
  const quality = bank.frames.quality[frame];
  const error = bank.frames.errors[frame];
  const errorTone = Math.abs(error) <= 1 ? "" : Math.abs(error) <= 5 ? "tone-warn" : "tone-bad";
  return (
    <div className="readout">
      <span className="readout-item">
        <span className="readout-label">{t("dbf.true")}</span>
        <span className="readout-value">{fmtSigned(bank.true_angles[frame], 0)}</span>
      </span>
      <span className="readout-item">
        <span className="readout-label">{t("dbf.peak")}</span>
        <span className="readout-value">{fmtSigned(bank.frames.estimated[frame], 0)}</span>
      </span>
      <span className="readout-item">
        <span className="readout-label">{t("dbf.error")}</span>
        <span className={`readout-value ${errorTone}`}>{fmtSigned(error, 1)}</span>
      </span>
      <span className="readout-item">
        <span className="readout-label">{t("dbf.margin")}</span>
        <span className="readout-value">
          {margin === Number.POSITIVE_INFINITY ? t("overview.noCompetitor") : fmt(margin, 1, " dB")}
        </span>
      </span>
      {quality && quality !== "normal" && (
        <span className="badge warn">{t(`cut.${quality}` as const)}</span>
      )}
    </div>
  );
}

function SpectrumChart({ bank, frame, onSeek }: { bank: DbfBank; frame: number; onSeek: (index: number) => void }) {
  const t = useT();
  const theme = useChartTheme();
  const display = useStore((state) => state.display);
  const matrix = useMemo(() => decodeMatrix(bank.spectra_db), [bank]);
  const axisTitle = t(bank.axis === "azimuth" ? "axis.azAngle" : "axis.elAngle");

  const trueAngle = bank.true_angles[frame];
  const values = useMemo(() => displayValues(matrixRow(matrix, frame), display), [matrix, frame, display]);
  const scan = bank.scan_angles;
  const peakAngle = bank.frames.estimated[frame];
  const peakIndex = scan.indexOf(peakAngle);
  const trueIndex = scan.reduce((best, angle, i) => (Math.abs(angle - trueAngle) < Math.abs(scan[best] - trueAngle) ? i : best), 0);
  const magnitude = display === "magnitude";

  const data = useMemo(
    () => [
      {
        type: "scatter",
        mode: "lines",
        x: scan,
        y: values,
        line: { color: theme.line, width: 2 },
        fill: magnitude ? "tozeroy" : "none",
        fillcolor: theme.band,
        name: t("dbf.legendSpectrum"),
        hovertemplate: magnitude ? "%{x:+.0f}°  %{y:.3f}<extra></extra>" : "%{x:+.0f}°  %{y:.2f} dB<extra></extra>",
      },
      {
        type: "scatter",
        mode: "markers",
        x: [trueAngle],
        y: [values[trueIndex]],
        marker: { size: 9, color: theme.trueAngle, line: { color: theme.surface, width: 1.5 } },
        name: t("dbf.legendTrue"),
        hoverinfo: "skip",
      },
      {
        type: "scatter",
        mode: "markers",
        x: [peakAngle],
        y: [values[peakIndex >= 0 ? peakIndex : 0]],
        marker: { size: 11, symbol: "x-thin", color: theme.peak, line: { color: theme.peak, width: 2.5 } },
        name: t("dbf.legendPeak"),
        hoverinfo: "skip",
      },
    ],
    [scan, values, trueAngle, trueIndex, peakAngle, peakIndex, theme, magnitude, t],
  );

  const layout = useMemo(
    () =>
      baseLayout(theme, {
        margin: { l: 58, r: 14, t: 14, b: 46 },
        showlegend: true,
        legend: { orientation: "h", x: 1, xanchor: "right", y: 1.02, yanchor: "bottom", font: { size: 11 } },
        shapes: [
          {
            type: "line",
            x0: trueAngle,
            x1: trueAngle,
            yref: "paper",
            y0: 0,
            y1: 1,
            line: { color: theme.trueAngle, width: 1.6 },
          },
        ],
        xaxis: { title: { text: axisTitle }, range: [-90, 90], dtick: 30, zeroline: false },
        yaxis: {
          title: { text: t(magnitude ? "axis.correlationMag" : "axis.correlationDb") },
          range: magnitude ? [-0.02, 1.04] : [-40.5, 1],
          dtick: magnitude ? 0.2 : 10,
          zeroline: false,
        },
      }),
    [theme, trueAngle, axisTitle, magnitude, t],
  );

  return (
    <div className="chart-body">
      <Plot
        data={data}
        layout={layout}
        ariaLabel={t("dbf.title", { axis: t(bank.axis === "azimuth" ? "axis.azimuth" : "axis.elevation") })}
        onClick={(point) => {
          const index = bank.true_angles.reduce(
            (best, angle, i) => (Math.abs(angle - point.x) < Math.abs(bank.true_angles[best] - point.x) ? i : best),
            0,
          );
          onSeek(index);
        }}
      />
    </div>
  );
}
