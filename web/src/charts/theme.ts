import { useEffect, useState } from "react";

export interface ChartTheme {
  text: string;
  textSecondary: string;
  grid: string;
  zero: string;
  surface: string;
  line: string;
  secondary: string;
  trueAngle: string;
  peak: string;
  band: string;
  tx: string;
  rx: string;
  accent: string;
  danger: string;
  warning: string;
  success: string;
  dark: boolean;
  font: string;
}

function readTheme(): ChartTheme {
  const style = getComputedStyle(document.documentElement);
  const value = (name: string) => style.getPropertyValue(name).trim();
  return {
    text: value("--text"),
    textSecondary: value("--text-secondary"),
    grid: value("--chart-grid"),
    zero: value("--chart-zero"),
    surface: value("--surface"),
    line: value("--chart-line"),
    secondary: value("--chart-secondary"),
    trueAngle: value("--chart-true"),
    peak: value("--chart-peak"),
    band: value("--chart-band"),
    tx: value("--tx"),
    rx: value("--rx"),
    accent: value("--accent"),
    danger: value("--danger"),
    warning: value("--warning"),
    success: value("--success"),
    dark: style.getPropertyValue("color-scheme").trim() === "dark",
    font: value("--font-sans"),
  };
}

/** Re-reads CSS tokens whenever the theme attribute or OS scheme changes. */
export function useChartTheme(): ChartTheme {
  const [theme, setTheme] = useState<ChartTheme>(() => readTheme());
  useEffect(() => {
    const refresh = () => setTheme(readTheme());
    const observer = new MutationObserver(refresh);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", refresh);
    return () => {
      observer.disconnect();
      media.removeEventListener("change", refresh);
    };
  }, []);
  return theme;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function baseLayout(theme: ChartTheme, overrides: Record<string, any> = {}): Record<string, any> {
  const axis = {
    gridcolor: theme.grid,
    zerolinecolor: theme.zero,
    linecolor: theme.zero,
    tickcolor: theme.zero,
    ticks: "outside",
    ticklen: 4,
    showline: true,
    mirror: false,
    tickfont: { size: 11, color: theme.textSecondary },
    title: { font: { size: 12, color: theme.textSecondary }, standoff: 6 },
    automargin: true,
  };
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: theme.font, size: 12, color: theme.text },
    margin: { l: 56, r: 16, t: 12, b: 44 },
    showlegend: false,
    hovermode: "x",
    hoverlabel: {
      bgcolor: theme.surface,
      bordercolor: theme.zero,
      font: { family: theme.font, size: 12, color: theme.text },
    },
    dragmode: false,
    ...overrides,
    xaxis: { ...axis, ...(overrides.xaxis ?? {}) },
    yaxis: { ...axis, ...(overrides.yaxis ?? {}) },
  };
}
