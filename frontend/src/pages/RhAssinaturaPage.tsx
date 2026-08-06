import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";
import { useRhLookups } from "../hooks/useRhLookups";
import { filtrosToQueryString } from "../lib/rhFilters";
import type { Vaga, VagasFiltros, VagasPage } from "../types/rh";
import FiltrosBar from "../components/rh/FiltrosBar";
import VagasTable from "../components/rh/VagasTable";
import AssinaturaPanel from "../components/rh/AssinaturaPanel";

export default function RhAssinaturaPage() {
  const { token } = useAuth();
  const { lookups } = useRhLookups(token);

  const [filtros, setFiltros] = useState<VagasFiltros>({});
  const [page, setPage] = useState(1);
  const [vagasPage, setVagasPage] = useState<VagasPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [selecionada, setSelecionada] = useState<Vaga | null>(null);

  function carregarVagas() {
    setLoading(true);
    const qs = filtrosToQueryString(filtros, { page, page_size: 50 });
    apiFetch<VagasPage>(`/api/rh/vagas?${qs}`, { token }).then(setVagasPage).finally(() => setLoading(false));
  }

  useEffect(() => { carregarVagas(); }, [filtros, page, token]);

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Assinatura Automatizada — Recursos Humanos</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Envie a Requisição de Pessoal pra assinatura eletrônica via D4Sign, em vez de imprimir. As duas
          opções convivem — escolha em cada vaga qual usar.
        </p>
      </div>

      <FiltrosBar lookups={lookups} value={filtros} onChange={(f) => { setFiltros(f); setPage(1); }} />

      <VagasTable
        vagas={vagasPage?.items ?? []}
        total={vagasPage?.total ?? 0}
        page={page}
        pageSize={50}
        onPageChange={setPage}
        onSelect={setSelecionada}
        loading={loading}
      />

      {selecionada && (
        <AssinaturaPanel
          vaga={selecionada}
          token={token}
          onClose={() => setSelecionada(null)}
          onSaved={carregarVagas}
        />
      )}
    </div>
  );
}
