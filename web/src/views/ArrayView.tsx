import {
  Eraser,
  Maximize2,
  Plus,
  Redo2,
  RotateCcw,
  Table2,
  Trash2,
  Undo2,
  Wand2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { ElementKind, Layout, Point } from "../api/types";
import { Button, Menu, NumberInput } from "../components/ui";
import { useT } from "../i18n";
import { elementName, nextElementPosition, snap, virtualGroups } from "../lib/geometry";
import { parseNumber, trimNumber } from "../lib/format";
import { type CoordUnit, useStore } from "../state/store";
import { Segmented } from "../components/ui";
import { PhysicalEditor } from "./PhysicalEditor";
import { VirtualPlot } from "./VirtualPlot";

const STARTER_LAYOUT: Layout = { tx: [{ x: 0, y: 2 }], rx: [{ x: 0, y: -2 }] };

/** Coordinate entry in λ or mm; typed values are kept exactly (no grid snap). */
function CoordInput({
  value,
  unit,
  mmPerLambda,
  onCommit,
  className,
}: {
  value: number;
  unit: CoordUnit;
  mmPerLambda: number;
  onCommit: (lambda: number) => void;
  className?: string;
}) {
  const t = useT();
  // The server validates too; without a published limit, leave the check to it.
  const limit = useStore((state) => state.config!.limits.coordinate_lambda) ?? Number.POSITIVE_INFINITY;
  const scale = unit === "mm" ? mmPerLambda : 1;
  const suffixes = unit === "mm" ? ["mm"] : ["λ"];
  return (
    <NumberInput
      className={className}
      value={value * scale}
      parse={(text) => {
        const parsed = parseNumber(text, suffixes);
        return parsed !== null && Math.abs(parsed / scale) <= limit ? parsed : null;
      }}
      format={(v) => trimNumber(v, unit === "mm" ? 3 : 4)}
      invalidTitle={(text) => (parseNumber(text, suffixes) === null ? t("input.notNumber") : t("physical.outOfRange", { limit }))}
      onCommit={(v) => onCommit(snap(v / scale, 0))}
    />
  );
}

export function ArrayView() {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const config = useStore((state) => state.config)!;
  const selection = useStore((state) => state.selection);
  const deleteMode = useStore((state) => state.deleteMode);
  const past = useStore((state) => state.past.length);
  const future = useStore((state) => state.future.length);
  const evaluation = useStore((state) => state.evaluation);
  const unit = useStore((state) => state.coordUnit);
  const { commitLayout, select, setDeleteMode, undo, redo, setStatus, setCoordUnit } = useStore.getState();

  const [preview, setPreview] = useState<Layout | null>(null);
  const [fitSignal, setFitSignal] = useState(0);
  const [showTable, setShowTable] = useState(false);
  const [autoTx, setAutoTx] = useState(project.layout.tx.length);
  const [autoRx, setAutoRx] = useState(project.layout.rx.length);

  const layout = project.layout;
  const shown = preview ?? layout;
  const groups = useMemo(() => virtualGroups(shown), [shown]);
  const duplicate = groups.reduce((sum, group) => sum + group.count - 1, 0);
  const mmPerLambda = 299.792458 / project.frequency_ghz;
  const limits = { tx: config.limits.max_tx, rx: config.limits.max_rx };

  const addElement = (kind: ElementKind) => {
    if (layout[kind].length >= limits[kind]) {
      setStatus("physical.limit", "error", { kind: kind === "tx" ? "Tx" : "Rx", max: limits[kind] });
      return;
    }
    const position = nextElementPosition(layout, kind, selection);
    const next = { ...layout, [kind]: [...layout[kind], position] };
    commitLayout(next, { kind, index: next[kind].length - 1 });
    const follow = useStore.getState().selection;
    setStatus("status.added", "success", { name: follow ? elementName(follow.kind, follow.index) : "" });
  };

  const deleteElement = (ref: { kind: ElementKind; index: number }) => {
    if (layout[ref.kind].length <= 1) {
      setStatus("physical.lastElement", "error", { kind: ref.kind === "tx" ? "Tx" : "Rx" });
      return;
    }
    const name = elementName(ref.kind, ref.index);
    const next = { ...layout, [ref.kind]: layout[ref.kind].filter((_, index) => index !== ref.index) };
    commitLayout(next, null);
    setStatus("status.deleted", "success", { name });
  };

  const applyAuto = async () => {
    try {
      const next = await api.autoLayout(autoTx, autoRx);
      commitLayout(next, null);
      setFitSignal((value) => value + 1);
      setStatus("status.autoLayout", "success", { tx: autoTx, rx: autoRx });
    } catch (error) {
      setStatus("overview.error", "error", undefined, errorMessage(error));
    }
  };

  const commitMove = (next: Layout, ref: { kind: ElementKind; index: number } | null) => {
    commitLayout(next, ref);
    const follow = useStore.getState().selection;
    if (follow) {
      const point = useStore.getState().project!.layout[follow.kind][follow.index];
      setStatus("status.moved", "info", {
        name: elementName(follow.kind, follow.index),
        x: trimNumber(point.x),
        y: trimNumber(point.y),
      });
    }
  };

  const updatePoint = (kind: ElementKind, index: number, point: Point) => {
    const next = { ...layout, [kind]: layout[kind].map((p, i) => (i === index ? point : p)) };
    commitMove(next, { kind, index });
  };

  const selected = selection ? layout[selection.kind][selection.index] : null;
  const highlight = selection
    ? { side: (selection.kind === "tx" ? 0 : 1) as 0 | 1, name: elementName(selection.kind, selection.index) }
    : null;
  const unique = evaluation && !preview ? evaluation.summary.unique_count : groups.length;
  const total = shown.tx.length * shown.rx.length;

  const relatedPairs = highlight
    ? groups.reduce((sum, group) => sum + group.pairs.filter((pair) => pair.split("-")[highlight.side] === highlight.name).length, 0)
    : 0;
  const ySpan = (points: Point[]) => (points.length ? Math.max(...points.map((p) => p.y)) - Math.min(...points.map((p) => p.y)) : 0);
  const xSpan = (points: Point[]) => (points.length ? Math.max(...points.map((p) => p.x)) - Math.min(...points.map((p) => p.x)) : 0);
  const gridLabel = project.grid_step_lambda > 0 ? `λ/${Math.round(1 / project.grid_step_lambda)}` : t("settings.gridFree");

  return (
    <div className="array-view">
      <div className="grid-2 array-panels">
        <section className="panel">
          <header className="panel-header">
            <div className="panel-heading">
              <span className="panel-title">{t("physical.title")}</span>
              <span className="panel-subtitle">
                {deleteMode ? t("physical.deleteHint") : t("physical.subtitle", { grid: gridLabel })}
              </span>
            </div>
            <div className="panel-tools">
              <span className="badge tx">Tx {layout.tx.length}</span>
              <span className="badge rx">Rx {layout.rx.length}</span>
            </div>
          </header>
          <div className="panel-toolbar">
            <Button size="sm" icon={<Plus size={14} />} onClick={() => addElement("tx")} title={t("physical.addTxTitle")}>
              <span className="legend-swatch tx" />
              {t("physical.addTx")}
            </Button>
            <Button size="sm" icon={<Plus size={14} />} onClick={() => addElement("rx")} title={t("physical.addRxTitle")}>
              <span className="legend-swatch rx" />
              {t("physical.addRx")}
            </Button>
            <AutoLayoutButton
              tx={autoTx}
              rx={autoRx}
              limits={limits}
              onChange={(tx, rx) => {
                setAutoTx(tx);
                setAutoRx(rx);
              }}
              onApply={applyAuto}
            />
            <span className="toolbar-sep" />
            <Button
              size="sm"
              variant="ghost"
              icon={<Eraser size={15} />}
              active={deleteMode}
              onClick={() => setDeleteMode(!deleteMode)}
              title={t("physical.deleteMode")}
              aria-label={t("physical.deleteMode")}
            />
            <Button
              size="sm"
              variant="ghost"
              icon={<Trash2 size={15} />}
              disabled={!selection}
              onClick={() => selection && deleteElement(selection)}
              title={t("physical.deleteSelected")}
              aria-label={t("physical.deleteSelected")}
            />
            <Button
              size="sm"
              variant="ghost"
              icon={<RotateCcw size={15} />}
              onClick={() => {
                commitLayout(STARTER_LAYOUT, null);
                setFitSignal((value) => value + 1);
                setStatus("status.cleared");
              }}
              title={t("physical.clear")}
              aria-label={t("physical.clear")}
            />
            <span className="toolbar-sep" />
            <Button size="sm" variant="ghost" icon={<Undo2 size={15} />} disabled={!past} onClick={undo} title={`${t("physical.undo")} (Ctrl+Z)`} aria-label={t("physical.undo")} />
            <Button size="sm" variant="ghost" icon={<Redo2 size={15} />} disabled={!future} onClick={redo} title={`${t("physical.redo")} (Ctrl+Y)`} aria-label={t("physical.redo")} />
            <span className="toolbar-spacer" />
            <Button size="sm" variant="ghost" icon={<Maximize2 size={15} />} onClick={() => setFitSignal((value) => value + 1)} title={t("physical.fit")} aria-label={t("physical.fit")} />
            <Button size="sm" variant="ghost" icon={<Table2 size={15} />} active={showTable} onClick={() => setShowTable((value) => !value)} title={t("physical.table")} aria-label={t("physical.table")} />
          </div>
          <div className="panel-body">
            <PhysicalEditor
              layout={layout}
              selection={selection}
              deleteMode={deleteMode}
              mmPerLambda={mmPerLambda}
              gridStep={project.grid_step_lambda}
              fitSignal={fitSignal}
              onSelect={select}
              onCommit={commitMove}
              onDelete={deleteElement}
              onPreview={setPreview}
            />
          </div>
          <footer className="panel-footer">
            <div className="inspector">
              {selected && selection ? (
                <>
                  <span className={`badge ${selection.kind}`}>{elementName(selection.kind, selection.index)}</span>
                  <label className="field">
                    <span className="field-label">{t("inspector.x")}</span>
                    <CoordInput
                      className=""
                      value={selected.x}
                      unit={unit}
                      mmPerLambda={mmPerLambda}
                      onCommit={(x) => updatePoint(selection.kind, selection.index, { x, y: selected.y })}
                    />
                    <span className="field-unit">{unit === "mm" ? "mm" : "λ"}</span>
                  </label>
                  <label className="field">
                    <span className="field-label">{t("inspector.y")}</span>
                    <CoordInput
                      className=""
                      value={selected.y}
                      unit={unit}
                      mmPerLambda={mmPerLambda}
                      onCommit={(y) => updatePoint(selection.kind, selection.index, { x: selected.x, y })}
                    />
                    <span className="field-unit">{unit === "mm" ? "mm" : "λ"}</span>
                  </label>
                  <span className="subtle mono inspector-alt">
                    {unit === "mm"
                      ? `(${trimNumber(selected.x)}, ${trimNumber(selected.y)}) λ`
                      : `(${trimNumber(selected.x * mmPerLambda, 2)}, ${trimNumber(selected.y * mmPerLambda, 2)}) mm`}
                  </span>
                </>
              ) : (
                <span className="subtle">{t("inspector.none")}</span>
              )}
            </div>
            <Segmented
              label={t("inspector.unit")}
              value={unit}
              options={[
                { value: "lambda", label: "λ" },
                { value: "mm", label: "mm" },
              ]}
              onChange={setCoordUnit}
            />
          </footer>
        </section>

        <section className="panel">
          <header className="panel-header">
            <div className="panel-heading">
              <span className="panel-title">{t("virtual.title")}</span>
              <span className="panel-subtitle">{t("virtual.subtitle")}</span>
            </div>
            <div className="panel-tools">
              <span className="badge num">{t("virtual.info", { unique, total, duplicate })}</span>
            </div>
          </header>
          <div className="panel-toolbar">
            <span className="toolbar-legend">
              <span className="legend-dot unique" />
              {t("virtual.unique")}
            </span>
            <span className="toolbar-legend">
              <span className="legend-dot duplicate" />
              {t("virtual.duplicate")}
            </span>
            <span className="toolbar-spacer" />
            <Button size="sm" variant="ghost" icon={<Maximize2 size={15} />} onClick={() => setFitSignal((value) => value + 1)} title={t("physical.fit")} aria-label={t("physical.fit")} />
          </div>
          <div className="panel-body">
            <VirtualPlot groups={groups} fitSignal={fitSignal} highlight={highlight} />
          </div>
          <footer className="panel-footer">
            {highlight ? (
              <span>
                <span className={`badge ${selection!.kind}`}>{highlight.name}</span>{" "}
                <span className="muted">{t("virtual.related", { count: relatedPairs })}</span>
              </span>
            ) : (
              <span className="muted num">
                {t("virtual.extent", {
                  x: trimNumber(xSpan(groups), 2),
                  y: trimNumber(ySpan(groups), 2),
                })}
              </span>
            )}
          </footer>
        </section>
      </div>

      {showTable && <CoordinateTable layout={layout} mmPerLambda={mmPerLambda} onChange={updatePoint} onClose={() => setShowTable(false)} />}
    </div>
  );
}

function AutoLayoutButton({
  tx,
  rx,
  limits,
  onChange,
  onApply,
}: {
  tx: number;
  rx: number;
  limits: { tx: number; rx: number };
  onChange: (tx: number, rx: number) => void;
  onApply: () => void;
}) {
  const t = useT();
  const integer = (max: number) => (text: string) => {
    const value = parseNumber(text);
    return value !== null && Number.isInteger(value) && value >= 1 && value <= max ? value : null;
  };
  return (
    <Menu
      align="left"
      trigger={({ toggle }) => (
        <Button size="sm" icon={<Wand2 size={14} />} onClick={toggle} title={t("physical.autoTitle")}>
          {t("physical.auto")}
        </Button>
      )}
    >
      {(close) => (
        <div className="popover-form">
          <div className="popover-title">{t("physical.autoTitle")}</div>
          <div className="popover-row">
            <label className="field compact">
              <span className="field-label">Tx</span>
              <NumberInput className="" value={tx} parse={integer(limits.tx)} onCommit={(value) => onChange(value, rx)} />
            </label>
            <span className="subtle">×</span>
            <label className="field compact">
              <span className="field-label">Rx</span>
              <NumberInput className="" value={rx} parse={integer(limits.rx)} onCommit={(value) => onChange(tx, value)} />
            </label>
            <Button
              size="sm"
              variant="primary"
              onClick={() => {
                onApply();
                close();
              }}
            >
              {t("physical.autoApply")}
            </Button>
          </div>
          <p className="subtle popover-hint">{t("physical.autoHint", { n: tx * rx })}</p>
        </div>
      )}
    </Menu>
  );
}

function CoordinateTable({
  layout,
  mmPerLambda,
  onChange,
  onClose,
}: {
  layout: Layout;
  mmPerLambda: number;
  onChange: (kind: ElementKind, index: number, point: Point) => void;
  onClose: () => void;
}) {
  const t = useT();
  const selection = useStore((state) => state.selection);
  const select = useStore((state) => state.select);
  const rows: { kind: ElementKind; index: number; point: Point }[] = [
    ...layout.tx.map((point, index) => ({ kind: "tx" as const, index, point })),
    ...layout.rx.map((point, index) => ({ kind: "rx" as const, index, point })),
  ];
  return (
    <section className="panel coordinate-panel">
      <header className="panel-header">
        <span className="panel-title">{t("physical.table")}</span>
        <div className="panel-tools">
          <Button size="sm" variant="ghost" onClick={onClose}>
            {t("table.close")}
          </Button>
        </div>
      </header>
      <div className="table-wrap" style={{ border: 0, borderRadius: 0, maxHeight: 320 }}>
        <table className="table">
          <thead>
            <tr>
              <th>{t("table.channel")}</th>
              <th className="num">{t("table.x")}</th>
              <th className="num">{t("table.y")}</th>
              <th className="num">{t("table.xmm")}</th>
              <th className="num">{t("table.ymm")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ kind, index, point }) => (
              <tr
                key={`${kind}${index}`}
                className={selection?.kind === kind && selection.index === index ? "selected" : ""}
                onClick={() => select({ kind, index })}
              >
                <td>
                  <span className={`badge ${kind}`}>{elementName(kind, index)}</span>
                </td>
                <td className="num">
                  <CoordInput value={point.x} unit="lambda" mmPerLambda={mmPerLambda} className="input num" onCommit={(x) => onChange(kind, index, { x, y: point.y })} />
                </td>
                <td className="num">
                  <CoordInput value={point.y} unit="lambda" mmPerLambda={mmPerLambda} className="input num" onCommit={(y) => onChange(kind, index, { x: point.x, y })} />
                </td>
                <td className="num">
                  <CoordInput value={point.x} unit="mm" mmPerLambda={mmPerLambda} className="input num" onCommit={(x) => onChange(kind, index, { x, y: point.y })} />
                </td>
                <td className="num">
                  <CoordInput value={point.y} unit="mm" mmPerLambda={mmPerLambda} className="input num" onCommit={(y) => onChange(kind, index, { x: point.x, y })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
