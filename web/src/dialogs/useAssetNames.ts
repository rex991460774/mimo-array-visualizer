import { useEffect, useState } from "react";
import { api } from "../api/client";

const names = new Map<string, string>();

export function rememberAssetName(id: string, filename: string): void {
  names.set(id, filename);
}

/** Resolve asset IDs to their original filenames (cached for the session). */
export function useAssetNames(ids: (string | null | undefined)[]): Record<string, string> {
  const wanted = [...new Set(ids.filter((id): id is string => Boolean(id)))];
  const key = wanted.join(",");
  const [, setVersion] = useState(0);
  useEffect(() => {
    let cancelled = false;
    const missing = wanted.filter((id) => !names.has(id));
    if (missing.length === 0) return;
    Promise.all(
      missing.map((id) =>
        api.assetInfo(id).then(
          (info) => names.set(id, info.filename),
          () => names.set(id, id.slice(0, 12)),
        ),
      ),
    ).then(() => !cancelled && setVersion((value) => value + 1));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return Object.fromEntries(wanted.map((id) => [id, names.get(id) ?? "…"]));
}
