import { beforeEach, describe, expect, it, vi } from "vitest";
import { CONFIG, project, resetStore } from "../../__tests__/fixtures";
import { projectSnapshot, useStore } from "../store";

const s = () => useStore.getState();
const LIMIT = CONFIG.limits.coordinate_lambda;

beforeEach(() => resetStore());

describe("commitLayout", () => {
  it("records history, clears redo and renumbers by position", () => {
    const before = s().project!.layout;
    const tx = [...before.tx];
    tx[0] = { x: 100, y: 0 }; // Tx1 moves to the far right → becomes the last Tx
    s().commitLayout({ ...before, tx }, { kind: "tx", index: 0 });
    expect(s().past).toEqual([before]);
    expect(s().future).toEqual([]);
    expect(s().project!.layout.tx.at(-1)).toEqual({ x: 100, y: 0 });
    expect(s().selection).toEqual({ kind: "tx", index: before.tx.length - 1 });
  });

  it.each([LIMIT, -LIMIT])("accepts a coordinate exactly at the limit (%d λ)", (x) => {
    const layout = { ...s().project!.layout, rx: [{ x, y: 0 }, ...s().project!.layout.rx.slice(1)] };
    s().commitLayout(layout);
    expect(s().past).toHaveLength(1);
    expect(s().status).toBeNull();
  });

  it.each([LIMIT + 0.01, -LIMIT - 0.01, 1e6, Number.NaN, Number.POSITIVE_INFINITY])(
    "refuses an out-of-range coordinate %d and reports physical.outOfRange (round 1 ±500λ bug)",
    (x) => {
      const before = s().project!.layout;
      s().commitLayout({ ...before, tx: [{ x, y: 0 }, ...before.tx.slice(1)] });
      expect(s().project!.layout).toBe(before);
      expect(s().past).toHaveLength(0);
      expect(s().status).toMatchObject({ key: "physical.outOfRange", tone: "error", params: { limit: LIMIT } });
    },
  );

  it("checks the y coordinate as well", () => {
    const before = s().project!.layout;
    s().commitLayout({ ...before, rx: [{ x: 0, y: -(LIMIT + 1) }, ...before.rx.slice(1)] });
    expect(s().project!.layout).toBe(before);
  });

  it("an unchanged layout does not create a history entry", () => {
    s().commitLayout(structuredClone(s().project!.layout), { kind: "rx", index: 2 });
    expect(s().past).toHaveLength(0);
    expect(s().selection).toEqual({ kind: "rx", index: 2 });
  });

  it("without a published limit, any finite layout is accepted", () => {
    const config = structuredClone(CONFIG);
    delete (config.limits as Partial<typeof config.limits>).coordinate_lambda;
    useStore.setState({ config });
    const before = s().project!.layout;
    s().commitLayout({ ...before, tx: [{ x: 1e5, y: 0 }, ...before.tx.slice(1)] });
    expect(s().past).toHaveLength(1);
  });

  it("history is capped at 50 entries", () => {
    for (let i = 1; i <= 60; i += 1) {
      const layout = s().project!.layout;
      s().commitLayout({ ...layout, tx: [{ x: -i, y: 0 }, ...layout.tx.slice(1)] }, null);
    }
    expect(s().past).toHaveLength(50);
  });
});

describe("undo / redo", () => {
  it("round-trips a change and reports status", () => {
    const original = s().project!.layout;
    s().commitLayout({ ...original, tx: [{ x: -3, y: 0 }, ...original.tx.slice(1)] });
    const changed = s().project!.layout;
    s().undo();
    expect(s().project!.layout).toEqual(original);
    expect(s().status?.key).toBe("status.undo");
    expect(s().future).toEqual([changed]);
    s().redo();
    expect(s().project!.layout).toEqual(changed);
    expect(s().status?.key).toBe("status.redo");
    expect(s().future).toEqual([]);
  });

  it("reports when there is nothing to undo or redo", () => {
    s().undo();
    expect(s().status?.key).toBe("status.nothingToUndo");
    s().redo();
    expect(s().status?.key).toBe("status.nothingToRedo");
  });

  it("a new edit after undo discards the redo stack", () => {
    const original = s().project!.layout;
    s().commitLayout({ ...original, tx: [{ x: -3, y: 0 }, ...original.tx.slice(1)] });
    s().undo();
    s().commitLayout({ ...original, tx: [{ x: -4, y: 0 }, ...original.tx.slice(1)] });
    expect(s().future).toEqual([]);
    s().redo();
    expect(s().status?.key).toBe("status.nothingToRedo");
  });

  it("undo clears the selection", () => {
    const original = s().project!.layout;
    s().commitLayout({ ...original, tx: [{ x: -3, y: 0 }, ...original.tx.slice(1)] }, { kind: "tx", index: 0 });
    s().undo();
    expect(s().selection).toBeNull();
  });
});

