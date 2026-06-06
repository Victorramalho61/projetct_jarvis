import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";
import type { CartaoItem, CartaoPerfil } from "../../types/cartoes";
import CardRevealModal from "./CardRevealModal";

interface Props {
  token: string | null;
  perfil: CartaoPerfil;
}

type SortKey = "bandeira" | "numero_final" | "cliente";
type SortDir = "asc" | "desc";

const BANDEIRA_COLORS: Record<string, string> = {
  VISA:      "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  MASTER:    "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  ELO:       "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  AMEX:      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  HIPERCARD: "bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300",
};

export default function CartoesListaTab({ token, perfil }: Props) {
  const [cards, setCards] = useState<CartaoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("bandeira");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [selectedCard, setSelectedCard] = useState<CartaoItem | null>(null);

  useEffect(() => {
    setLoading(true);
    apiFetch<CartaoItem[]>("/api/cards/cards", { token })
      .then((r) => setCards(r))
      .catch(() => setError("Erro ao carregar cartões."))
      .finally(() => setLoading(false));
  }, [token]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  }

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return cards
      .filter((c) => c.ativo)
      .filter((c) =>
        !q ||
        c.bandeira.toLowerCase().includes(q) ||
        c.numero_final.includes(q) ||
        (c.cards_clientes?.nome ?? "").toLowerCase().includes(q)
      )
      .sort((a, b) => {
        let va = "", vb = "";
        if (sortKey === "bandeira") { va = a.bandeira; vb = b.bandeira; }
        else if (sortKey === "numero_final") { va = a.numero_final; vb = b.numero_final; }
        else { va = a.cards_clientes?.nome ?? ""; vb = b.cards_clientes?.nome ?? ""; }
        return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
      });
  }, [cards, search, sortKey, sortDir]);

  function SortIcon({ k }: { k: SortKey }) {
    if (sortKey !== k) return <span className="opacity-30">↕</span>;
    return <span>{sortDir === "asc" ? "↑" : "↓"}</span>;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="h-7 w-7 border-4 border-brand-green/30 border-t-brand-green rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return <p className="text-sm text-red-500 py-8 text-center">{error}</p>;
  }

  return (
    <div className="space-y-3">
      {/* Search */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
          </svg>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por bandeira, 4 dígitos ou cliente…"
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
          />
        </div>
        <span className="text-xs text-gray-400 dark:text-gray-500">{filtered.length} cartão(ões)</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
              <th
                onClick={() => toggleSort("bandeira")}
                className="px-4 py-3 text-left font-semibold text-gray-600 dark:text-gray-400 cursor-pointer select-none whitespace-nowrap hover:text-gray-900 dark:hover:text-gray-100"
              >
                Bandeira <SortIcon k="bandeira" />
              </th>
              <th
                onClick={() => toggleSort("numero_final")}
                className="px-4 py-3 text-left font-semibold text-gray-600 dark:text-gray-400 cursor-pointer select-none whitespace-nowrap hover:text-gray-900 dark:hover:text-gray-100"
              >
                Número <SortIcon k="numero_final" />
              </th>
              <th
                onClick={() => toggleSort("cliente")}
                className="px-4 py-3 text-left font-semibold text-gray-600 dark:text-gray-400 cursor-pointer select-none whitespace-nowrap hover:text-gray-900 dark:hover:text-gray-100"
              >
                Cliente <SortIcon k="cliente" />
              </th>
              <th className="px-4 py-3 text-right font-semibold text-gray-600 dark:text-gray-400">
                Ações
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-gray-400 dark:text-gray-600">
                  Nenhum cartão encontrado.
                </td>
              </tr>
            ) : (
              filtered.map((card) => (
                <tr key={card.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${BANDEIRA_COLORS[card.bandeira.toUpperCase()] ?? "bg-gray-100 text-gray-700"}`}>
                      {card.bandeira}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-700 dark:text-gray-300">
                    •••• •••• •••• {card.numero_final}
                  </td>
                  <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                    {card.cards_clientes?.nome ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setSelectedCard(card)}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-brand-green px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-deep transition-colors"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.641 0-8.573-3.007-9.964-7.178Z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                      </svg>
                      Ver dados
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {selectedCard && (
        <CardRevealModal
          card={selectedCard}
          token={token}
          onClose={() => setSelectedCard(null)}
        />
      )}
    </div>
  );
}
