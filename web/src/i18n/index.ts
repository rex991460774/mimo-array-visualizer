import { useCallback } from "react";
import { useStore, type Language } from "../state/store";
import { en, ja, type MessageKey, zh } from "./messages";

const catalogs: Record<Language, Record<MessageKey, string>> = { zh, en, ja };

export type Translate = (key: MessageKey, params?: Record<string, string | number>) => string;

export function translate(language: Language, key: MessageKey, params?: Record<string, string | number>): string {
  const template = catalogs[language]?.[key] ?? zh[key] ?? key;
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

export function useT(): Translate {
  const language = useStore((state) => state.language);
  return useCallback((key, params) => translate(language, key, params), [language]);
}

export const LANGUAGE_LABELS: Record<Language, string> = { zh: "中文", en: "English", ja: "日本語" };

export type { MessageKey };
