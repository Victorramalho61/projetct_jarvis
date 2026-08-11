import { useEffect } from "react";
import type { RhLookups } from "../../hooks/useRhLookups";
import type { VagasFiltros } from "../../types/rh";

const ANO_ATUAL = new Date().getFullYear();
const ANOS_DISPONIVEIS = [ANO_ATUAL, ANO_ATUAL - 1, ANO_ATUAL - 2, ANO_ATUAL - 3];

const FIELD_CLASS =
  "w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

type Props = {
  lookups: RhLookups;
  value: VagasFiltros;
  onChange: (next: VagasFiltros) => void;
  showSearch?: boolean;
};

function Select({
  label, value, onChange, options,
}: { label: string; value: string; onChange: (v: string) => void; options: { id: string; nome?: string; sigla?: string }[] }) {
  return (
    <div>
      <label className="mb-1 block text-[11px] font-medium text-gray-500 dark:text-gray-400">{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={FIELD_CLASS}>
        <option value="">Todos</option>
        {options.map((o) => (
          <option key={o.id} value={o.id}>{o.nome ?? o.sigla}</option>
        ))}
      </select>
    </div>
  );
}

export default function FiltrosBar({ lookups, value, onChange, showSearch = true }: Props) {
  function set<K extends keyof VagasFiltros>(key: K, v: VagasFiltros[K]) {
    onChange({ ...value, [key]: v || undefined });
  }

  useEffect(() => {
    if (value.ano === undefined) {
      onChange({ ...value, ano: [ANO_ATUAL] });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="text-[11px] font-medium text-gray-500 dark:text-gray-400">Ano:</label>
        {ANOS_DISPONIVEIS.map((a) => {
          const ativo = (value.ano ?? []).includes(a);
          return (
            <button
              key={a}
              onClick={() => {
                const atual = value.ano ?? [];
                const next = ativo ? atual.filter((x) => x !== a) : [...atual, a];
                onChange({ ...value, ano: next.length ? next : undefined });
              }}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                ativo
                  ? "border-emerald-600 bg-emerald-600 text-white"
                  : "border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
            >
              {a}
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {showSearch && (
          <div className="col-span-2 sm:col-span-3 lg:col-span-2">
            <label className="mb-1 block text-[11px] font-medium text-gray-500 dark:text-gray-400">
              Buscar (candidato, cargo, analista, nº requisição)
            </label>
            <input
              value={value.q ?? ""}
              onChange={(e) => set("q", e.target.value)}
              className={FIELD_CLASS}
              placeholder="Ex: João Silva, Analista, TUR.ADM.280/26"
            />
          </div>
        )}

        <div>
          <label className="mb-1 block text-[11px] font-medium text-gray-500 dark:text-gray-400">De</label>
          <input type="date" value={value.data_inicio ?? ""} onChange={(e) => set("data_inicio", e.target.value)} className={FIELD_CLASS} />
        </div>
        <div>
          <label className="mb-1 block text-[11px] font-medium text-gray-500 dark:text-gray-400">Até</label>
          <input type="date" value={value.data_fim ?? ""} onChange={(e) => set("data_fim", e.target.value)} className={FIELD_CLASS} />
        </div>

        <Select label="Empresa" value={value.empresa_id ?? ""} onChange={(v) => set("empresa_id", v)} options={lookups.empresas} />
        <Select label="Tipo de vaga" value={value.tipo_vaga_id ?? ""} onChange={(v) => set("tipo_vaga_id", v)} options={lookups["tipos-vaga"]} />
        <Select label="Tipo de contrato" value={value.tipo_contrato_id ?? ""} onChange={(v) => set("tipo_contrato_id", v)} options={lookups["tipos-contrato"]} />
        <Select label="Nível" value={value.nivel_id ?? ""} onChange={(v) => set("nivel_id", v)} options={lookups.niveis} />
        <Select label="Hierarquia" value={value.hierarquia_id ?? ""} onChange={(v) => set("hierarquia_id", v)} options={lookups.hierarquias} />
        <Select label="Seção" value={value.secao_id ?? ""} onChange={(v) => set("secao_id", v)} options={lookups.secoes} />
        <Select label="Etapa do processo" value={value.etapa_atual_id ?? ""} onChange={(v) => set("etapa_atual_id", v)} options={lookups.etapas} />
        <Select label="Analista" value={value.responsavel_id ?? ""} onChange={(v) => set("responsavel_id", v)} options={lookups.analistas} />
        <Select label="Requisitante" value={value.requisitante_id ?? ""} onChange={(v) => set("requisitante_id", v)} options={lookups.requisitantes} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <label className="text-[11px] font-medium text-gray-500 dark:text-gray-400 self-center">Status:</label>
        {lookups.status.map((s) => {
          const ativo = (value.status_id ?? []).includes(s.id);
          return (
            <button
              key={s.id}
              onClick={() => {
                const atual = value.status_id ?? [];
                const next = ativo ? atual.filter((id) => id !== s.id) : [...atual, s.id];
                onChange({ ...value, status_id: next.length ? next : undefined });
              }}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                ativo
                  ? "border-blue-600 bg-blue-600 text-white"
                  : "border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
            >
              {s.nome}
            </button>
          );
        })}
        {(Object.keys(value).some((k) => (value as Record<string, unknown>)[k])) && (
          <button
            onClick={() => onChange({})}
            className="ml-auto rounded-full border border-gray-300 dark:border-gray-700 px-3 py-1 text-xs text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            Limpar filtros
          </button>
        )}
      </div>
    </div>
  );
}
