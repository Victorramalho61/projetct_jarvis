import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";
import { useRhLookups } from "../hooks/useRhLookups";
import { filtrosToQueryString } from "../lib/rhFilters";
import type { Vaga, VagasFiltros, VagasPage } from "../types/rh";
import FiltrosBar from "../components/rh/FiltrosBar";
import VagasTable from "../components/rh/VagasTable";
import VagaFormModal from "../components/rh/VagaFormModal";
import UploadPlanilhaPanel from "../components/rh/UploadPlanilhaPanel";
import ListasManager from "../components/rh/ListasManager";

const FIELD_CLASS =
  "w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

const TABS = [
  { id: "vagas", label: "Vagas" },
  { id: "upload", label: "Upload de Planilha" },
  { id: "listas", label: "Listas" },
] as const;

function IniciarProcessoModal({
  token, empresas, onClose, onCriado,
}: { token: string | null; empresas: { id: string; nome?: string }[]; onClose: () => void; onCriado: (id: string) => void }) {
  const [empresaId, setEmpresaId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCriar() {
    if (!empresaId) { setError("Selecione a empresa da vaga."); return; }
    setSaving(true);
    setError(null);
    try {
      const vaga = await apiFetch<Vaga>("/api/rh/vagas/iniciar", { method: "POST", json: { empresa_id: empresaId }, token });
      onCriado(vaga.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao iniciar processo.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-xl bg-white dark:bg-gray-900 p-6 shadow-xl">
        <h2 className="mb-1 font-semibold text-gray-900 dark:text-gray-100">Iniciar novo processo de admissão</h2>
        <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
          O número de requisição é gerado automaticamente para a empresa selecionada.
        </p>
        <select value={empresaId} onChange={(e) => setEmpresaId(e.target.value)} className={FIELD_CLASS}>
          <option value="">— selecione a empresa —</option>
          {empresas.map((e) => <option key={e.id} value={e.id}>{e.nome}</option>)}
        </select>
        {error && <p className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-gray-300 dark:border-gray-700 px-4 py-2 text-sm text-gray-700 dark:text-gray-300">
            Cancelar
          </button>
          <button onClick={handleCriar} disabled={saving} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {saving ? "Criando..." : "Iniciar processo"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function RhVagasPage() {
  const { token } = useAuth();
  const { lookups, reload: reloadLookups } = useRhLookups(token);
  const [tab, setTab] = useState<typeof TABS[number]["id"]>("vagas");

  const [filtros, setFiltros] = useState<VagasFiltros>({});
  const [page, setPage] = useState(1);
  const [vagasPage, setVagasPage] = useState<VagasPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [selecionada, setSelecionada] = useState<string | null>(null);
  const [iniciando, setIniciando] = useState(false);

  function carregarVagas() {
    setLoading(true);
    const qs = filtrosToQueryString(filtros, { page, page_size: 50 });
    apiFetch<VagasPage>(`/api/rh/vagas?${qs}`, { token }).then(setVagasPage).finally(() => setLoading(false));
  }

  useEffect(() => { carregarVagas(); }, [filtros, page, token]);

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Vagas — Recursos Humanos</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Cadastro, upload em massa e listas do módulo de RH.</p>
        </div>
        {tab === "vagas" && (
          <button
            onClick={() => setIniciando(true)}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            + Iniciar Novo Processo de Admissão
          </button>
        )}
      </div>

      <div className="flex gap-1 border-b border-gray-200 dark:border-gray-800">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
              tab === t.id
                ? "border-blue-600 text-blue-600 dark:text-blue-400"
                : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "vagas" && (
        <div className="space-y-4">
          <FiltrosBar lookups={lookups} value={filtros} onChange={(f) => { setFiltros(f); setPage(1); }} />
          <VagasTable
            vagas={vagasPage?.items ?? []}
            total={vagasPage?.total ?? 0}
            page={page}
            pageSize={50}
            onPageChange={setPage}
            onSelect={(v) => setSelecionada(v.id)}
            loading={loading}
          />
        </div>
      )}

      {tab === "upload" && (
        <UploadPlanilhaPanel token={token} onImported={() => { carregarVagas(); reloadLookups(); }} />
      )}

      {tab === "listas" && (
        <ListasManager token={token} lookups={lookups} onReload={reloadLookups} />
      )}

      {selecionada && (
        <VagaFormModal
          vagaId={selecionada}
          lookups={lookups}
          token={token}
          onClose={() => setSelecionada(null)}
          onSaved={carregarVagas}
        />
      )}

      {iniciando && (
        <IniciarProcessoModal
          token={token}
          empresas={lookups.empresas}
          onClose={() => setIniciando(false)}
          onCriado={(id) => { setIniciando(false); carregarVagas(); setSelecionada(id); }}
        />
      )}
    </div>
  );
}
