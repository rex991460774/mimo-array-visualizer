import { useEffect, useRef } from "react";

// Plotly is large; load it on first use so the array editor opens instantly.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let plotlyPromise: Promise<any> | null = null;
function loadPlotly() {
  plotlyPromise ??= import("plotly.js-cartesian-dist-min").then((module) => module.default ?? module);
  return plotlyPromise;
}

export interface PlotPoint {
  x: number;
  y: number;
  z?: number;
  curveNumber: number;
  pointIndex: number;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export function Plot({
  data,
  layout,
  config,
  onClick,
  className,
  style,
  ariaLabel,
}: {
  data: any[];
  layout: Record<string, any>;
  config?: Record<string, any>;
  onClick?: (point: PlotPoint) => void;
  className?: string;
  style?: React.CSSProperties;
  ariaLabel?: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const clickHandler = useRef(onClick);
  clickHandler.current = onClick;
  const ready = useRef(false);

  useEffect(() => {
    let cancelled = false;
    const element = container.current;
    if (!element) return;
    loadPlotly().then((Plotly) => {
      if (cancelled || !element) return;
      Plotly.react(element, data, layout, {
        displaylogo: false,
        responsive: false,
        displayModeBar: false,
        doubleClick: "reset",
        ...config,
      });
      if (!ready.current) {
        ready.current = true;
        (element as any).on?.("plotly_click", (event: any) => {
          const point = event?.points?.[0];
          if (point && clickHandler.current) {
            clickHandler.current({
              x: Number(point.x),
              y: Number(point.y),
              z: point.z === undefined ? undefined : Number(point.z),
              curveNumber: point.curveNumber,
              pointIndex: Array.isArray(point.pointIndex) ? point.pointIndex[0] : point.pointIndex,
            });
          }
        });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [data, layout, config]);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        loadPlotly().then((Plotly) => {
          if (ready.current && element.isConnected) Plotly.Plots.resize(element);
        });
      });
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      loadPlotly().then((Plotly) => Plotly.purge(element));
      ready.current = false;
    };
  }, []);

  return (
    <div
      ref={container}
      className={className}
      style={{ width: "100%", height: "100%", ...style }}
      role="img"
      aria-label={ariaLabel}
    />
  );
}
/* eslint-enable @typescript-eslint/no-explicit-any */
