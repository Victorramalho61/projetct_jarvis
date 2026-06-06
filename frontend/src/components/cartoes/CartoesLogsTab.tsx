import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import type { AcessoLog, AccessLogsResponse } from "../../types/cartoes";

interface Props { token: string | null; }

interface Filters {
  localizador_os: string;
  nome_cliente: string;
  produto: string;
  data_acesso_de: string;
  data_acesso_ate: string;
  fornecedor: string;
  nome_pax: string;
}

const EMPTY_FILTERS: Filters = {
  localizador_os: "", nome_cliente: "", produto: "",
  data_acesso_de: "", data_acesso_ate: "", fornecedor: "", nome_pax: "",
};

export default function CartoesLogsTab({ token }: Props) {
  const [logs, setLogs] = useState<AcessoLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(
    (f: Filters, p: number) => {
      setLoading(true);
      const params = new URLSearchParams({ page: String(p), page_size: String(PAGE_SIZE) });
      Object.entries(f).forEach(([k, v]) => { if (v) params.set(k, v); });
      apiFetch<AccessLogsResponse>(`/api/cards/access-logs?${params.toString()}`, { token })
        .then((r) => { setLogs(r.data); setTotal(r.total); })
        .finally(() => setLoading(false));
    },
    [token]
  );

  useEffect(() => { load(applied, page); }, [applied, page, load]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setApplied(filters);
  }

  function handleReset() {
    setFilters(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
    setPage(1);
  }

  async function handleExport(format: "csv" | "xml") {
    setExporting(true);
    const params = new URLSearchParams({ format });
    Object.entries(applied).forEach(([k, v]) => { if (v) params.set(k, v); });
    try {
      const res = await fetch(`/api/cards/access-logs/export?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Erro na exportação");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `acessos_cartoes.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Erro ao exportar.");
    } finally {
      setExporting(false);
    }
  }

  function fmtDate(d: string) {
    return new Date(d).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
  }

  const PRODUTO_LABEL: Record<string, string> = {
    aereo: "Aéreo", hotel: "Hotel", locacao: "Locação",
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-4">
      {/* Filtros */}
      <form onSubmit={handleSearch} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <FilterInput label="Localizador / OS" value={filters.localizador_os} onChange={(v) => setFilters((f) => ({ ...f, localizador_os: v }))} />
          <FilterInput label="Nome do Cliente" value={filters.nome_cliente} onChange={(v) => setFilters((f) => ({ ...f, nome_cliente: v }))} />
          <FilterInput label="Nome do PAX" value={filters.nome_pax} onChange={(v) => setFilters((f) => ({ ...f, nome_pax: v }))} />
          <FilterInput label="Fornecedor" value={filters.fornecedor} onChange={(v) => setFilters((f) => ({ ...f, fornecedor: v }))} />
          <div>
            <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">Produto</label>
            <select
              value={filters.produto}
              onChange={(e) => setFilters((f) => ({ ...f, produto: e.target.value }))}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
            >
              <option value="">Todos</option>
              <option value="aereo">Aéreo</option>
              <option value="hotel">Hotel</option>
              <option value="locacao">Locação</option>
            </select>
          </div>
          <FilterInput type="date" label="Acesso de" value={filters.data_acesso_de} onChange={(v) => setFilters((f) => ({ ...f, data_acesso_de: v }))} />
          <FilterInput type="date" label="Acesso até" value={filters.data_acesso_ate} onChange={(v) => setFilters((f) => ({ ...f, data_acesso_ate: v }))} />
        </div>
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
          <button
            type="button"
            onClick={handleReset}
            className="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          >
            Limpar filtros
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => handleExport("csv")}
              disabled={exporting}
              className="flex items-center gap-1.5 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              CSV
            </button>
            <button
              type="button"
              onClick={() => handleExport("xml")}
              disabled={exporting}
              className="flex items-center gap-1.5 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              XML
            </button>
            <button
              type="submit"
              className="rounded-lg bg-brand-green px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-deep"
            >
              Buscar
            </button>
          </div>
        </div>
      </form>

      {/* Tabela */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        {loading ? (
          <div className="flex justify-center h-40 items-center">
            <div className="h-7 w-7 border-4 border-brand-green/30 border-t-brand-green rounded-full animate-spin" />
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                {["Data/Hora", "Colaborador", "Cartão", "Cliente", "Produto", "Localizador", "PAX", "Fornecedor", "Valor"].map((h) => (
                  <th key={h} className="px-3 py-2.5 text-left font-semibold text-gray-600 dark:text-gray-400 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {logs.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-10 text-center text-gray-400 dark:text-gray-600">Nenhum registro encontrado.</td></tr>
              ) : logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                  <td className="px-3 py-2 whitespace-nowrap font-mono text-gray-600 dark:text-gray-400">{fmtDate(log.data_hora_acesso)}</td>
                  <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">{log.user_nome}</td>
                  <td className="px-3 py-2 font-mono whitespace-nowrap text-gray-600 dark:text-gray-400">
                    {log.cards_cartoes ? `${log.cards_cartoes.bandeira} ••${log.cards_cartoes.numero_final}` : "—"}
                  </td>
                  <td className="px-3 py-2 text-gray-700 dark:text-gray-300 max-w-[120px] truncate">{log.cards_cartoes?.cards_clientes?.nome ?? "—"}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-gray-700 dark:text-gray-300">{PRODUTO_LABEL[log.produto] ?? log.produto}</td>
                  <td className="px-3 py-2 font-mono text-gray-700 dark:text-gray-300 whitespace-nowrap">{log.localizador_os}</td>
                  <td className="px-3 py-2 text-gray-700 dark:text-gray-300 max-w-[100px] truncate">{log.nome_pax}</td>
                  <td className="px-3 py-2 text-gray-700 dark:text-gray-300 max-w-[100px] truncate">{log.fornecedor}</td>
                  <td className="px-3 py-2 text-right whitespace-nowrap font-mono text-gray-700 dark:text-gray-300">
                    R$ {Number(log.valor_transacao).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Paginação */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
          <span>{total} registros</span>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40"
            >
              ←
            </button>
            <span>Página {page} de {totalPages}</span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40"
            >
              →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function FilterInput({ label, value, onChange, type = "text" }: {
  label: string; value: string; onChange: (v: string) => void; type?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
      />
    </div>
  );
}
