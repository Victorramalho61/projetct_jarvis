import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../../lib/api";
import type { Solicitacao } from "../../types/cartoes";

interface Props {
  token: string | null;
  onCountChange: (n: number) => void;
}

export default function CartoesAprovacoesTab({ token, onCountChange }: Props) {
  const [items, setItems] = useState<Solicitacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState("");
  const [rejectId, setRejectId] = useState("");
  const [motivo, setMotivo] = useState("");
  const [rejecting, setRejecting] = useState(false);

  function load() {
    setLoading(true);
    apiFetch<Solicitacao[]>("/api/cards/approvals", { token })
      .then((r) => {
        setItems(r ?? []);
        onCountChange(r?.length ?? 0);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, [token]);

  async function handleApprove(id: string) {
    setActionId(id);
    try {
      await apiFetch(`/api/cards/approvals/${id}/approve`, { token, method: "POST" });
      load();
    } catch {}
    finally { setActionId(""); }
  }

  async function handleReject() {
    if (!rejectId || !motivo.trim()) return;
    setRejecting(true);
    try {
      await apiFetch(`/api/cards/approvals/${rejectId}/reject`, { token, method: "POST", json: { motivo } });
      setRejectId(""); setMotivo(""); load();
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Erro ao rejeitar.");
    } finally {
      setRejecting(false);
    }
  }

  function fmtDate(d: string) {
    return new Date(d).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
  }

  const PRODUTO_LABEL: Record<string, string> = {
    aereo: "Aéreo", hotel: "Hotel", locacao: "Locação",
  };

  if (loading) {
    return <div className="flex justify-center h-40 items-center"><div className="h-7 w-7 border-4 border-brand-green/30 border-t-brand-green rounded-full animate-spin" /></div>;
  }

  return (
    <div className="space-y-3">
      {items.length === 0 ? (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-6 py-12 text-center">
          <div className="mx-auto h-12 w-12 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-3">
            <svg className="h-6 w-6 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
          </div>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Nenhuma aprovação pendente</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((sol) => (
            <div key={sol.id} className="rounded-xl border border-amber-200 dark:border-amber-700 bg-white dark:bg-gray-900 overflow-hidden">
              <div className="bg-amber-50 dark:bg-amber-900/20 px-4 py-3 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                    <svg className="h-5 w-5 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                      Reuso de localizador detectado
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Solicitado em {fmtDate(sol.created_at)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setRejectId(sol.id)}
                    className="rounded-lg border border-red-200 dark:border-red-700 px-3 py-1.5 text-xs font-semibold text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
                  >
                    Rejeitar
                  </button>
                  <button
                    onClick={() => handleApprove(sol.id)}
                    disabled={actionId === sol.id}
                    className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-40 flex items-center gap-1.5"
                  >
                    {actionId === sol.id && <div className="h-3.5 w-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />}
                    Aprovar
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2 px-4 py-3 text-xs">
                <Info label="Colaborador" value={`${sol.user_nome} (${sol.user_login})`} />
                <Info label="Cartão" value={sol.cards_cartoes ? `${sol.cards_cartoes.bandeira} •••• ${sol.cards_cartoes.numero_final}` : "—"} />
                <Info label="Cliente" value={sol.cards_cartoes?.cards_clientes?.nome ?? "—"} />
                <Info label="Localizador / OS" value={sol.localizador_os} />
                <Info label="Nome do Cliente" value={sol.nome_cliente} />
                <Info label="Produto" value={PRODUTO_LABEL[sol.produto] ?? sol.produto} />
                <Info label="Data da Reserva" value={sol.data_reserva} />
                <Info label="Nome do PAX" value={sol.nome_pax} />
                <Info label="Fornecedor" value={sol.fornecedor} />
                <Info label="Valor da Transação" value={`R$ ${Number(sol.valor_transacao).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal de rejeição */}
      {rejectId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm rounded-xl bg-white dark:bg-gray-900 shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 px-5 py-4">
              <h2 className="font-semibold text-gray-900 dark:text-gray-100">Rejeitar solicitação</h2>
              <button onClick={() => { setRejectId(""); setMotivo(""); }} className="h-8 w-8 grid place-items-center rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="px-5 py-4">
              <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                Motivo da rejeição <span className="text-red-500">*</span>
              </label>
              <textarea
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                rows={3}
                placeholder="Informe o motivo…"
                className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green resize-none"
              />
            </div>
            <div className="flex justify-end gap-3 border-t border-gray-100 dark:border-gray-800 px-5 py-4">
              <button onClick={() => { setRejectId(""); setMotivo(""); }} className="rounded-lg border border-gray-200 dark:border-gray-700 px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800">
                Cancelar
              </button>
              <button onClick={handleReject} disabled={rejecting || !motivo.trim()} className="rounded-lg bg-red-600 px-5 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-40 flex items-center gap-2">
                {rejecting && <div className="h-4 w-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />}
                Rejeitar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-gray-400 dark:text-gray-500">{label}</p>
      <p className="font-medium text-gray-700 dark:text-gray-300 mt-0.5">{value}</p>
    </div>
  );
}
