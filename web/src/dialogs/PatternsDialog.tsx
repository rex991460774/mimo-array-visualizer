import { ArrowLeftRight, Plus, Trash2, Upload, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { ChannelPatternBinding, ElementPatternPreview, PatternKind, PatternPlane, Project } from "../api/types";
import { Plot } from "../charts/Plot";
import { baseLayout, useChartTheme } from "../charts/theme";
import { Button, Callout, Dialog, Segmented, Spinner, useFilePicker } from "../components/ui";
import { type MessageKey, useT } from "../i18n";
import { fmt } from "../lib/format";
import { useStore } from "../state/store";
import { rememberAssetName, useAssetNames } from "./useAssetNames";

const PATTERN_ACCEPT = ".csv,.tsv,.txt,.xlsx,.xlsm";
const SLOTS: { kind: PatternKind; plane: PatternPlane }[] = [
  { kind: "amplitude", plane: "horizontal" },
  { kind: "amplitude", plane: "elevation" },
  { kind: "phase", plane: "horizontal" },
  { kind: "phase", plane: "elevation" },
];

function slotKey(kind: PatternKind, plane: PatternPlane): MessageKey {
  return `patternDialog.slot.${kind}.${plane}` as MessageKey;
}

function virtualNames(project: Project): string[] {
  const names: string[] = [];
  project.layout.tx.forEach((_, ti) => project.layout.rx.forEach((__, ri) => names.push(`Tx${ti + 1}Rx${ri + 1}`)));
  return names;
}

function physicalNames(project: Project): string[] {
  return [...project.layout.tx.map((_, i) => `Tx${i + 1}`), ...project.layout.rx.map((_, i) => `Rx${i + 1}`)];
}

/** Replace bindings for the same (channel, kind, plane) with the new ones. */
function mergeBindings(current: ChannelPatternBinding[], incoming: ChannelPatternBinding[]): ChannelPatternBinding[] {
  const replaced = new Set(incoming.map((b) => `${b.channel}|${b.kind}|${b.plane}`));
  return [...current.filter((b) => !replaced.has(`${b.channel}|${b.kind}|${b.plane}`)), ...incoming];
}

export function PatternsDialog({ onClose }: { onClose: () => void }) {
  const t = useT();
  return (
    <Dialog
      title={t("patternDialog.title")}
      onClose={onClose}
      size="wide"
      footer={
        <>
          <span className="spacer" />
          <Button variant="primary" onClick={onClose}>
            {t("patternDialog.done")}
          </Button>
        </>
      }
    >
      <ChannelPatternsSection />
      <ElementPatternSection />
    </Dialog>
  );
}

function ChannelPatternsSection() {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const { updateProject, setStatus } = useStore.getState();
  const [target, setTarget] = useState<"physical" | "virtual">("physical");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef<{ kind: PatternKind; plane: PatternPlane; channel: string | null } | null>(null);
  const bindings = project.channel_patterns;
  const names = useAssetNames(bindings.map((binding) => binding.asset));

  const physical = useMemo(() => physicalNames(project), [project]);
  const virtual = useMemo(() => virtualNames(project), [project]);
  const byChannel = useMemo(() => {
    const map = new Map<string, ChannelPatternBinding>();
    for (const binding of bindings) map.set(`${binding.channel}|${binding.kind}|${binding.plane}`, binding);
    return map;
  }, [bindings]);
  const configuredVirtual = virtual.some((name) => SLOTS.some((s) => byChannel.has(`${name}|${s.kind}|${s.plane}`)));
  const [showVirtual, setShowVirtual] = useState(configuredVirtual || target === "virtual");
  useEffect(() => {
    if (target === "virtual") setShowVirtual(true);
  }, [target]);

  const onFile = async (file: File) => {
    const request = pending.current;
    if (!request) return;
    setBusy(true);
    setError(null);
    try {
      const info = await api.uploadAsset(file);
      rememberAssetName(info.id, info.filename);
      const resolved = await api.resolveChannelPatterns({
        project,
        asset: info.id,
        kind: request.kind,
        plane: request.plane,
        target,
        channel: request.channel,
      });
      const latest = useStore.getState().project!;
      updateProject({ channel_patterns: mergeBindings(latest.channel_patterns, resolved) });
      setStatus("patternDialog.loaded", "success", { count: resolved.length, slot: t(slotKey(request.kind, request.plane)) });
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  };
  const pick = useFilePicker(PATTERN_ACCEPT, onFile);
  const request = (kind: PatternKind, plane: PatternPlane, channel: string | null) => {
    pending.current = { kind, plane, channel };
    pick();
  };

  const clearChannel = (channel: string) =>
    updateProject({ channel_patterns: bindings.filter((binding) => binding.channel !== channel) });

  const renderRow = (channel: string) => {
    const hasAny = SLOTS.some((slot) => byChannel.has(`${channel}|${slot.kind}|${slot.plane}`));
    return (
      <tr key={channel}>
        <td>
          <span className={`badge ${channel.startsWith("Tx") && !channel.includes("Rx") ? "tx" : channel.startsWith("Rx") ? "rx" : ""}`}>
            {channel}
          </span>
        </td>
        {SLOTS.map((slot) => {
          const binding = byChannel.get(`${channel}|${slot.kind}|${slot.plane}`);
          return (
            <td key={`${slot.kind}${slot.plane}`} className="slot-cell">
              {binding ? (
                <span title={`${names[binding.asset]} : ${binding.column}`}>
                  {names[binding.asset]} <span className="subtle">· {binding.column || `#${binding.column_index + 1}`}</span>
                </span>
              ) : (
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Plus size={13} />}
                  title={t("patternDialog.setSingle", { channel, slot: t(slotKey(slot.kind, slot.plane)) })}
                  aria-label={t("patternDialog.setSingle", { channel, slot: t(slotKey(slot.kind, slot.plane)) })}
                  onClick={() => request(slot.kind, slot.plane, channel)}
                  disabled={busy}
                />
              )}
            </td>
          );
        })}
        <td style={{ width: 40 }}>
          {hasAny && (
            <Button
              size="sm"
              variant="ghost"
              icon={<X size={14} />}
              title={t("patternDialog.clearChannel")}
              aria-label={t("patternDialog.clearChannel")}
              onClick={() => clearChannel(channel)}
            />
          )}
        </td>
      </tr>
    );
  };

  return (
    <div className="section">
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <h3 className="section-title" style={{ flex: 1 }}>
          {t("patternDialog.channelSection")}
        </h3>
        {busy && <Spinner />}
        <span className="subtle">{t("patternDialog.target")}</span>
        <Segmented
          value={target}
          options={[
            { value: "physical", label: t("patternDialog.physical") },
            { value: "virtual", label: t("patternDialog.virtual") },
          ]}
          onChange={setTarget}
        />
      </div>
      <p className="subtle" style={{ margin: 0 }}>
        {t("patternDialog.summaryHint")}
      </p>
      <div className="btn-group" style={{ flexWrap: "wrap" }}>
        {SLOTS.map((slot) => (
          <Button
            key={`${slot.kind}${slot.plane}`}
            size="sm"
            icon={<Upload size={13} />}
            disabled={busy}
            onClick={() => request(slot.kind, slot.plane, null)}
          >
            {t("patternDialog.loadSummary", { slot: t(slotKey(slot.kind, slot.plane)) })}
          </Button>
        ))}
        <span style={{ flex: 1 }} />
        <Button
          size="sm"
          variant="ghost"
          className="danger"
          icon={<Trash2 size={13} />}
          disabled={bindings.length === 0}
          onClick={() => updateProject({ channel_patterns: [] })}
        >
          {t("patternDialog.clearAll")}
        </Button>
      </div>
      {error && <Callout tone="danger">{error}</Callout>}
      <div className="table-wrap" style={{ maxHeight: 340 }}>
        <table className="table">
          <thead>
            <tr>
              <th>{t("patternDialog.channel")}</th>
              {SLOTS.map((slot) => (
                <th key={`${slot.kind}${slot.plane}`}>{t(slotKey(slot.kind, slot.plane))}</th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            <tr className="group-row">
              <td colSpan={6}>{t("patternDialog.groupPhysical")}</td>
            </tr>
            {physical.map(renderRow)}
            <tr className="group-row" style={{ cursor: "pointer" }} onClick={() => setShowVirtual((value) => !value)}>
              <td colSpan={6}>
                {showVirtual ? "▾" : "▸"} {t("patternDialog.groupVirtual")} ({virtual.length})
              </td>
            </tr>
            {showVirtual && virtual.map(renderRow)}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ElementPatternSection() {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const { updateProject, setStatus } = useStore.getState();
  const settings = project.element_pattern;
  const [preview, setPreview] = useState<ElementPatternPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!settings) {
      setPreview(null);
      return;
    }
    let cancelled = false;
    api.elementPatternPreview(settings.asset, settings.swap_axes).then(
      (result) => !cancelled && (setPreview(result), setError(null)),
      (reason) => !cancelled && setError(errorMessage(reason)),
    );
    return () => {
      cancelled = true;
    };
  }, [settings]);

  const pick = useFilePicker(PATTERN_ACCEPT, async (file) => {
    setBusy(true);
    setError(null);
    try {
      const info = await api.uploadAsset(file);
      rememberAssetName(info.id, info.filename);
      const result = await api.elementPatternPreview(info.id, false);
      updateProject({ element_pattern: { asset: info.id, swap_axes: false } });
      setPreview(result);
      setStatus("status.elementLoaded", "success", { name: result.name });
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  });

  const describe = (metrics: ElementPatternPreview["horizontal_metrics"] | null) =>
    metrics
      ? t("patternDialog.metrics", {
          peak: fmt(metrics.peak_gain_dbi, 2),
          angle: fmt(metrics.peak_angle_deg, 1),
          bw3: fmt(metrics.beamwidth_3db_deg, 1, "°"),
          bw6: fmt(metrics.beamwidth_6db_deg, 1, "°"),
        })
      : "";

  return (
    <div className="section">
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <h3 className="section-title" style={{ flex: 1 }}>
          {t("patternDialog.elementSection")}
        </h3>
        {busy && <Spinner />}
        {settings && (
          <Button
            size="sm"
            icon={<ArrowLeftRight size={13} />}
            disabled={!preview?.elevation_column && !settings.swap_axes}
            active={settings.swap_axes}
            onClick={() => updateProject({ element_pattern: { ...settings, swap_axes: !settings.swap_axes } })}
          >
            {t("patternDialog.swap")}
          </Button>
        )}
        <Button size="sm" icon={<Upload size={13} />} onClick={pick} disabled={busy}>
          {t("patternDialog.elementUpload")}
        </Button>
        {settings && (
          <Button
            size="sm"
            variant="ghost"
            icon={<X size={13} />}
            onClick={() => {
              updateProject({ element_pattern: null });
              setStatus("status.elementCleared");
            }}
          >
            {t("patternDialog.elementClear")}
          </Button>
        )}
      </div>
      <p className="subtle" style={{ margin: 0 }}>
        {t("patternDialog.elementHint")}
      </p>
      {error && <Callout tone="danger">{error}</Callout>}
      {!settings && <Callout>{t("patternDialog.isotropic")}</Callout>}
      {settings && preview && (
        <>
          <div className="subtle mono" style={{ fontSize: 12 }}>
            {preview.name} · θ: {preview.angle_column} · H: {preview.horizontal_column}
            {preview.elevation_column ? ` · V: ${preview.elevation_column}` : ""}
          </div>
          {!preview.elevation_column && <Callout tone="info">{t("patternDialog.reuse")}</Callout>}
          <div className="two-col">
            <PatternCut
              title={t("patternDialog.horizontal")}
              angles={preview.angles}
              gains={preview.horizontal_gain_db}
              caption={describe(preview.horizontal_metrics)}
            />
            <PatternCut
              title={t("patternDialog.elevationPlane")}
              angles={preview.angles}
              gains={preview.elevation_gain_db ?? preview.horizontal_gain_db}
              caption={describe(preview.elevation_metrics ?? preview.horizontal_metrics)}
            />
          </div>
        </>
      )}
    </div>
  );
}

function PatternCut({ title, angles, gains, caption }: { title: string; angles: number[]; gains: number[]; caption: string }) {
  const t = useT();
  const theme = useChartTheme();
  const data = useMemo(
    () => [
      {
        type: "scatter",
        mode: "lines",
        x: angles,
        y: gains,
        line: { color: theme.line, width: 2 },
        hovertemplate: "%{x:.0f}°  %{y:.2f} dB<extra></extra>",
      },
    ],
    [angles, gains, theme],
  );
  const layout = useMemo(
    () =>
      baseLayout(theme, {
        margin: { l: 50, r: 10, t: 8, b: 40 },
        xaxis: { title: { text: t("axis.angle") }, dtick: 60 },
        yaxis: { title: { text: t("axis.gain") } },
      }),
    [theme, t],
  );
  return (
    <div>
      <div style={{ fontWeight: 600, marginBottom: 2 }}>{title}</div>
      <div className="subtle" style={{ fontSize: 12, marginBottom: 6 }}>
        {caption}
      </div>
      <div className="chart-box" style={{ height: 220 }}>
        <div className="chart-body">
          <Plot data={data} layout={layout} />
        </div>
      </div>
    </div>
  );
}
