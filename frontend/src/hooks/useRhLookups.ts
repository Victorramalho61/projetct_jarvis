import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { LOOKUP_TIPOS, type LookupItem, type LookupTipo } from "../types/rh";

export type RhLookups = Record<LookupTipo, LookupItem[]>;

const EMPTY: RhLookups = LOOKUP_TIPOS.reduce((acc, t) => ({ ...acc, [t]: [] }), {} as RhLookups);

export function useRhLookups(token: string | null) {
  const [lookups, setLookups] = useState<RhLookups>(EMPTY);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const results = await Promise.all(
        LOOKUP_TIPOS.map((tipo) => apiFetch<LookupItem[]>(`/api/rh/lookups/${tipo}`, { token }))
      );
      const next = {} as RhLookups;
      LOOKUP_TIPOS.forEach((tipo, i) => { next[tipo] = results[i]; });
      setLookups(next);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { reload(); }, [reload]);

  return { lookups, loading, reload };
}
