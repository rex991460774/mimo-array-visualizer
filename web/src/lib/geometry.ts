import type { ElementKind, Layout, Point } from "../api/types";

export const GRID_STEP = 0.5;

export interface ElementRef {
  kind: ElementKind;
  index: number;
}

export function snap(value: number, step = GRID_STEP): number {
  const snapped = Math.round(value / step) * step;
  return Object.is(snapped, -0) ? 0 : snapped;
}

export function elementName(kind: ElementKind, index: number): string {
  return `${kind === "tx" ? "Tx" : "Rx"}${index + 1}`;
}

/**
 * Sort each kind by (x, y) so channel numbers follow position, as the desktop
 * tool did after every edit.  Returns the new index of `follow` if given.
 */
export function renumber(layout: Layout, follow?: ElementRef | null): { layout: Layout; follow: ElementRef | null } {
  let followed: ElementRef | null = null;
  const sortKind = (kind: ElementKind): Point[] => {
    const indexed = layout[kind].map((point, index) => ({ point, index }));
    indexed.sort((a, b) => a.point.x - b.point.x || a.point.y - b.point.y || a.index - b.index);
    if (follow && follow.kind === kind) {
      const newIndex = indexed.findIndex((item) => item.index === follow.index);
      if (newIndex >= 0) followed = { kind, index: newIndex };
    }
    return indexed.map((item) => item.point);
  };
  return { layout: { tx: sortKind("tx"), rx: sortKind("rx") }, follow: followed };
}

export interface VirtualGroup {
  x: number;
  y: number;
  count: number;
  pairs: string[];
}

/** Virtual positions are Tx + Rx (λ); computed locally for instant drag feedback. */
export function virtualGroups(layout: Layout): VirtualGroup[] {
  const groups = new Map<string, VirtualGroup>();
  layout.tx.forEach((tx, ti) => {
    layout.rx.forEach((rx, ri) => {
      const x = round9(tx.x + rx.x);
      const y = round9(tx.y + rx.y);
      const key = `${x},${y}`;
      const pair = `${elementName("tx", ti)}-${elementName("rx", ri)}`;
      const group = groups.get(key);
      if (group) {
        group.count += 1;
        group.pairs.push(pair);
      } else {
        groups.set(key, { x, y, count: 1, pairs: [pair] });
      }
    });
  });
  return [...groups.values()];
}

function round9(value: number): number {
  return Math.round(value * 1e9) / 1e9;
}

export function nextElementPosition(layout: Layout, kind: ElementKind, selected: ElementRef | null): Point {
  const same = layout[kind];
  if (same.length === 0) return { x: 0, y: kind === "tx" ? 0 : -5 };
  const anchor =
    selected && selected.kind === kind && same[selected.index]
      ? same[selected.index]
      : same.reduce((best, point) => (point.x > best.x || (point.x === best.x && point.y > best.y) ? point : best));
  const occupied = new Set([...layout.tx, ...layout.rx].map((point) => `${point.x},${point.y}`));
  let x = snap(anchor.x + 1);
  const y = snap(anchor.y);
  while (occupied.has(`${x},${y}`)) x = snap(x + 1);
  return { x, y };
}

export function layoutBounds(points: Point[], pad = 1): { minX: number; maxX: number; minY: number; maxY: number } {
  if (points.length === 0) return { minX: -5, maxX: 5, minY: -5, maxY: 5 };
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const point of points) {
    minX = Math.min(minX, point.x);
    maxX = Math.max(maxX, point.x);
    minY = Math.min(minY, point.y);
    maxY = Math.max(maxY, point.y);
  }
  return { minX: minX - pad, maxX: maxX + pad, minY: minY - pad, maxY: maxY + pad };
}

export function layoutsEqual(a: Layout, b: Layout): boolean {
  const same = (p: Point[], q: Point[]) => p.length === q.length && p.every((point, i) => point.x === q[i].x && point.y === q[i].y);
  return same(a.tx, b.tx) && same(a.rx, b.rx);
}
