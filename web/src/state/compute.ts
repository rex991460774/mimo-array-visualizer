import { useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { Axis, DbfBank, NoiseAccuracy, Project } from "../api/types";
import { useStore } from "./store";

const EVALUATE_DEBOUNCE_MS = 120;

/** Fields that affect analysis results (the project name does not). */
export function evaluationKey(project: Project): string {
  const { name: _name, ...rest } = project;
  return JSON.stringify(rest);
}

/** Fields that affect DBF spectra and metrics (frequency and element pattern do not). */
export function dbfKey(project: Project): string {
  return JSON.stringify([
    project.layout,
    project.channel_patterns,
    project.dbf_dictionary,
    project.fov,
    project.ambiguity_margin_db,
  ]);
}

/** Default per-channel SNR for projects saved before the noise analysis existed (server default). */
export const DEFAULT_SNR_DB = 10;

export function snrOf(project: Project): number {
  return project.noise?.snr_db ?? DEFAULT_SNR_DB;
}

/** Fields that affect the noise Monte Carlo: the DBF inputs plus element gain and SNR. */
export function noiseKey(project: Project): string {
  return JSON.stringify([dbfKey(project), project.element_pattern, snrOf(project)]);
}

export function useEvaluationSync(): void {
  const project = useStore((state) => state.project);
  const key = project ? evaluationKey(project) : "";
  useEffect(() => {
    if (!project) return;
    const controller = new AbortController();
    const { setEvaluating, setEvaluation } = useStore.getState();
    const timer = window.setTimeout(async () => {
      setEvaluating(true);
      try {
        const result = await api.evaluate(project, controller.signal);
        setEvaluation(result, null);
      } catch (error) {
        if ((error as Error).name === "AbortError") return;
        setEvaluation(useStore.getState().evaluation, errorMessage(error));
      } finally {
        if (!controller.signal.aborted) setEvaluating(false);
      }
    }, EVALUATE_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
    // `key` captures every result-relevant field of `project`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}

const REQUEST_CACHE_LIMIT = 8;

/** One shared request per key (bounded, oldest first out); failures are retried on the next call. */
function memoized<T>(cache: Map<string, Promise<T>>, key: string, load: () => Promise<T>): Promise<T> {
  let pending = cache.get(key);
  if (!pending) {
    pending = load();
    pending.catch(() => cache.delete(key));
    cache.set(key, pending);
    while (cache.size > REQUEST_CACHE_LIMIT) {
      const oldest = cache.keys().next().value;
      if (oldest === undefined) break;
      cache.delete(oldest);
    }
  }
  return pending;
}

const bankCache = new Map<string, Promise<DbfBank>>();
const noiseCache = new Map<string, Promise<NoiseAccuracy>>();

export function fetchBank(project: Project, axis: Axis): Promise<DbfBank> {
  return memoized(bankCache, `${axis}|${dbfKey(project)}`, () => api.dbfBank(project, axis));
}

export function fetchNoise(project: Project, axis: Axis): Promise<NoiseAccuracy> {
  return memoized(noiseCache, `${axis}|${noiseKey(project)}`, () => api.noise(project, axis));
}

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

export function useDbfBank(axis: Axis, enabled: boolean): AsyncState<DbfBank> {
  return useAxisRequest(axis, enabled, dbfKey, fetchBank);
}

export function useNoiseAccuracy(axis: Axis, enabled: boolean): AsyncState<NoiseAccuracy> {
  return useAxisRequest(axis, enabled, noiseKey, fetchNoise);
}

function useAxisRequest<T>(
  axis: Axis,
  enabled: boolean,
  keyOf: (project: Project) => string,
  load: (project: Project, axis: Axis) => Promise<T>,
): AsyncState<T> {
  const project = useStore((state) => state.project);
  const key = project ? keyOf(project) : "";
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: false });
  useEffect(() => {
    if (!project || !enabled) return;
    let cancelled = false;
    setState((previous) => ({ ...previous, loading: true, error: null }));
    const timer = window.setTimeout(() => {
      load(project, axis).then(
        (data) => !cancelled && setState({ data, error: null, loading: false }),
        (error) => !cancelled && setState({ data: null, error: errorMessage(error), loading: false }),
      );
    }, EVALUATE_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, axis, enabled]);
  return state;
}
