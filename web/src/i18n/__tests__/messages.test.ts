import { describe, expect, it } from "vitest";
import { HELP } from "../help";
import { en, ja, zh } from "../messages";

describe("i18n catalogues", () => {
  it("define the same keys and placeholders in every language", () => {
    const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const catalog of [en, ja]) {
      expect(Object.keys(catalog).sort()).toEqual(Object.keys(zh).sort());
      for (const key of Object.keys(zh) as (keyof typeof zh)[]) {
        expect(placeholders(catalog[key]), key).toEqual(placeholders(zh[key]));
      }
    }
  });

  it("help sections line up across languages", () => {
    const ids = (language: keyof typeof HELP) => HELP[language].map((section) => section.id);
    expect(ids("en")).toEqual(ids("zh"));
    expect(ids("ja")).toEqual(ids("zh"));
  });
});
