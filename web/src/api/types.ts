// Mirrors src/virtual_array/project.py and engine.py payloads.

export type ElementKind = "tx" | "rx";
export type Axis = "azimuth" | "elevation";
export type DictionaryMode = "ideal" | "ideal_reversed" | "channel_pattern" | "custom";
export type ChannelMode = "virtual" | "physical";
export type PatternKind = "amplitude" | "phase";
export type PatternPlane = "horizontal" | "elevation";

export interface Point {
  x: number;
  y: number;
}

export interface Layout {
  tx: Point[];
  rx: Point[];
}

export interface DictionarySettings {
  mode: DictionaryMode;
  azimuth_asset: string | null;
  elevation_asset: string | null;
  channel_mode: ChannelMode;
  phase_reversed: boolean;
  zero_phase_calibrated: boolean;
}

export interface ElementPatternSettings {
  asset: string;
  swap_axes: boolean;
}

export interface ChannelPatternBinding {
  channel: string;
  kind: PatternKind;
  plane: PatternPlane;
  asset: string;
  column_index: number;
  column: string;
}

export type BandPreset = "60G" | "77G" | "92G" | "custom";

export interface Band {
  preset: BandPreset;
  start_ghz: number;
  stop_ghz: number;
}

export interface FieldOfView {
  azimuth: [number, number];
  elevation: [number, number];
}

export interface Requirements {
  azimuth_resolution_deg: number | null;
  elevation_resolution_deg: number | null;
  azimuth_unambiguous_fov: boolean;
  elevation_unambiguous_fov: boolean;
  max_abs_error_deg: number | null;
  min_peak_margin_db: number | null;
  max_psl_db: number | null;
}

export interface Project {
  version: 2;
  name: string;
  /** Design frequency: the layout's λ is defined here. */
  frequency_ghz: number;
  ambiguity_margin_db: number;
  band: Band;
  fov: FieldOfView;
  grid_step_lambda: number;
  requirements: Requirements;
  layout: Layout;
  dbf_dictionary: DictionarySettings;
  element_pattern: ElementPatternSettings | null;
  channel_patterns: ChannelPatternBinding[];
}

/** JSON-safe number from the server: ±Infinity arrive as strings. */
export type WireNumber = number | "Infinity" | "-Infinity" | null;

export interface EncodedArray {
  dtype: "float32" | "float64";
  shape: number[];
  data: string;
}

export type CutReason =
  | "competitor"
  | "error_jump"
  | "boundary_limited"
  | "unreliable"
  | "data_boundary"
  | "normal"
  | null;

export interface AngleMetrics {
  no_fold_left: WireNumber;
  no_fold_right: WireNumber;
  no_fold_width: WireNumber;
  no_fold_max_abs_error: WireNumber;
  focus_max_abs_error: WireNumber;
  center_error: WireNumber;
  min_peak_margin_db: WireNumber;
  center_peak_margin_db: WireNumber;
  negative_cut_reason: CutReason;
  positive_cut_reason: CutReason;
}

export interface ArrayMetrics {
  tx_count: number;
  rx_count: number;
  virtual_count: number;
  unique_count: number;
  azimuth_resolution: WireNumber;
  elevation_resolution: WireNumber;
  azimuth_3db_beamwidth: WireNumber;
  azimuth_null_beamwidth: WireNumber;
  azimuth_islr_db: WireNumber;
  azimuth_first_sidelobe_db: WireNumber;
  azimuth_first_sidelobe_angle: WireNumber;
  azimuth_grating_lobe_db: WireNumber;
  azimuth_grating_lobe_angle: WireNumber;
  elevation_3db_beamwidth: WireNumber;
  psl_db: WireNumber;
  azimuth_psl_db: WireNumber;
  elevation_psl_db: WireNumber;
  sidelobe_azimuth: WireNumber;
  sidelobe_elevation: WireNumber;
  front_radar_status: "Good" | "Acceptable" | "Risky" | "Bad" | string;
  elevation_ambiguity_level: "High" | "Medium" | "Low" | string;
  psl_grade: string;
  warning_messages: string[];
}

export interface VirtualPointGroup {
  x: number;
  y: number;
  count: number;
  pairs: string[];
}

export type AmpPhaseState = "ideal" | "imported" | "mixed";

export interface AxisResolution {
  measured: WireNumber;
  estimate: WireNumber;
  value: WireNumber;
}

export type RequirementKey = "resolution" | "unambiguous_fov" | "max_error" | "peak_margin" | "psl";

export interface RequirementCheck {
  key: RequirementKey;
  axis: Axis | null;
  target: WireNumber;
  actual: WireNumber;
  status: "pass" | "fail" | "na";
}

export interface LayoutCheck {
  code: "coincident" | "too_close" | "design_outside_band";
  a?: string;
  b?: string;
  distance_lambda?: number;
  distance_mm?: number;
}

export interface PerformanceSummary {
  frequency_ghz: number;
  wavelength_mm: number;
  capability: { azimuth: boolean; elevation: boolean; two_d: boolean };
  resolution: Record<Axis, AxisResolution>;
  psl_db: WireNumber;
  azimuth_psl_db: WireNumber;
  elevation_psl_db: WireNumber;
  angle: Record<Axis, AngleMetrics | { error: string } | null>;
  requirements: RequirementCheck[];
  passed: number;
  failed: number;
}

