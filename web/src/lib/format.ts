export function fmt(value: number | null | undefined, digits = 1, suffix = ""): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value.toFixed(digits)}${suffix}`;
}

export function fmtSigned(value: number | null | undefined, digits = 0, suffix = "°"): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (Math.abs(value) < 0.5 * 10 ** -digits) return `0${suffix}`;
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}${suffix}`;
}

export function fmtLambda(value: number): string {
  return `${trimNumber(value)} λ`;
}

export function trimNumber(value: number, digits = 3): string {
  if (!Number.isFinite(value)) return "—";
  const text = value.toFixed(digits);
  return text.includes(".") ? text.replace(/0+$/, "").replace(/\.$/, "") : text;
}

const DECIMAL = /^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/;

/**
 * Parse a user-typed number: plain decimal or scientific notation, with an
 * optional unit suffix. Anything that could be misread is rejected rather than
 * guessed: hex/binary literals, several separators, and "1,000"-style input
 * where the comma may be a thousands separator. An unambiguous decimal comma
 * ("1,5", "0,125") is accepted.
 */
export function parseNumber(text: string, suffixes: string[] = []): number | null {
  let value = text.trim().toLowerCase().replace(/\u2212/g, "-");
  for (const suffix of suffixes) {
    if (value.endsWith(suffix)) {
      value = value.slice(0, -suffix.length).trim();
      break;
    }
  }
  if (value.includes(",")) {
    const ambiguous = /^[+-]?[1-9]\d*,\d{3}$/.test(value);
    if (ambiguous || value.includes(".") || value.indexOf(",") !== value.lastIndexOf(",")) return null;
    value = value.replace(",", ".");
  }
  if (!DECIMAL.test(value)) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function dbToMagnitude(db: number): number {
  return Math.min(1, Math.max(0, 10 ** (Math.min(db, 0) / 20)));
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadJson(data: unknown, filename: string): void {
  downloadBlob(new Blob([JSON.stringify(data, null, 2) + "\n"], { type: "application/json" }), filename);
}

export function safeFilename(name: string): string {
  return name.replace(/[\\/:*?"<>|\x00-\x1f]/g, "_").trim() || "project";
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
