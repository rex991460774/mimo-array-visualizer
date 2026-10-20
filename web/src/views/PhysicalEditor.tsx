import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ElementKind, Layout, Point } from "../api/types";
import { type ElementRef, elementName, layoutBounds, snap } from "../lib/geometry";
import { trimNumber } from "../lib/format";
import { PLOT_MARGIN, PlaneGrid, useElementSize, usePlane } from "./plane";

interface DragState {
  ref: ElementRef;
  pointerId: number;
  offset: { dx: number; dy: number };
  position: Point;
  start: Point;
  moved: boolean;
}

interface PanState {
  pointerId: number;
  last: { x: number; y: number };
  moved: boolean;
}

const MARKER = 7.5;

function withPosition(layout: Layout, ref: ElementRef, position: Point): Layout {
  const points = layout[ref.kind].map((point, index) => (index === ref.index ? position : point));
  return { ...layout, [ref.kind]: points };
}

export function PhysicalEditor({
  layout,
  selection,
  deleteMode,
  mmPerLambda,
  fitSignal,
  onSelect,
  onCommit,
  onDelete,
  onPreview,
  onStatus,
}: {
  layout: Layout;
  selection: ElementRef | null;
  deleteMode: boolean;
  mmPerLambda: number;
  fitSignal: number;
  onSelect: (ref: ElementRef | null) => void;
  onCommit: (layout: Layout, selection: ElementRef | null) => void;
  onDelete: (ref: ElementRef) => void;
  onPreview: (layout: Layout | null) => void;
  onStatus?: (text: string) => void;
}) {
  const [container, size] = useElementSize<HTMLDivElement>();
  const svg = useRef<SVGSVGElement>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [pan, setPan] = useState<PanState | null>(null);
  const [hover, setHover] = useState<ElementRef | null>(null);

  const allPoints = useMemo(() => [...layout.tx, ...layout.rx], [layout]);
  const bounds = useMemo(() => layoutBounds(allPoints, 2), [allPoints]);
  const fitKey = useMemo(
    () => `${bounds.minX},${bounds.maxX},${bounds.minY},${bounds.maxY}`,
    [bounds],
  );
  const plane = usePlane(bounds, size.width, size.height, fitKey);
  const { toScreen, toWorld, zoomAt, panBy, fit } = plane;

  useEffect(() => {
    if (fitSignal > 0) fit();
  }, [fitSignal, fit]);

  const displayLayout = drag ? withPosition(layout, drag.ref, drag.position) : layout;

  const localPoint = useCallback((event: { clientX: number; clientY: number }) => {
    const rect = svg.current?.getBoundingClientRect();
    return { x: event.clientX - (rect?.left ?? 0), y: event.clientY - (rect?.top ?? 0) };
  }, []);

  // Wheel zoom needs a non-passive listener to prevent page scrolling.
  useEffect(() => {
    const element = svg.current;
    if (!element) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = element.getBoundingClientRect();
      zoomAt(event.clientX - rect.left, event.clientY - rect.top, Math.exp(-event.deltaY * 0.0015));
    };
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  const cancelDrag = useCallback(() => {
    if (!drag) return;
    setDrag(null);
    onPreview(null);
  }, [drag, onPreview]);

  useEffect(() => {
    if (!drag) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        cancelDrag();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [drag, cancelDrag]);

  const onElementPointerDown = (event: React.PointerEvent, ref: ElementRef) => {
    if (event.button !== 0) return;
    event.stopPropagation();
    if (deleteMode) {
      onDelete(ref);
      return;
    }
    const point = layout[ref.kind][ref.index];
    const local = localPoint(event);
    const world = toWorld(local.x, local.y);
    svg.current?.setPointerCapture(event.pointerId);
    onSelect(ref);
    setDrag({
      ref,
      pointerId: event.pointerId,
      offset: { dx: point.x - world.x, dy: point.y - world.y },
      position: point,
      start: point,
      moved: false,
    });
  };

  const onBackgroundPointerDown = (event: React.PointerEvent) => {
    if (event.button !== 0 && event.button !== 1) return;
    svg.current?.setPointerCapture(event.pointerId);
    const local = localPoint(event);
    setPan({ pointerId: event.pointerId, last: local, moved: false });
  };

  const onPointerMove = (event: React.PointerEvent) => {
    const local = localPoint(event);
    if (drag && event.pointerId === drag.pointerId) {
      const world = toWorld(local.x, local.y);
      const position = { x: world.x + drag.offset.dx, y: world.y + drag.offset.dy };
      const moved =
        drag.moved || Math.hypot(position.x - drag.start.x, position.y - drag.start.y) * plane.viewport.scale > 3;
      const next = { ...drag, position, moved };
      setDrag(next);
      if (moved) {
        const snapped = { x: snap(position.x), y: snap(position.y) };
        onPreview(withPosition(layout, drag.ref, snapped));
        onStatus?.(
          `${elementName(drag.ref.kind, drag.ref.index)}  x=${trimNumber(snapped.x)} λ  y=${trimNumber(snapped.y)} λ`,
        );
      }
      return;
    }
    if (pan && event.pointerId === pan.pointerId) {
      const dx = local.x - pan.last.x;
      const dy = local.y - pan.last.y;
      if (pan.moved || Math.hypot(dx, dy) > 2) {
        panBy(dx, dy);
        setPan({ ...pan, last: local, moved: true });
      }
    }
  };

  const onPointerUp = (event: React.PointerEvent) => {
    if (drag && event.pointerId === drag.pointerId) {
      if (drag.moved) {
        const snapped = { x: snap(drag.position.x), y: snap(drag.position.y) };
        onCommit(withPosition(layout, drag.ref, snapped), drag.ref);
      }
      setDrag(null);
      onPreview(null);
      return;
    }
    if (pan && event.pointerId === pan.pointerId) {
      if (!pan.moved) onSelect(null);
      setPan(null);
    }
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (!selection) return;
    const step = event.shiftKey ? 2.5 : 0.5;
    const delta: Record<string, [number, number]> = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, step],
      ArrowDown: [0, -step],
    };
    const move = delta[event.key];
    if (move) {
      event.preventDefault();
      const point = layout[selection.kind][selection.index];
      if (!point) return;
      onCommit(withPosition(layout, selection, { x: snap(point.x + move[0]), y: snap(point.y + move[1]) }), selection);
    }
  };

  const renderElement = (kind: ElementKind, point: Point, index: number) => {
    const ref = { kind, index };
    const { sx, sy } = toScreen(point.x, point.y);
    const isSelected = selection?.kind === kind && selection.index === index;
    const isHover = hover?.kind === kind && hover.index === index;
    const isDragging = drag?.ref.kind === kind && drag.ref.index === index;
    const color = kind === "tx" ? "var(--tx)" : "var(--rx)";
    const edge = kind === "tx" ? "var(--tx-edge)" : "var(--rx-edge)";
    const ring = deleteMode && isHover ? "var(--danger)" : "var(--accent)";
    const shape =
      kind === "tx" ? (
        <path
          d={`M${sx} ${sy - MARKER - 1.5} L${sx + MARKER + 0.5} ${sy + MARKER - 1.5} L${sx - MARKER - 0.5} ${sy + MARKER - 1.5} Z`}
          fill={color}
          stroke={edge}
          strokeWidth={1}
          strokeLinejoin="round"
        />
      ) : (
        <circle cx={sx} cy={sy} r={MARKER - 0.5} fill={color} stroke={edge} strokeWidth={1} />
      );
    return (
      <g
        key={`${kind}${index}`}
        className="element"
        style={{ cursor: deleteMode ? "pointer" : isDragging ? "grabbing" : "grab" }}
        onPointerDown={(event) => onElementPointerDown(event, ref)}
        onPointerEnter={() => setHover(ref)}
        onPointerLeave={() => setHover((current) => (current?.kind === kind && current.index === index ? null : current))}
      >
        <circle cx={sx} cy={sy} r={MARKER + 8} fill="transparent" />
        {(isSelected || isHover) && (
          <circle
            cx={sx}
            cy={sy}
            r={MARKER + 4.5}
            fill={isSelected ? "var(--accent-soft)" : "none"}
            stroke={ring}
            strokeWidth={isSelected ? 2 : 1.5}
            opacity={isSelected ? 1 : 0.8}
          />
        )}
        {shape}
        {deleteMode && isHover && (
          <path
            d={`M${sx - 4} ${sy - 4}L${sx + 4} ${sy + 4}M${sx + 4} ${sy - 4}L${sx - 4} ${sy + 4}`}
            stroke="#fff"
            strokeWidth={2}
            strokeLinecap="round"
          />
        )}
        <text x={sx + MARKER + 5} y={sy - MARKER} className="element-label">
          {elementName(kind, index)}
        </text>
      </g>
    );
  };

  const hovered = hover ? displayLayout[hover.kind][hover.index] : null;
  const hoverScreen = hovered ? toScreen(hovered.x, hovered.y) : null;
  const snapGhost = drag?.moved ? { x: snap(drag.position.x), y: snap(drag.position.y) } : null;
  const ghostScreen = snapGhost ? toScreen(snapGhost.x, snapGhost.y) : null;

  return (
    <div
      ref={container}
      className={`plane ${deleteMode ? "delete-mode" : ""}`}
      tabIndex={0}
      onKeyDown={onKeyDown}
      aria-label="Physical array editor"
    >
      {size.width > 0 && (
        <svg
          ref={svg}
          width={size.width}
          height={size.height}
          onPointerDown={onBackgroundPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={() => {
            cancelDrag();
            setPan(null);
          }}
          style={{ cursor: pan?.moved ? "grabbing" : "default", touchAction: "none" }}
        >
          <defs>
            <clipPath id="physical-clip">
              <rect
                x={PLOT_MARGIN.left}
                y={PLOT_MARGIN.top}
                width={Math.max(0, size.width - PLOT_MARGIN.left - PLOT_MARGIN.right)}
                height={Math.max(0, size.height - PLOT_MARGIN.top - PLOT_MARGIN.bottom)}
              />
            </clipPath>
          </defs>
          <PlaneGrid width={size.width} height={size.height} {...plane} />
          <g clipPath="url(#physical-clip)">
            {ghostScreen && (
              <circle
                cx={ghostScreen.sx}
                cy={ghostScreen.sy}
                r={MARKER + 3}
                fill="none"
                stroke="var(--text-tertiary)"
                strokeDasharray="3 3"
              />
            )}
            {displayLayout.rx.map((point, index) => renderElement("rx", point, index))}
            {displayLayout.tx.map((point, index) => renderElement("tx", point, index))}
          </g>
        </svg>
      )}
      {hover && hovered && hoverScreen && !drag && (
        <div className="plane-tooltip" style={{ left: hoverScreen.sx + 14, top: hoverScreen.sy + 12 }}>
          <strong>{elementName(hover.kind, hover.index)}</strong>
          <span className="mono">
            ({trimNumber(hovered.x)}, {trimNumber(hovered.y)}) λ
          </span>
          <span className="mono subtle">
            ({trimNumber(hovered.x * mmPerLambda, 2)}, {trimNumber(hovered.y * mmPerLambda, 2)}) mm
          </span>
        </div>
      )}
    </div>
  );
}
