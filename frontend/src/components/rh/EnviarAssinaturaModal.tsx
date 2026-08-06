import { useState } from "react";
import { apiFetch, ApiError } from "../../lib/api";
import { PAPEIS_SIGNATARIO, type SignatarioForm } from "../../types/rh";

const FIELD_CLASS =
  "w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

type Props = {
  vagaId: string;
  token: string | null;
  modo: "enviar" | "aditivo";
  prefill?: SignatarioForm[];
  onClose: () => void;
  onSaved: () => void;
};

function vazio(): SignatarioForm[] {
  return PAPEIS_SIGNATARIO.map((p) => ({ papel: p.papel, nome: "", email: "", cargo: "" }));
}

export default function EnviarAssinaturaModal({ vagaId, token, modo, prefill, onClose, onSaved }: Props) {
  const [signatarios, setSignatarios] = useState<SignatarioForm[]>(prefill?.length ? prefill : vazio());
  const [tipoAditivo, setTipoAditivo] = useState<"CANCELAMENTO" | "ALTERACAO">("ALTERACAO");
  const [justificativa, setJustificativa] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set(idx: number, campo: keyof SignatarioForm, valor: string) {
    setSignatarios((prev) => prev.map((s, i) => (i === idx ? { ...s, [campo]: valor } : s)));
  }

  async function handleSubmit() {
    for (const s of signatarios) {
      if (!s.nome.trim() || !s.email.trim() || !s.cargo.trim()) {
        setError("Preencha nome, e-mail e cargo dos 4 signatários.");
        return;
      }
    }
    if (modo === "aditivo" && !justificativa.trim()) {
      setError("Justificativa é obrigatória pro aditivo.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (modo === "enviar") {
        await apiFetch(`/api/rh/vagas/${vagaId}/assinatura/enviar`, {
          method: "POST", json: { signatarios }, token,
        });
      } else {
        await apiFetch(`/api/rh/vagas/${vagaId}/assinatura/aditivo`, {
          method: "POST", json: { tipo: tipoAditivo, justificativa, signatarios }, token,
        });
      }
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao enviar pra assinatura.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4">
      <div className="flex w-full max-w-2xl flex-col rounded-t-xl bg-white dark:bg-gray-900 shadow-xl sm:rounded-xl max-h-[92vh]">
        <div className="flex shrink-0 items-center justify-between border-b border-gray-100 dark:border-gray-800 px-4 py-4 sm:px-6">
          <h2 className="font-semibold text-gray-900 dark:text-gray-100">
            {modo === "enviar" ? "Enviar para assinatura" : "Criar aditivo"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none">&times;</button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6 space-y-4">
          {modo === "aditivo" && (
            <>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Tipo do aditivo</label>
                <select value={tipoAditivo} onChange={(e) => setTipoAditivo(e.target.value as typeof tipoAditivo)} className={FIELD_CLASS}>
                  <option value="ALTERACAO">Alteração — corrige dados, a vaga continua ativa</option>
                  <option value="CANCELAMENTO">Cancelamento — encerra a vaga (status muda pra Cancelado)</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Justificativa *</label>
                <textarea value={justificativa} onChange={(e) => setJustificativa(e.target.value)} rows={3} className={FIELD_CLASS}
                  placeholder="Explique o motivo do cancelamento/alteração — fica registrado no documento e no histórico." />
              </div>
            </>
          )}

          <div className="space-y-3">
            {signatarios.map((s, idx) => (
              <div key={s.papel} className="rounded-lg border border-gray-200 dark:border-gray-800 p-3">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                  {PAPEIS_SIGNATARIO.find((p) => p.papel === s.papel)?.label}
                </p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <input value={s.nome} onChange={(e) => set(idx, "nome", e.target.value)} placeholder="Nome" className={FIELD_CLASS} />
                  <input value={s.email} onChange={(e) => set(idx, "email", e.target.value)} placeholder="E-mail" type="email" className={FIELD_CLASS} />
                  <input value={s.cargo} onChange={(e) => set(idx, "cargo", e.target.value)} placeholder="Cargo" className={FIELD_CLASS} />
                </div>
              </div>
            ))}
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-700 dark:text-red-300">{error}</div>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-gray-100 dark:border-gray-800 px-4 py-4 sm:px-6">
          <button onClick={onClose} className="rounded-lg border border-gray-300 dark:border-gray-700 px-4 py-2 text-sm text-gray-700 dark:text-gray-300">
            Cancelar
          </button>
          <button onClick={handleSubmit} disabled={saving} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {saving ? "Enviando..." : modo === "enviar" ? "Enviar para assinatura" : "Enviar aditivo"}
          </button>
        </div>
      </div>
    </div>
  );
}
