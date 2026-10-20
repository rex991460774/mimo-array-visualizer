import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

/** Shared viewport for the λ-plane plots (physical and virtual arrays). */

export interface Bounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

export interface Viewport {
  /** λ coordinate at the viewport center. */
  cx: number;
  cy: number;
  /** Pixels per λ. */
  scale: number;
}

export const PLOT_MARGIN = { left: 48, right: 14, top: 14, bottom: 32 };

export function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize((previous) =>
        Math.abs(previous.width - width) < 0.5 && Math.abs(previous.height - height) < 0.5
          ? previous
          : { width, height },
      );
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, size] as const;
}

export function fitViewport(bounds: Bounds, width: number, height: number): Viewport {
  const innerWidth = Math.max(10, width - PLOT_MARGIN.left - PLOT_MARGIN.right);
  const innerHeight = Math.max(10, height - PLOT_MARGIN.top - PLOT_MARGIN.bottom);
  const spanX = Math.max(2, bounds.maxX - bounds.minX);
  const spanY = Math.max(2, bounds.maxY - bounds.minY);
  const scale = Math.min(innerWidth / spanX, innerHeight / spanY);
  return {
    cx: (bounds.minX + bounds.maxX) / 2,
    cy: (bounds.minY + bounds.maxY) / 2,
    scale: Math.max(2, Math.min(scale, 120)),
  };
}

export function usePlane(bounds: Bounds, width: number, height: number, autoFitKey: string) {
  const [viewport, setViewport] = useState<Viewport>({ cx: 0, cy: 0, scale: 10 });
  const manual = useRef(false);
  const boundsRef = useRef(bounds);
  boundsRef.current = bounds;

  const fit = useCallback(() => {
    manual.current = false;
    if (width > 0 && height > 0) setViewport(fitViewport(boundsRef.current, width, height));
  }, [width, height]);

  // Auto-fit on size or layout change unless the user zoomed/panned.
  useEffect(() => {
    if (!manual.current && width > 0 && height > 0) {
      setViewport(fitViewport(boundsRef.current, width, height));
    }
  }, [width, height, autoFitKey]);

  const centerX = PLOT_MARGIN.left + (width - PLOT_MARGIN.left - PLOT_MARGIN.right) / 2;
  const centerY = PLOT_MARGIN.top + (height - PLOT_MARGIN.top - PLOT_MARGIN.bottom) / 2;

  const toScreen = useCallback(
    (x: number, y: number) => ({
      sx: centerX + (x - viewport.cx) * viewport.scale,
      sy: centerY - (y - viewport.cy) * viewport.scale,
    }),
    [centerX, centerY, viewport],
  );

  const toWorld = useCallback(
    (sx: number, sy: number) => ({
      x: viewport.cx + (sx - centerX) / viewport.scale,
      y: viewport.cy - (sy - centerY) / viewport.scale,
    }),
    [centerX, centerY, viewport],
  );

  const zoomAt = useCallback(
    (sx: number, sy: number, factor: number) => {
      manual.current = true;
      setViewport((current) => {
        const scale = Math.max(2, Math.min(current.scale * factor, 200));
        const worldX = current.cx + (sx - centerX) / current.scale;
        const worldY = current.cy - (sy - centerY) / current.scale;
        return {
          scale,
          cx: worldX - (sx - centerX) / scale,
          cy: worldY + (sy - centerY) / scale,
        };
      });
    },
    [centerX, centerY],
  );

  const panBy = useCallback((dx: number, dy: number) => {
    manual.current = true;
    setViewport((current) => ({
      ...current,
      cx: current.cx - dx / current.scale,
      cy: current.cy + dy / current.scale,
    }));
  }, []);

  return { viewport, toScreen, toWorld, zoomAt, panBy, fit };
}

function niceStep(pixelsPerUnit: number, minPixels: number): number {
  const candidates = [0.5, 1, 2, 5, 10, 20, 50, 100];
  return candidates.find((step) => step * pixelsPerUnit >= minPixels) ?? 100;
}

