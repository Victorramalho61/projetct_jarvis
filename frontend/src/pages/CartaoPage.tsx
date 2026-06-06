import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";
import type { CartaoPerfil } from "../types/cartoes";
import CartoesListaTab from "../components/cartoes/CartoesListaTab";
import CartoesGestaoTab from "../components/cartoes/CartoesGestaoTab";
import CartoesClientesTab from "../components/cartoes/CartoesClientesTab";
import CartoesAprovacoesTab from "../components/cartoes/CartoesAprovacoesTab";
import CartoesLogsTab from "../components/cartoes/CartoesLogsTab";

type Tab = "lista" | "aprovacoes" | "gestao" | "clientes" | "logs";

interface PerfilResponse {
  perfil: CartaoPerfil;
}

export default function CartaoPage() {
  const { token } = useAuth();
  const [perfil, setPerfil] = useState<CartaoPerfil | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("lista");
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    apiFetch<PerfilResponse>("/api/cards/cards/me", { token })
      .then((r) => setPerfil(r.perfil))
      .catch(() => setError("Sem acesso ao módulo de cartões."))
      .finally(() => setLoading(false));
  }, [token]);

  // Atualiza badge de aprovações pendentes a cada 30s (supervisor)
  useEffect(() => {
    if (perfil !== "supervisor") return;
    function fetchPending() {
      apiFetch<unknown[]>("/api/cards/approvals", { token })
        .then((r) => setPendingCount(r?.length ?? 0))
        .catch(() => {});
    }
    fetchPending();
    const t = setInterval(fetchPending, 30_000);
    return () => clearInterval(t);
  }, [perfil, token]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 border-4 border-brand-green/30 border-t-brand-green rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !perfil) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <div className="h-12 w-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
          <svg className="h-6 w-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {error || "Sem acesso ao módulo de cartões."}
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-600">
          Solicite acesso a um supervisor.
        </p>
      </div>
    );
  }

  const TABS: { id: Tab; label: string; supervisorOnly?: boolean }[] = [
    { id: "lista", label: "Cartões" },
    { id: "aprovacoes", label: "Aprovações", supervisorOnly: true },
    { id: "gestao", label: "Gestão de Cartões", supervisorOnly: true },
    { id: "clientes", label: "Clientes", supervisorOnly: true },
    { id: "logs", label: "Log de Acessos", supervisorOnly: true },
  ];

  const visibleTabs = TABS.filter((t) => !t.supervisorOnly || perfil === "supervisor");

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Cofre de Cartões
          </h1>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-0.5">
            {perfil === "supervisor" ? "Acesso supervisor" : "Acesso colaborador"} — dados protegidos por criptografia
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500">
          <svg className="h-4 w-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
          </svg>
          Dados criptografados
        </div>
      </div>

      {/* Tab bar (supervisor) */}
      {perfil === "supervisor" && (
        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav className="flex gap-1 -mb-px overflow-x-auto">
            {visibleTabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`relative flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                  tab === t.id
                    ? "border-brand-green text-brand-green"
                    : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                }`}
              >
                {t.label}
                {t.id === "aprovacoes" && pendingCount > 0 && (
                  <span className="ml-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">
                    {pendingCount}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>
      )}

      {/* Content */}
      {tab === "lista" && <CartoesListaTab token={token} perfil={perfil} />}
      {tab === "aprovacoes" && perfil === "supervisor" && (
        <CartoesAprovacoesTab token={token} onCountChange={setPendingCount} />
      )}
      {tab === "gestao" && perfil === "supervisor" && <CartoesGestaoTab token={token} />}
      {tab === "clientes" && perfil === "supervisor" && <CartoesClientesTab token={token} />}
      {tab === "logs" && perfil === "supervisor" && <CartoesLogsTab token={token} />}
    </div>
  );
}
