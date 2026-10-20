import { useEffect, useMemo, useRef, useState } from "react";
import { useT } from "../i18n";
import type { VirtualGroup } from "../lib/geometry";
import { layoutBounds } from "../lib/geometry";
import { trimNumber } from "../lib/format";
import { PLOT_MARGIN, PlaneGrid, useElementSize, usePlane } from "./plane";

export function VirtualPlot({
  groups,
  fitSignal,
  highlight,
}: {
  groups: VirtualGroup[];
  fitSignal: number;
  /** Highlight virtual points formed by the selected physical channel. */
  highlight: { side: 0 | 1; name: string } | null;
}) {
  const t = useT();
  const [container, size] = useElementSize<HTMLDivElement>();
  const svg = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<VirtualGroup | null>(null);
  const bounds = useMemo(() => layoutBounds(groups, 2), [groups]);
  const fitKey = `${bounds.minX},${bounds.maxX},${bounds.minY},${bounds.maxY}`;
  const plane = usePlane(bounds, size.width, size.height, fitKey);
  const { toScreen, zoomAt, fit } = plane;

  useEffect(() => {
    if (fitSignal > 0) fit();
  }, [fitSignal, fit]);

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
  }, [zoomAt, size.width]);

  const radius = Math.max(2.5, Math.min(6, plane.viewport.scale * 0.22));
  const hoverScreen = hover ? toScreen(hover.x, hover.y) : null;

  return (
    <div ref={container} className="plane">
      {size.width > 0 && (
        <svg ref={svg} width={size.width} height={size.height}>
          <defs>
            <clipPath id="virtual-clip">
              <rect
                x={PLOT_MARGIN.left}
                y={PLOT_MARGIN.top}
                width={Math.max(0, size.width - PLOT_MARGIN.left - PLOT_MARGIN.right)}
                height={Math.max(0, size.height - PLOT_MARGIN.top - PLOT_MARGIN.bottom)}
              />
            </clipPath>
          </defs>
          <PlaneGrid width={size.width} height={size.height} {...plane} />
          <g clipPath="url(#virtual-clip)">
            {groups.map((group) => {
              const { sx, sy } = toScreen(group.x, group.y);
              const duplicate = group.count > 1;
              const related = highlight
                ? group.pairs.some((pair) => pair.split("-")[highlight.side] === highlight.name)
                : false;
              const dimmed = highlight !== null && !related;
              return (
                <g
                  key={`${group.x},${group.y}`}
                  onPointerEnter={() => setHover(group)}
                  onPointerLeave={() => setHover((current) => (current === group ? null : current))}
                  opacity={dimmed ? 0.4 : 1}
                >
                  <circle cx={sx} cy={sy} r={radius + 5} fill="transparent" />
                  <circle
                    cx={sx}
                    cy={sy}
                    r={duplicate ? radius + 1.5 : radius}
                    fill={duplicate ? "var(--virtual-dup)" : "var(--virtual)"}
                    stroke={related ? "var(--text)" : duplicate ? "var(--warning)" : "none"}
                    strokeWidth={related ? 1.4 : 1}
                    fillOpacity={duplicate ? 0.95 : 0.85}
                  />
                  {duplicate && radius >= 4 && (
                    <text x={sx} y={sy + 3} textAnchor="middle" className="virtual-count">
                      {group.count}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>
      )}
      {hover && hoverScreen && (
        <div className="plane-tooltip" style={{ left: hoverScreen.sx + 12, top: hoverScreen.sy + 10 }}>
          <span className="mono">
            ({trimNumber(hover.x)}, {trimNumber(hover.y)}) λ
          </span>
          <span>{t("virtual.multiplicity", { count: hover.count })}</span>
          <span className="subtle mono" style={{ whiteSpace: "normal", maxWidth: 260 }}>
            {hover.pairs.slice(0, 8).join(", ")}
            {hover.pairs.length > 8 ? ` … (${hover.pairs.length})` : ""}
          </span>
        </div>
      )}
    </div>
  );
}
