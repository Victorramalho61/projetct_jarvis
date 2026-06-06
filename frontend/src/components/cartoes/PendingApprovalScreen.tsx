import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "../../lib/api";
import type { RevealResponse, SolicitacaoStatus } from "../../types/cartoes";

interface Props {
  solicitacaoId: string;
  token: string | null;
  onRevealed: (data: RevealResponse) => void;
  onRejected: (motivo: string) => void;
  onCancel: () => void;
}

export default function PendingApprovalScreen({
  solicitacaoId,
  token,
  onRevealed,
  onRejected,
  onCancel,
}: Props) {
  const [dots, setDots] = useState(".");
  const [error, setError] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Animação dos dots
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setDots((d) => (d.length >= 3 ? "." : d + "."));
    }, 500);
    return () => clearInterval(intervalRef.current!);
  }, []);

  const confirm = useCallback(async () => {
    try {
      const result = await apiFetch<RevealResponse>(
        `/api/cards/approvals/${solicitacaoId}/confirm`,
        { token, method: "POST" }
      );
      clearInterval(pollRef.current!);
      onRevealed(result);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erro ao confirmar";
      setError(msg);
    }
  }, [solicitacaoId, token, onRevealed]);

  useEffect(() => {
    pollRef.current = setInterval(async () => {
      try {
        const status = await apiFetch<SolicitacaoStatus>(
          `/api/cards/approvals/${solicitacaoId}/status`,
          { token }
        );
        if (status.status === "aprovada") {
          clearInterval(pollRef.current!);
          await confirm();
        } else if (status.status === "rejeitada") {
          clearInterval(pollRef.current!);
          onRejected(status.motivo_rejeicao ?? "Solicitação rejeitada pelo supervisor");
        }
      } catch {
        // Silencia erros de rede no poll — continua tentando
      }
    }, 5000);

    return () => clearInterval(pollRef.current!);
  }, [solicitacaoId, token, confirm, onRejected]);

  return (
    <div className="flex flex-col items-center gap-5 py-4">
      {/* Ícone animado */}
      <div className="relative h-16 w-16">
        <div className="absolute inset-0 rounded-full border-4 border-amber-200 dark:border-amber-800" />
        <div className="absolute inset-0 rounded-full border-4 border-t-amber-500 animate-spin" />
        <div className="absolute inset-0 flex items-center justify-center">
          <svg className="h-7 w-7 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
          </svg>
        </div>
      </div>

      <div className="text-center space-y-1">
        <p className="text-base font-semibold text-gray-900 dark:text-gray-100">
          Aguardando aprovação{dots}
        </p>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Um supervisor precisa autorizar este acesso.<br />
          Esta tela atualiza automaticamente.
        </p>
      </div>

      {/* Motivo: localizador já foi usado antes */}
      <div className="w-full rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 px-4 py-3">
        <p className="text-xs text-amber-700 dark:text-amber-400 font-medium">
          O localizador informado já foi utilizado anteriormente para este cartão.
          Por segurança, o acesso precisa de autorização do supervisor.
        </p>
      </div>

      {error && (
        <div className="w-full rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-4 py-3">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      <button
        onClick={onCancel}
        className="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 underline"
      >
        Cancelar
      </button>
    </div>
  );
}
