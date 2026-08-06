import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../../lib/api";
import type { AssinaturaStatusResponse, PapelSignatario, Vaga } from "../../types/rh";
import { PAPEIS_SIGNATARIO } from "../../types/rh";
import EnviarAssinaturaModal from "./EnviarAssinaturaModal";

type Props = {
  vaga: Vaga;
  token: string | null;
  onClose: () => void;
  onSaved: () => void;
};

const STATUS_LABEL: Record<string, string> = {
  PRE_ENVIO: "Ainda não enviado",
  ENVIADO: "Enviado — aguardando assinaturas",
  PARCIAL: "Parcialmente assinado",
  EM_ALTERACAO: "Em alteração de assinadores",
  CONCLUIDO: "Concluído — todos assinaram",
};

export default function AssinaturaPanel({ vaga, token, onClose, onSaved }: Props) {
  const [dados, setDados] = useState<AssinaturaStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalAberto, setModalAberto] = useState<"enviar" | "aditivo" | null>(null);
  const [popupAditivo, setPopupAditivo] = useState(false);
  const [acaoCarregando, setAcaoCarregando] = useState(false);

  function carregar() {
    setLoading(true);
    apiFetch<AssinaturaStatusResponse>(`/api/rh/vagas/${vaga.id}/assinatura`, { token })
      .then(setDados)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erro ao carregar status."))
      .finally(() => setLoading(false));
  }

  useEffect(() => { carregar(); }, [vaga.id, token]);

  async function handleAlterar() {
    setAcaoCarregando(true);
    setError(null);
    try {
      await apiFetch(`/api/rh/vagas/${vaga.id}/assinatura/alterar`, { method: "POST", token });
      carregar();
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao alterar assinadores.");
    } finally {
      setAcaoCarregando(false);
    }
  }

  async function handleCancelar() {
    setAcaoCarregando(true);
    setError(null);
    try {
      await apiFetch(`/api/rh/vagas/${vaga.id}/assinatura/cancelar`, { method: "POST", token });
      carregar();
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao cancelar envio.");
    } finally {
      setAcaoCarregando(false);
    }
  }

  const atual = dados?.atual;
  const status = atual?.status ?? "PRE_ENVIO";
  const prefillSignatarios = atual?.signatarios?.map((s) => ({
    papel: s.papel as PapelSignatario, nome: s.nome, email: s.email, cargo: s.cargo,
  }));

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4">
      <div className="flex w-full max-w-2xl flex-col rounded-t-xl bg-white dark:bg-gray-900 shadow-xl sm:rounded-xl max-h-[92vh]">
        <div className="flex shrink-0 items-center justify-between border-b border-gray-100 dark:border-gray-800 px-4 py-4 sm:px-6">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-gray-100">
              Assinatura — {vaga.numero_requisicao ?? vaga.id}
            </h2>
            <p className="text-xs text-gray-400">{vaga.candidato ?? vaga.cargo ?? "—"}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none">&times;</button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6 space-y-4">
          {loading && <p className="text-sm text-gray-400">Carregando...</p>}

          {!loading && dados && !dados.configurado && (
            <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 px-3 py-2 text-sm text-amber-800 dark:text-amber-300">
              Assinatura automatizada ainda não configurada (cofre/template do D4Sign pendentes). A tela já funciona — só o envio real fica bloqueado até a configuração ser concluída.
            </div>
          )}

          {!loading && dados && (
            <>
              <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-4">
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  Status: <span className="font-normal">{STATUS_LABEL[status]}</span>
                </p>
                {atual && atual.signatarios.length > 0 && (
                  <ul className="mt-2 space-y-1 text-sm">
                    {atual.signatarios.map((s) => (
                      <li key={s.papel} className="flex items-center justify-between">
                        <span className="text-gray-600 dark:text-gray-300">
                          {PAPEIS_SIGNATARIO.find((p) => p.papel === s.papel)?.label}: {s.nome} ({s.cargo})
                        </span>
                        <span className={s.status === "assinado" ? "text-green-600 dark:text-green-400 text-xs font-semibold" : "text-gray-400 text-xs"}>
                          {s.status === "assinado" ? "Assinado" : "Pendente"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {status === "PRE_ENVIO" && (
                <button onClick={() => setModalAberto("enviar")} className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                  Enviar para assinatura
                </button>
              )}

              {(status === "ENVIADO" || status === "PARCIAL") && (
                <div className="flex gap-2">
                  <button onClick={handleAlterar} disabled={acaoCarregando} className="flex-1 rounded-lg border border-gray-300 dark:border-gray-700 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 disabled:opacity-50">
                    Alterar assinadores
                  </button>
                  <button onClick={handleCancelar} disabled={acaoCarregando} className="flex-1 rounded-lg border border-red-300 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400 disabled:opacity-50">
                    Cancelar envio
                  </button>
                </div>
              )}

              {status === "EM_ALTERACAO" && (
                <button onClick={() => setModalAberto("enviar")} className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                  Corrigir signatários e reenviar
                </button>
              )}

              {status === "CONCLUIDO" && (
                <div className="space-y-2">
                  {atual?.documento_assinado && (
                    <p className="text-sm text-green-700 dark:text-green-400">Documento assinado disponível.</p>
                  )}
                  <button onClick={() => setPopupAditivo(true)} className="w-full rounded-lg border border-gray-300 dark:border-gray-700 px-4 py-2 text-sm text-gray-700 dark:text-gray-300">
                    Cancelar ou Alterar (Aditivo)
                  </button>
                </div>
              )}

              {dados.aditivos.length > 0 && (
                <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-4">
                  <p className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">Aditivos</p>
                  <ul className="space-y-1 text-sm text-gray-600 dark:text-gray-300">
                    {dados.aditivos.map((a) => (
                      <li key={a.id}>
                        {a.tipo_aditivo} — {STATUS_LABEL[a.status]}
                        {a.justificativa_aditivo ? `: ${a.justificativa_aditivo}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {error && (
            <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-700 dark:text-red-300">{error}</div>
          )}
        </div>
      </div>

      {modalAberto === "enviar" && (
        <EnviarAssinaturaModal
          vagaId={vaga.id}
          token={token}
          modo="enviar"
          prefill={prefillSignatarios}
          onClose={() => setModalAberto(null)}
          onSaved={() => { carregar(); onSaved(); }}
        />
      )}

      {popupAditivo && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl bg-white dark:bg-gray-900 p-6 shadow-xl">
            <h3 className="mb-2 font-semibold text-gray-900 dark:text-gray-100">Documento assinado é imutável</h3>
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Este processo já foi assinado por todos e é imutável no D4Sign — não é possível cancelar ou
              editar o documento original diretamente. Para formalizar um cancelamento ou alteração, é
              necessário enviar um novo documento — um <strong>aditivo</strong> — com novas assinaturas das
              mesmas partes, que cancela ou altera formalmente o documento já assinado. O documento original
              nunca é apagado; o aditivo fica anexado a ele como um novo registro assinado.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setPopupAditivo(false)} className="rounded-lg border border-gray-300 dark:border-gray-700 px-4 py-2 text-sm text-gray-700 dark:text-gray-300">
                Cancelar
              </button>
              <button
                onClick={() => { setPopupAditivo(false); setModalAberto("aditivo"); }}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Continuar — criar aditivo
              </button>
            </div>
          </div>
        </div>
      )}

      {modalAberto === "aditivo" && (
        <EnviarAssinaturaModal
          vagaId={vaga.id}
          token={token}
          modo="aditivo"
          prefill={prefillSignatarios}
          onClose={() => setModalAberto(null)}
          onSaved={() => { carregar(); onSaved(); }}
        />
      )}
    </div>
  );
}
