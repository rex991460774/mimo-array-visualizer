import { useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { Axis, DbfBank, Project } from "../api/types";
import { useStore } from "./store";

const EVALUATE_DEBOUNCE_MS = 120;

/** Fields that affect analysis results (the project name does not). */
export function evaluationKey(project: Project): string {
  const { name: _name, ...rest } = project;
  return JSON.stringify(rest);
}

/** Fields that affect DBF spectra (frequency, margin and element pattern do not). */
export function dbfKey(project: Project): string {
  return JSON.stringify([project.layout, project.channel_patterns, project.dbf_dictionary]);
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

const bankCache = new Map<string, Promise<DbfBank>>();
const BANK_CACHE_LIMIT = 8;

export function fetchBank(project: Project, axis: Axis): Promise<DbfBank> {
  const key = `${axis}|${dbfKey(project)}`;
  let pending = bankCache.get(key);
  if (!pending) {
    pending = api.dbfBank(project, axis);
    pending.catch(() => bankCache.delete(key));
    bankCache.set(key, pending);
    while (bankCache.size > BANK_CACHE_LIMIT) {
      const oldest = bankCache.keys().next().value;
      if (oldest === undefined) break;
      bankCache.delete(oldest);
    }
  }
  return pending;
}

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

export function useDbfBank(axis: Axis, enabled: boolean): AsyncState<DbfBank> {
  const project = useStore((state) => state.project);
  const key = project ? dbfKey(project) : "";
  const [state, setState] = useState<AsyncState<DbfBank>>({ data: null, error: null, loading: false });
  useEffect(() => {
    if (!project || !enabled) return;
    let cancelled = false;
    setState((previous) => ({ ...previous, loading: true, error: null }));
    const timer = window.setTimeout(() => {
      fetchBank(project, axis).then(
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
