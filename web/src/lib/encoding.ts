import type { EncodedArray, WireNumber } from "../api/types";

export interface Matrix {
  rows: number;
  cols: number;
  data: Float32Array | Float64Array;
}

export function decodeMatrix(encoded: EncodedArray): Matrix {
  const binary = atob(encoded.data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  const data =
    encoded.dtype === "float64" ? new Float64Array(bytes.buffer) : new Float32Array(bytes.buffer);
  const [rows, cols = 1] = encoded.shape;
  return { rows, cols, data };
}

export function matrixRow(matrix: Matrix, row: number): number[] {
  const start = row * matrix.cols;
  return Array.from(matrix.data.subarray(start, start + matrix.cols));
}

export function matrixRows(matrix: Matrix): number[][] {
  const rows: number[][] = [];
  for (let r = 0; r < matrix.rows; r += 1) rows.push(matrixRow(matrix, r));
  return rows;
}

/** Server numbers may be ±Infinity strings or null (NaN). */
export function wire(value: WireNumber | undefined): number | null {
  if (value === null || value === undefined) return null;
  if (value === "Infinity") return Number.POSITIVE_INFINITY;
  if (value === "-Infinity") return Number.NEGATIVE_INFINITY;
  return value;
}