export function PlaneGrid({
  width,
  height,
  viewport,
  toScreen,
  toWorld,
  showMinor = true,
}: {
  width: number;
  height: number;
  viewport: Viewport;
  toScreen: (x: number, y: number) => { sx: number; sy: number };
  toWorld: (sx: number, sy: number) => { x: number; y: number };
  showMinor?: boolean;
}) {
  const lines = useMemo(() => {
    const left = PLOT_MARGIN.left;
    const right = width - PLOT_MARGIN.right;
    const top = PLOT_MARGIN.top;
    const bottom = height - PLOT_MARGIN.bottom;
    const topLeft = toWorld(left, top);
    const bottomRight = toWorld(right, bottom);
    const major = niceStep(viewport.scale, 46);
    const minor = 0.5;
    const result: { minor: string[]; major: string[]; xLabels: [number, number][]; yLabels: [number, number][] } = {
      minor: [],
      major: [],
      xLabels: [],
      yLabels: [],
    };
    const drawMinor = showMinor && minor * viewport.scale >= 7;
    const step = drawMinor ? minor : major;
    const startX = Math.ceil(topLeft.x / step) * step;
    for (let x = startX; x <= bottomRight.x + 1e-9; x += step) {
      const { sx } = toScreen(x, 0);
      const isMajor = Math.abs(x / major - Math.round(x / major)) < 1e-6;
      (isMajor ? result.major : result.minor).push(`M${sx.toFixed(1)} ${top}V${bottom}`);
      if (isMajor) result.xLabels.push([sx, x]);
    }
    const startY = Math.ceil(bottomRight.y / step) * step;
    for (let y = startY; y <= topLeft.y + 1e-9; y += step) {
      const { sy } = toScreen(0, y);
      const isMajor = Math.abs(y / major - Math.round(y / major)) < 1e-6;
      (isMajor ? result.major : result.minor).push(`M${left} ${sy.toFixed(1)}H${right}`);
      if (isMajor) result.yLabels.push([sy, y]);
    }
    return { ...result, left, right, top, bottom };
  }, [width, height, viewport, toScreen, toWorld, showMinor]);

  const format = (value: number) => (Math.abs(value) < 1e-9 ? "0" : String(Math.round(value * 100) / 100));

  return (
    <g className="plane-grid" pointerEvents="none">
      <rect
        x={lines.left}
        y={lines.top}
        width={Math.max(0, lines.right - lines.left)}
        height={Math.max(0, lines.bottom - lines.top)}
        fill="var(--surface)"
      />
      <path d={lines.minor.join("")} stroke="var(--chart-grid)" strokeWidth={1} opacity={0.55} />
      <path d={lines.major.join("")} stroke="var(--chart-grid)" strokeWidth={1} />
      <rect
        x={lines.left}
        y={lines.top}
        width={Math.max(0, lines.right - lines.left)}
        height={Math.max(0, lines.bottom - lines.top)}
        fill="none"
        stroke="var(--border-strong)"
      />
      {lines.xLabels.map(([sx, value]) => (
        <text key={`x${value}`} x={sx} y={lines.bottom + 15} textAnchor="middle" className="plane-tick">
          {format(value)}
        </text>
      ))}
      {lines.yLabels.map(([sy, value]) => (
        <text key={`y${value}`} x={lines.left - 6} y={sy + 3.5} textAnchor="end" className="plane-tick">
          {format(value)}
        </text>
      ))}
      <text x={lines.right} y={lines.bottom + 26} textAnchor="end" className="plane-axis-label">
        x (λ)
      </text>
      <text
        x={10}
        y={(lines.top + lines.bottom) / 2}
        className="plane-axis-label"
        textAnchor="middle"
        transform={`rotate(-90 10 ${(lines.top + lines.bottom) / 2})`}
      >
        y (λ)
      </text>
    </g>
  );
}

export function clipId(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 8)}`;
}
