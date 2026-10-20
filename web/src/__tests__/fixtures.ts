import type { Evaluation, Project, ServerConfig } from "../api/types";
import { useStore } from "../state/store";
import configJson from "./fixtures/config.json";
import evaluationJson from "./fixtures/evaluation.json";

/** Real /api/config and /api/evaluate responses captured from the server at 13531eb. */
export const CONFIG = configJson as unknown as ServerConfig;
export const EVALUATION = evaluationJson as unknown as Evaluation;

export function project(overrides: Partial<Project> = {}): Project {
  return { ...structuredClone(CONFIG.default_project), ...overrides };
}

/** Put the store into a freshly-initialised state, as after App start-up. */
export function resetStore(language: "zh" | "en" | "ja" = "zh"): void {
  useStore.setState({
    config: structuredClone(CONFIG),
    project: project(),
    projectId: null,
    projectRevision: null,
    savedSnapshot: null,
    past: [],
    future: [],
    selection: null,
    deleteMode: false,
    view: "array",
    dialog: null,
    language,
    coordUnit: "lambda",
    status: null,
    evaluation: null,
    evaluationError: null,
    evaluating: false,
  });
}

export function jsonResponse(body: unknown, status = 200, statusText = ""): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    statusText,
    headers: { "Content-Type": "application/json" },
  });
}
