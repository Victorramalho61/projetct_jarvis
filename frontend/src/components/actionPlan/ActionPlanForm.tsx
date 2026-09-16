import { useState } from "react";
import { IndicatorOption, ItemFields, EMPTY_ITEM, FIELD_LABELS, REQUIRED_ITEMS } from "./formFields";

// Formulário de preenchimento do Plano de Ação (2 competências + 5 campos cada),
// reaproveitado do fluxo do gestor (pages/PublicActionPlanPage.tsx) — mesma UI e
// validação, mas embutível dentro de outra tela (ex: logo após a ciência da
// avaliação) em vez de ser uma página inteira própria. Quem chama decide o
// endpoint (via `onSubmit`) e mostra o próprio cabeçalho/contexto por fora.

export function ActionPlanForm({
  indicators,
  onSubmit,
}: {
  indicators: IndicatorOption[];
  onSubmit: (payload: { items: (ItemFields & { indicator_id: string })[]; frequencia_alinhamento: string }) => Promise<void>;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [fieldsByIndicator, setFieldsByIndicator] = useState<Record<string, ItemFields>>({});
  const [frequenciaAlinhamento, setFrequenciaAlinhamento] = useState("");
  const [showReview, setShowReview] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [formError, setFormError] = useState("");
  const [done, setDone] = useState(false);

  function toggleIndicator(id: string) {
    setFormError("");
    setSelected(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id);
      if (prev.length >= REQUIRED_ITEMS) return prev;
      return [...prev, id];
    });
    setFieldsByIndicator(prev => prev[id] ? prev : { ...prev, [id]: { ...EMPTY_ITEM } });
  }

  function updateField(id: string, key: keyof ItemFields, value: string) {
    setFieldsByIndicator(prev => ({ ...prev, [id]: { ...(prev[id] || EMPTY_ITEM), [key]: value } }));
  }

  function validateAndOpenReview() {
    setFormError("");
    if (selected.length !== REQUIRED_ITEMS) {
      setFormError(`Escolha exatamente ${REQUIRED_ITEMS} competências prioritárias.`);
      return;
    }
    for (const id of selected) {
      const f = fieldsByIndicator[id] || EMPTY_ITEM;
      if (FIELD_LABELS.some(fl => !f[fl.key].trim())) {
        setFormError("Preencha todos os campos das competências escolhidas antes de revisar.");
        return;
      }
    }
    if (!frequenciaAlinhamento.trim()) {
      setFormError("Informe a frequência de alinhamento (combinados de acompanhamento).");
      return;
    }
    setShowReview(true);
  }

  async function handleConfirmSubmit() {
    setSubmitting(true);
    setSubmitError("");
    try {
      await onSubmit({
        items: selected.map(id => ({ indicator_id: id, ...(fieldsByIndicator[id] || EMPTY_ITEM) })),
        frequencia_alinhamento: frequenciaAlinhamento.trim(),
      });
      setShowReview(false);
      setDone(true);
    } catch (e: any) {
      setSubmitError(e?.message || "Erro ao enviar.");
    } finally {
      setSubmitting(false);
    }
  }

  const selectedIndicators = indicators.filter(i => selected.includes(i.indicator_id));

  if (done) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-2xl p-8 text-center shadow border">
        <div className="text-4xl mb-3">✅</div>
        <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-1">Plano de Ação Enviado</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Obrigado! O RH vai acompanhar o andamento a cada 3 meses.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4">
        <p className="text-sm text-amber-800 dark:text-amber-200">
          Escolha exatamente <strong>{REQUIRED_ITEMS} competências prioritárias</strong> para o seu plano de
          desenvolvimento nos próximos 12 meses.
          {" "}<span className="font-semibold">Selecionadas: {selected.length}/{REQUIRED_ITEMS}</span>
        </p>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-2xl p-4 sm:p-6 shadow border space-y-2">
        {indicators.map(ind => {
          const isSelected = selected.includes(ind.indicator_id);
          const disabled = !isSelected && selected.length >= REQUIRED_ITEMS;
          return (
            <label key={ind.indicator_id}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                isSelected ? "border-[#00694E] bg-[#E6F4F0] dark:bg-[#00694E]/10" : "border-gray-200 dark:border-gray-700"
              } ${disabled ? "opacity-40 cursor-not-allowed" : "hover:bg-gray-50 dark:hover:bg-gray-700/40"}`}>
              <input type="checkbox" checked={isSelected} disabled={disabled}
                onChange={() => toggleIndicator(ind.indicator_id)}
                className="mt-1 accent-[#00694E]" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm text-gray-900 dark:text-white">{ind.name}</span>
                  {ind.original_score != null && (ind.original_score === 1 || ind.original_score === 2) && (
                    <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                      Nota {ind.original_score}
                    </span>
                  )}
                </div>
                {ind.description && <p className="text-xs text-gray-500 mt-0.5">{ind.description}</p>}
              </div>
            </label>
          );
        })}
      </div>

      {selected.length > 0 && (
        <div className="space-y-4">
          {selectedIndicators.map(ind => (
            <div key={ind.indicator_id} className="bg-white dark:bg-gray-800 rounded-2xl p-4 sm:p-6 shadow border">
              <h3 className="font-bold text-gray-900 dark:text-white mb-3">{ind.name}</h3>
              <div className="space-y-3">
                {FIELD_LABELS.map(fl => (
                  <div key={fl.key}>
                    <label className="block text-xs font-semibold text-gray-500 mb-1">{fl.label}</label>
                    <textarea
                      value={(fieldsByIndicator[ind.indicator_id] || EMPTY_ITEM)[fl.key]}
                      onChange={e => updateField(ind.indicator_id, fl.key, e.target.value)}
                      placeholder={fl.placeholder}
                      rows={2}
                      className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-3 py-2 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]"
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-2xl p-4 sm:p-6 shadow border">
        <h3 className="font-bold text-gray-900 dark:text-white mb-1">Combinados de acompanhamento</h3>
        <label className="block text-xs font-semibold text-gray-500 mb-1 mt-2">Frequência de alinhamento</label>
        <textarea
          value={frequenciaAlinhamento}
          onChange={e => setFrequenciaAlinhamento(e.target.value)}
          placeholder="Ex: reuniões quinzenais de 30min para acompanhar o progresso..."
          rows={3}
          className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-3 py-2 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]"
        />
      </div>

      {formError && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3">
          <p className="text-sm text-red-700 dark:text-red-300">{formError}</p>
        </div>
      )}

      <button
        onClick={validateAndOpenReview}
        className="w-full py-3.5 bg-[#00694E] hover:bg-[#004F3A] text-white font-bold rounded-xl transition-all"
      >
        Revisar e Enviar Plano de Ação
      </button>

      {showReview && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 sm:p-7 max-w-lg w-full shadow-2xl my-8">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-1">Revise antes de enviar</h3>
            <p className="text-sm text-gray-500 mb-4">
              Confira as informações abaixo. Depois de confirmado, o plano não poderá mais ser editado.
            </p>
            <div className="space-y-3 max-h-80 overflow-y-auto pr-1 mb-4">
              {selectedIndicators.map(ind => {
                const f = fieldsByIndicator[ind.indicator_id] || EMPTY_ITEM;
                return (
                  <div key={ind.indicator_id} className="border border-gray-100 dark:border-gray-700 rounded-lg p-3">
                    <p className="font-semibold text-sm text-gray-900 dark:text-white mb-1">{ind.name}</p>
                    {FIELD_LABELS.map(fl => (
                      <p key={fl.key} className="text-xs text-gray-500 mt-1">
                        <strong className="text-gray-700 dark:text-gray-300">{fl.label}:</strong> {f[fl.key]}
                      </p>
                    ))}
                  </div>
                );
              })}
              <div className="border border-gray-100 dark:border-gray-700 rounded-lg p-3">
                <p className="font-semibold text-sm text-gray-900 dark:text-white mb-1">Combinados de acompanhamento</p>
                <p className="text-xs text-gray-500">{frequenciaAlinhamento}</p>
              </div>
            </div>
            {submitError && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3 mb-4">
                <p className="text-sm text-red-700 dark:text-red-300">{submitError}</p>
              </div>
            )}
            <div className="flex flex-col gap-3">
              <button
                onClick={handleConfirmSubmit}
                disabled={submitting}
                className="w-full py-3.5 bg-[#00694E] hover:bg-[#004F3A] text-white font-bold rounded-xl transition-all disabled:opacity-60"
              >
                {submitting ? "Enviando..." : "Confirmar e Enviar"}
              </button>
              <button
                onClick={() => setShowReview(false)}
                disabled={submitting}
                className="w-full py-2 text-sm text-gray-400 hover:text-gray-600"
              >
                Voltar e editar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
