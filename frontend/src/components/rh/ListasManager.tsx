import { useState } from "react";
import { apiFetch, ApiError } from "../../lib/api";
import type { RhLookups } from "../../hooks/useRhLookups";
import { LOOKUP_TIPOS, type LookupItem, type LookupTipo } from "../../types/rh";

const LABELS: Record<LookupTipo, string> = {
  empresas: "Empresas", ufs: "UFs", alocacoes: "Alocações reais",
  "tipos-contrato": "Tipos de contrato", "tipos-vaga": "Tipos de vaga",
  cargos: "Cargos", niveis: "Níveis", hierarquias: "Hierarquias",
  secoes: "Seções", status: "Status da vaga", modalidades: "Modalidades de contratação",
  analistas: "Analistas (R&S)", requisitantes: "Requisitantes", etapas: "Etapas do processo",
};

const FIELD_CLASS =
  "w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

type Props = {
  token: string | null;
  lookups: RhLookups;
  onReload: () => void;
};

export default function ListasManager({ token, lookups, onReload }: Props) {
  const [tipo, setTipo] = useState<LookupTipo>("empresas");
  const [novoNome, setNovoNome] = useState("");
  const [novoExtra, setNovoExtra] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const itens = lookups[tipo] ?? [];
  const nameKey = tipo === "ufs" ? "sigla" : "nome";

  async function handleAdd() {
    if (!novoNome.trim()) return;
    setError(null);
    try {
      const payload: Record<string, unknown> = { [nameKey]: novoNome.trim(), ...novoExtra };
      await apiFetch(`/api/rh/lookups/${tipo}`, { method: "POST", json: payload, token });
      setNovoNome("");
      setNovoExtra({});
      onReload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao adicionar.");
    }
  }

  async function handleDelete(item: LookupItem) {
    setError(null);
    try {
      await apiFetch(`/api/rh/lookups/${tipo}/${item.id}`, { method: "DELETE", token });
      onReload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao remover.");
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">Listas</h3>
        <div className="flex flex-col gap-1">
          {LOOKUP_TIPOS.map((t) => (
            <button
              key={t}
              onClick={() => setTipo(t)}
              className={`rounded-lg px-3 py-2 text-left text-sm ${
                tipo === t ? "bg-blue-600 text-white" : "text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
            >
              {LABELS[t]} <span className="opacity-60">({(lookups[t] ?? []).length})</span>
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 lg:col-span-3">
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">{LABELS[tipo]}</h3>

        <div className="mb-4 flex flex-wrap items-end gap-2">
          <input
            value={novoNome}
            onChange={(e) => setNovoNome(e.target.value)}
            placeholder={tipo === "ufs" ? "Ex: DF" : "Novo item..."}
            className={`${FIELD_CLASS} max-w-xs`}
          />

          {tipo === "empresas" && (
            <input
              value={novoExtra.prefixo_requisicao ?? ""}
              onChange={(e) => setNovoExtra({ ...novoExtra, prefixo_requisicao: e.target.value.toUpperCase() })}
              placeholder="Prefixo (ex: TUR)"
              className={`${FIELD_CLASS} max-w-[140px]`}
            />
          )}
          {tipo === "cargos" && (
            <select
              value={novoExtra.nivel_padrao_id ?? ""}
              onChange={(e) => setNovoExtra({ ...novoExtra, nivel_padrao_id: e.target.value })}
              className={`${FIELD_CLASS} max-w-[200px]`}
            >
              <option value="">Nível padrão (opcional)</option>
              {lookups.niveis.map((n) => <option key={n.id} value={n.id}>{n.nome}</option>)}
            </select>
          )}
          {tipo === "etapas" && (
            <>
              <input
                type="number"
                value={novoExtra.ordem ?? ""}
                onChange={(e) => setNovoExtra({ ...novoExtra, ordem: e.target.value })}
                placeholder="Ordem"
                className={`${FIELD_CLASS} max-w-[100px]`}
              />
              <select
                value={novoExtra.secao_responsavel_id ?? ""}
                onChange={(e) => setNovoExtra({ ...novoExtra, secao_responsavel_id: e.target.value })}
                className={`${FIELD_CLASS} max-w-[200px]`}
              >
                <option value="">Seção responsável</option>
                {lookups.secoes.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
              </select>
            </>
          )}
          {tipo === "status" && (
            <>
              <label className="flex items-center gap-1 text-sm text-gray-600 dark:text-gray-300">
                <input type="checkbox" onChange={(e) => setNovoExtra({ ...novoExtra, em_aberto: String(e.target.checked) })} /> Em aberto
              </label>
              <label className="flex items-center gap-1 text-sm text-gray-600 dark:text-gray-300">
                <input type="checkbox" onChange={(e) => setNovoExtra({ ...novoExtra, concluido: String(e.target.checked) })} /> Concluído
              </label>
            </>
          )}

          <button onClick={handleAdd} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
            Adicionar
          </button>
        </div>

        {error && (
          <div className="mb-3 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-700 dark:text-red-300">{error}</div>
        )}

        <div className="max-h-[420px] overflow-y-auto divide-y divide-gray-100 dark:divide-gray-800">
          {itens.length === 0 && <p className="py-4 text-sm text-gray-400">Nenhum item cadastrado.</p>}
          {itens.map((item) => (
            <div key={item.id} className="flex items-center justify-between py-2 text-sm">
              <span className="text-gray-700 dark:text-gray-300">
                {tipo === "ufs" ? item.sigla : item.nome}
                {tipo === "empresas" && item.prefixo_requisicao && (
                  <span className="ml-2 text-xs text-gray-400">({item.prefixo_requisicao})</span>
                )}
                {tipo === "etapas" && (
                  <span className="ml-2 text-xs text-gray-400">#{item.ordem}</span>
                )}
              </span>
              <button onClick={() => handleDelete(item)} className="text-xs text-red-600 dark:text-red-400 hover:underline">
                Remover
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
