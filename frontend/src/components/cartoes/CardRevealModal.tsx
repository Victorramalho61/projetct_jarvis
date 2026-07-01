import { useEffect, useRef, useState } from "react";
import { apiFetch, ApiError } from "../../lib/api";
import type { CartaoItem, RevealRequest, RevealResponse } from "../../types/cartoes";
import CardDataDisplay from "./CardDataDisplay";
import PendingApprovalScreen from "./PendingApprovalScreen";
import { useAuth } from "../../context/AuthContext";

interface Props {
  card: CartaoItem;
  token: string | null;
  onClose: () => void;
}

type ModalState = "form" | "submitting" | "pending" | "revealed" | "rejected";

const PRODUTOS = [
  { value: "aereo", label: "Aéreo" },
  { value: "hotel", label: "Hotel" },
  { value: "locacao", label: "Locação de Veículo" },
];

function NowDisplay() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <span>
      {now.toLocaleDateString("pt-BR")} {now.toLocaleTimeString("pt-BR")}
    </span>
  );
}

export default function CardRevealModal({ card, token, onClose }: Props) {
  const { user } = useAuth();
  const [state, setModalState] = useState<ModalState>("form");
  const [solicitacaoId, setSolicitacaoId] = useState("");
  const [revealData, setRevealData] = useState<RevealResponse | null>(null);
  const [rejectionMsg, setRejectionMsg] = useState("");
  const [submitError, setSubmitError] = useState("");
  const backdropRef = useRef<HTMLDivElement>(null);

  const [form, setForm] = useState<RevealRequest>({
    localizador_os: "",
    nome_cliente: "",
    produto: "aereo",
    data_reserva: "",
    nome_pax: "",
    fornecedor: "",
    valor_transacao: 0,
  });

  // ESC fecha o modal em qualquer estado
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") handleClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const isFormValid =
    form.localizador_os.trim() !== "" &&
    form.nome_cliente.trim() !== "" &&
    form.data_reserva !== "" &&
    form.nome_pax.trim() !== "" &&
    form.fornecedor.trim() !== "" &&
    form.valor_transacao > 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isFormValid) return;
    setModalState("submitting");
    setSubmitError("");
    try {
      const res = await apiFetch<RevealResponse>(`/api/cards/cards/${card.id}/reveal`, {
        token,
        method: "POST",
        json: form,
      });
      if (res.status === "revealed") {
        setRevealData(res);
        setModalState("revealed");
      } else {
        setSolicitacaoId(res.solicitacao_id ?? "");
        setModalState("pending");
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Erro ao solicitar acesso";
      setSubmitError(msg);
      setModalState("form");
    }
  }

  function handleExpired() {
    setRevealData(null);
    onClose();
  }

  // Fechar sem estado — ao reabrir, tudo começa do zero
  function handleClose() {
    setRevealData(null);
    setSolicitacaoId("");
    setRejectionMsg("");
    setSubmitError("");
    setModalState("form");
    setForm({
      localizador_os: "",
      nome_cliente: "",
      produto: "aereo",
      data_reserva: "",
      nome_pax: "",
      fornecedor: "",
      valor_transacao: 0,
    });
    onClose();
  }

  // Clique no backdrop fecha apenas quando não está em formulário ativo
  function handleBackdropClick(e: React.MouseEvent) {
    if (e.target === backdropRef.current && state !== "form" && state !== "submitting") {
      handleClose();
    }
  }

  const canClose = state !== "submitting";

  const HEADER_TITLES: Record<ModalState, string> = {
    form: "Solicitar Acesso ao Cartão",
    submitting: "Processando...",
    pending: "Aguardando Aprovação",
    revealed: "Dados do Cartão",
    rejected: "Acesso Negado",
  };

  const clienteNome = card.cards_clientes?.nome ?? "—";

  return (
    <div
      ref={backdropRef}
      onClick={handleBackdropClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
    >
      {/* Modal — flex col com max-height para manter header e footer sempre visíveis */}
      <div className="relative w-full max-w-lg flex flex-col rounded-xl bg-white dark:bg-gray-900 shadow-2xl max-h-[calc(100dvh-2rem)] overflow-hidden">

        {/* Header — sempre visível, nunca rola */}
        <div className="flex-none flex items-center justify-between border-b border-gray-100 dark:border-gray-800 px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">
              {HEADER_TITLES[state]}
            </h2>
            <p className="text-xs text-gray-400 mt-0.5 truncate">
              {card.bandeira} •••• {card.numero_final} — {clienteNome}
            </p>
          </div>
          {canClose && (
            <button
              onClick={handleClose}
              aria-label="Fechar"
              className="flex-none ml-3 h-8 w-8 grid place-items-center rounded-md text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Body — rola se o conteúdo for alto */}
        <div className="flex-1 overflow-y-auto px-5 py-5">

          {/* Estado: revelado */}
          {state === "revealed" && revealData && (
            <CardDataDisplay
              numero={revealData.numero!}
              cvv={revealData.cvv!}
              expiracao={revealData.expiracao!}
              titular={revealData.titular!}
              bandeira={revealData.bandeira!}
              onExpired={handleExpired}
            />
          )}

          {/* Estado: aguardando aprovação */}
          {state === "pending" && (
            <PendingApprovalScreen
              solicitacaoId={solicitacaoId}
              token={token}
              onRevealed={(data) => { setRevealData(data); setModalState("revealed"); }}
              onRejected={(motivo) => { setRejectionMsg(motivo); setModalState("rejected"); }}
              onCancel={handleClose}
            />
          )}

          {/* Estado: rejeitado */}
          {state === "rejected" && (
            <div className="flex flex-col items-center gap-4 py-4">
              <div className="h-14 w-14 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                <svg className="h-7 w-7 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                </svg>
              </div>
              <div className="text-center">
                <p className="font-semibold text-gray-900 dark:text-gray-100">Acesso negado</p>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{rejectionMsg}</p>
              </div>
              <button
                onClick={handleClose}
                className="rounded-lg bg-gray-100 dark:bg-gray-800 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
              >
                Fechar
              </button>
            </div>
          )}

          {/* Estado: formulário */}
          {(state === "form" || state === "submitting") && (
            <form id="reveal-form" onSubmit={handleSubmit} className="space-y-4">
              {/* Dados automáticos — não editáveis */}
              <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3 space-y-1.5">
                <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-2">
                  Dados do colaborador (preenchidos automaticamente)
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-gray-400 dark:text-gray-500 text-xs">Login</span>
                    <p className="font-medium text-gray-700 dark:text-gray-300 break-all">{user?.email}</p>
                  </div>
                  <div>
                    <span className="text-gray-400 dark:text-gray-500 text-xs">Nome</span>
                    <p className="font-medium text-gray-700 dark:text-gray-300">{user?.display_name}</p>
                  </div>
                  <div className="col-span-1 sm:col-span-2">
                    <span className="text-gray-400 dark:text-gray-500 text-xs">Data/Hora da solicitação</span>
                    <p className="font-medium text-gray-700 dark:text-gray-300 font-mono text-xs">
                      <NowDisplay />
                    </p>
                  </div>
                </div>
              </div>

              {/* Campos obrigatórios */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="col-span-1 sm:col-span-2">
                  <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                    Localizador / OS <span className="text-red-500">*</span>
                  </label>
                  <input
                    required
                    value={form.localizador_os}
                    onChange={(e) => setForm((f) => ({ ...f, localizador_os: e.target.value }))}
                    placeholder="Ex: LOC-12345"
                    className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                    Nome do Cliente <span className="text-red-500">*</span>
                  </label>
                  <input
                    required
                    value={form.nome_cliente}
                    onChange={(e) => setForm((f) => ({ ...f, nome_cliente: e.target.value }))}
                    placeholder="Empresa / pessoa"
                    className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                    Produto <span className="text-red-500">*</span>
                  </label>
                  <select
                    required
                    value={form.produto}
                    onChange={(e) => setForm((f) => ({ ...f, produto: e.target.value as RevealRequest["produto"] }))}
                    className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                  >
                    {PRODUTOS.map((p) => (
                      <option key={p.value} value={p.value}>{p.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                    Data da Reserva <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={form.data_reserva}
                    onChange={(e) => setForm((f) => ({ ...f, data_reserva: e.target.value }))}
                    className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                    Nome do PAX <span className="text-red-500">*</span>
                  </label>
                  <input
                    required
                    value={form.nome_pax}
                    onChange={(e) => setForm((f) => ({ ...f, nome_pax: e.target.value }))}
                    placeholder="Passageiro / hóspede"
                    className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                    Fornecedor <span className="text-red-500">*</span>
                  </label>
                  <input
                    required
                    value={form.fornecedor}
                    onChange={(e) => setForm((f) => ({ ...f, fornecedor: e.target.value }))}
                    placeholder="LATAM, Accor, Localiza..."
                    className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                    Valor da Transação (R$) <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    required
                    min={0.01}
                    step={0.01}
                    value={form.valor_transacao || ""}
                    onChange={(e) => setForm((f) => ({ ...f, valor_transacao: parseFloat(e.target.value) || 0 }))}
                    placeholder="0,00"
                    className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                  />
                </div>
              </div>

              {submitError && (
                <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-4 py-3">
                  <p className="text-sm text-red-600 dark:text-red-400">{submitError}</p>
                </div>
              )}
            </form>
          )}
        </div>

        {/* Footer — sempre visível, nunca rola */}
        {(state === "form" || state === "submitting") && (
          <div className="flex-none flex items-center justify-between border-t border-gray-100 dark:border-gray-800 px-5 py-4">
            <button
              type="button"
              onClick={handleClose}
              className="rounded-lg border border-gray-200 dark:border-gray-700 px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="reveal-form"
              disabled={!isFormValid || state === "submitting"}
              className="rounded-lg bg-brand-green px-5 py-2 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {state === "submitting" && (
                <div className="h-4 w-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              )}
              Confirmar acesso
            </button>
          </div>
        )}

        {state === "revealed" && (
          <div className="flex-none border-t border-gray-100 dark:border-gray-800 px-5 py-4">
            <button
              onClick={handleClose}
              className="w-full rounded-lg bg-gray-100 dark:bg-gray-800 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
            >
              Fechar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