describe("project lifecycle", () => {
  it("replaceProject resets history and remembers the library revision", () => {
    s().commitLayout({ ...s().project!.layout, tx: [{ x: -3, y: 0 }, ...s().project!.layout.tx.slice(1)] });
    const p = project({ name: "Loaded" });
    s().replaceProject(p, "a".repeat(32), true, 7);
    expect(s()).toMatchObject({ projectId: "a".repeat(32), projectRevision: 7, past: [], future: [], selection: null });
    expect(s().savedSnapshot).toBe(projectSnapshot(p));
  });

  it("replaceProject without an id drops the revision", () => {
    s().replaceProject(project(), null, false, 9);
    expect(s().projectRevision).toBeNull();
    expect(s().savedSnapshot).toBeNull();
  });

  it("markSaved stores id, revision and the saved snapshot", () => {
    const p = s().project!;
    s().markSaved("b".repeat(32), p, 3);
    expect(s()).toMatchObject({ projectId: "b".repeat(32), projectRevision: 3, savedSnapshot: projectSnapshot(p) });
  });

  it("updateProject merges fields", () => {
    s().updateProject({ name: "X", frequency_ghz: 79 });
    expect(s().project).toMatchObject({ name: "X", frequency_ghz: 79 });
  });

  it("initialize fills fields missing from an old draft with defaults", () => {
    useStore.setState({ project: null, config: null });
    s().initialize(CONFIG);
    expect(s().project).toEqual(CONFIG.default_project);
  });

  it("initialize keeps an old draft's band and fills newer fields", () => {
    const defaults = { ...structuredClone(CONFIG.default_project), noise: { snr_db: 10 } };
    defaults.band = { ...defaults.band, dictionary_frequency: "operating" };
    const draft = structuredClone(CONFIG.default_project) as Partial<typeof defaults>;
    draft.band = { preset: "custom", start_ghz: 77, stop_ghz: 79 };
    delete draft.noise;
    window.localStorage.setItem("mimo-array-workbench:v1", JSON.stringify({ project: draft }));
    vi.resetModules();
    return import("../store").then(({ useStore: fresh }) => {
      fresh.getState().initialize({ ...CONFIG, default_project: defaults });
      expect(fresh.getState().project!.band).toEqual({ preset: "custom", start_ghz: 77, stop_ghz: 79, dictionary_frequency: "operating" });
      expect(fresh.getState().project!.noise).toEqual({ snr_db: 10 });
      expect(fresh.getState().angleMode).toBe("ideal");
    });
  });

  it("persists the working draft and preferences to localStorage", () => {
    s().setLanguage("en");
    s().updateProject({ name: "Persisted" });
    const stored = JSON.parse(window.localStorage.getItem("mimo-array-workbench:v1")!);
    expect(stored.project.name).toBe("Persisted");
    expect(stored.language).toBe("en");
  });

  it("delete mode clears the selection; leaving it keeps the current one", () => {
    s().select({ kind: "rx", index: 1 });
    s().setDeleteMode(true);
    expect(s().selection).toBeNull();
    s().select({ kind: "rx", index: 1 });
    s().setDeleteMode(false);
    expect(s().selection).toEqual({ kind: "rx", index: 1 });
  });

  it("simple setters", () => {
    s().setView("angle");
    s().openDialog("help");
    s().setTheme("dark");
    s().setDisplay("magnitude");
    s().setCoordUnit("mm");
    s().setAngleMode("noise");
    s().setEvaluating(true);
    s().setEvaluation(null, "boom");
    expect(s()).toMatchObject({
      view: "angle",
      dialog: "help",
      theme: "dark",
      display: "magnitude",
      coordUnit: "mm",
      angleMode: "noise",
      evaluating: true,
      evaluationError: "boom",
    });
  });
});