export interface BandSweep {
  band: Band;
  design_ghz: number;
  design_in_band: boolean;
  uses_single_frequency_data: boolean;
  points: (PerformanceSummary & { role: string })[];
}

export type CompareItem = {
  name: string;
  band: Band;
  design_ghz: number;
  tx_count: number;
  rx_count: number;
  fov: FieldOfView;
  error: string | null;
} & Partial<PerformanceSummary>;

export interface Evaluation {
  wavelength_mm: number;
  half_wavelength_mm: number;
  summary: {
    tx_count: number;
    rx_count: number;
    virtual_count: number;
    unique_count: number;
    duplicate_locations: number;
    duplicate_excess: number;
    utilization: number;
    x_aperture_lambda: number;
    y_aperture_lambda: number;
    x_aperture_mm: number;
    y_aperture_mm: number;
  };
  resolution: Record<Axis, AxisResolution>;
  metrics: ArrayMetrics;
  capability: { azimuth: boolean; elevation: boolean; two_d: boolean };
  fov: Record<Axis, [number, number]>;
  virtual_points: VirtualPointGroup[];
  angle: Record<Axis, AngleMetrics | { error: string } | null>;
  requirements: RequirementCheck[];
  layout_checks: LayoutCheck[];
  pattern_status: { amplitude: AmpPhaseState; phase: AmpPhaseState };
  notes: string[];
}

export interface DbfBank {
  axis: Axis;
  fov: [number, number];
  true_angles: number[];
  scan_angles: number[];
  spectra_db: EncodedArray;
  frames: {
    estimated: number[];
    errors: number[];
    main_peak_db: number[];
    competitor_peak_db: WireNumber[];
    margins_db: WireNumber[];
    quality: CutReason[];
  };
  metrics: AngleMetrics;
}

export interface Dbf2dFrame {
  true_azimuth: number;
  true_elevation: number;
  peak_azimuth: number;
  peak_elevation: number;
  peak_db: number;
  spectrum_db: EncodedArray;
}

export interface Dbf2dResult {
  fov: Record<Axis, [number, number]>;
  scan_azimuths: number[];
  scan_elevations: number[];
  frames: Dbf2dFrame[];
}

export interface AssetInfo {
  id: string;
  filename: string;
  size: number;
  uploaded_at: string;
}

export interface PatternCutMetrics {
  peak_angle_deg: number;
  peak_gain_dbi: number;
  beamwidth_3db_deg: number | null;
  beamwidth_6db_deg: number | null;
}

export interface ElementPatternPreview {
  name: string;
  angle_column: string;
  horizontal_column: string;
  elevation_column: string | null;
  angles: number[];
  horizontal_gain_db: number[];
  elevation_gain_db: number[] | null;
  horizontal_metrics: PatternCutMetrics;
  elevation_metrics: PatternCutMetrics | null;
}

export interface DictionaryPreview {
  axis: Axis;
  angles: number[];
  phase_deg: EncodedArray;
  channel_count: number;
  quality: {
    severity: "ok" | "warning" | "danger";
    row_count: number;
    channel_count: number;
    zero_norm_rows: number;
    competitor_ambiguous_rows: number;
    non_neighbor_effective_rank: number;
    non_neighbor_rank_rows: number;
  };
  tables: Record<
    Axis,
    { channel_mode: ChannelMode; value_format: string; rows: number; columns: string[]; is_2d: boolean } | null
  >;
}

export interface ProjectSummary {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  tx_count: number;
  rx_count: number;
  frequency_ghz: number | null;
}

export interface ProjectRecord {
  id: string;
  created_at: string;
  updated_at: string;
  project: Project;
}

export interface ImportResult {
  project: Project;
  missing_assets: string[];
}

export interface ShareCreated {
  id: string;
  created_at: string;
  path: string;
}

export interface ShareRecord extends ImportResult {
  id: string;
  created_at: string;
}

export interface Job {
  id: string;
  kind: "report" | "angle_image";
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  message: string;
  error: string | null;
  download_name: string | null;
}

export interface ReportOptions {
  title: string;
  azimuth_focus: { start: number; stop: number };
  elevation_focus: { start: number; stop: number };
  azimuth_hold: { start: number; stop: number };
  elevation_hold: { start: number; stop: number };
  azimuth_hold_stride_frames: number;
  elevation_hold_stride_frames: number;
  error_limit_deg: number;
  spectrum_floor_db: number;
  include_raw_data: boolean;
  include_spectrum_db: boolean;
  include_spectrum_magnitude: boolean;
  language: "zh" | "en" | "ja";
}

export interface ServerConfig {
  version: string;
  default_project: Project;
  limits: {
    max_tx: number;
    max_rx: number;
    grid_step_lambda: number;
    max_asset_bytes: number;
    max_2d_frames_per_request: number;
    grid_steps_lambda: number[];
    /** Element coordinates must stay within ±this many λ. */
    coordinate_lambda: number;
  };
  band_presets: Record<"60G" | "77G" | "92G", { start_ghz: number; stop_ghz: number; design_ghz: number }>;
  dbf: { scan_fov: [number, number]; scan_step_deg: number; scan_grid_size: number };
}
