import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

const SOCIALS = [
  { label: "LinkedIn",  href: "https://www.linkedin.com/company/grupo-voetur/" },
  { label: "Instagram", href: "https://www.instagram.com/grupovoetur/" },
  { label: "Facebook",  href: "https://www.facebook.com/GrupoVoetur" },
  { label: "YouTube",   href: "https://www.youtube.com/@GrupoVoetur-br" },
];

const HR_EMAIL = "rh@voetur.com.br";
const REQUIRED_ITEMS = 2;

function CompanyLogo() {
  return (
    <img
      src="https://grupovoetur.com.br/wp-content/uploads/2024/09/Grupo-Logo-Branco.svg"
      alt="Grupo Voetur"
      className="h-8 max-w-[200px] object-contain"
      onError={(e) => { e.currentTarget.style.display = "none"; }}
    />
  );
}

function GrupoVoeturFooter() {
  return (
    <footer className="mt-6 border-t border-gray-200 dark:border-gray-800 pt-8 pb-10 text-center">
      <img
        src="https://grupovoetur.com.br/wp-content/uploads/2024/09/Grupo-Logo-Verde.svg"
        alt="Grupo Voetur"
        className="h-7 mx-auto mb-2 object-contain"
        onError={(e) => { e.currentTarget.style.display = "none"; }}
      />
      <p className="text-xs text-gray-400 italic mb-5">Movimentamos o melhor do Brasil</p>
      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 mb-4">
        {SOCIALS.map((s, i) => (
          <span key={s.label} className="flex items-center gap-x-4">
            <a href={s.href} target="_blank" rel="noopener noreferrer"
              className="text-xs text-gray-500 hover:text-[#00694E] transition-colors">
              {s.label}
            </a>
            {i < SOCIALS.length - 1 && (
              <span className="text-gray-300 dark:text-gray-700 text-xs select-none">·</span>
            )}
          </span>
        ))}
      </div>
      <p className="text-xs text-gray-400 mb-1">
        Dúvidas?{" "}
        <a href={`mailto:${HR_EMAIL}`} className="text-[#00694E] hover:underline">
          {HR_EMAIL}
        </a>
      </p>
      <p className="text-xs text-gray-300 dark:text-gray-600 mt-1">Sistema Jarvis &copy; 2026 — Grupo Voetur</p>
    </footer>
  );
}

interface IndicatorOption {
  indicator_id: string;
  name: string;
  description: string;
  original_score: number | null;
}

interface ItemFields {
  situacao_observada: string;
  meta_esperada: string;
  acoes: string;
  responsavel_acompanhamento: string;
  como_sera_verificado: string;
}

const EMPTY_ITEM: ItemFields = {
  situacao_observada: "", meta_esperada: "", acoes: "",
  responsavel_acompanhamento: "", como_sera_verificado: "",
};

const FIELD_LABELS: { key: keyof ItemFields; label: string; placeholder: string }[] = [
  { key: "situacao_observada", label: "Situação observada", placeholder: "Descreva o que foi observado nessa competência..." },
  { key: "meta_esperada", label: "Meta esperada / Objetivo", placeholder: "Qual o resultado esperado ao final do acompanhamento?" },
  { key: "acoes", label: "Ações — O quê", placeholder: "Quais ações concretas serão tomadas?" },
  { key: "responsavel_acompanhamento", label: "Responsável pelo acompanhamento", placeholder: "Quem vai acompanhar essa ação?" },
  { key: "como_sera_verificado", label: "Como será verificado", placeholder: "Como o progresso será medido/verificado?" },
];

export default function PublicActionPlanPage() {
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<"loading" | "error" | "form" | "done">("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [data, setData] = useState<any>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [fieldsByIndicator, setFieldsByIndicator] = useState<Record<string, ItemFields>>({});
  const [frequenciaAlinhamento, setFrequenciaAlinhamento] = useState("");
  const [showReview, setShowReview] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [formError, setFormError] = useState("");

  useEffect(() => {
    if (!token) { setState("error"); setErrorMsg("Link inválido."); return; }
    fetch(`/api/performance/public/action-plans/inicial/${token}`)
      .then(r => r.json().then(j => ({ ok: r.ok, data: j })))
      .then(({ ok, data }) => {
        if (!ok) { setState("error"); setErrorMsg(data.detail || "Link inválido."); return; }
        setData(data);
        setState("form");
      })
      .catch(() => { setState("error"); setErrorMsg("Erro de conexão."); });
  }, [token]);

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
      const res = await fetch(`/api/performance/public/action-plans/inicial/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: selected.map(id => ({ indicator_id: id, ...fieldsByIndicator[id] })),
          frequencia_alinhamento: frequenciaAlinhamento.trim(),
        }),
      });
      const json = await res.json();
      if (!res.ok) { setSubmitError(json.detail || "Erro ao enviar."); setSubmitting(false); return; }
      setShowReview(false);
      setState("done");
    } catch {
      setSubmitError("Erro de conexão.");
    } finally {
      setSubmitting(false);
    }
  }

  const indicators: IndicatorOption[] = data?.indicators || [];
  const selectedIndicators = indicators.filter(i => selected.includes(i.indicator_id));

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950">
      <header className="bg-[#00694E] shadow-lg">
        <div className="h-1 bg-[#004F3A]" />
        <div className="max-w-2xl mx-auto px-5 py-4 flex items-center justify-between">
          <CompanyLogo />
          <div className="text-right">
            <div className="text-white font-semibold text-sm">Sistema Jarvis</div>
            <div className="text-white/60 text-xs">Plano de Ação de Feedback</div>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">
        {state === "loading" && (
          <div className="flex justify-center py-20">
            <div className="w-10 h-10 border-4 border-[#00694E] border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {state === "error" && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-10 text-center shadow border">
            <div className="text-5xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold mb-2">Link Inválido</h2>
            <p className="text-gray-600 dark:text-gray-400 mb-3">{errorMsg}</p>
            <p className="text-sm text-gray-500">
              Em caso de dúvidas:{" "}
              <a href={`mailto:${HR_EMAIL}`} className="hover:underline text-[#00694E]">{HR_EMAIL}</a>
            </p>
          </div>
        )}

        {state === "done" && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-10 text-center shadow border">
            <div className="text-5xl mb-4">✅</div>
            <h2 className="text-xl font-bold mb-2">Plano de Ação Enviado</h2>
            <p className="text-gray-600 dark:text-gray-400">
              Obrigado! O RH vai acompanhar o andamento a cada 3 meses e você receberá um novo
              e-mail em cada checkpoint para atualizar o progresso. O colaborador também receberá
              um e-mail para tomar ciência deste plano.
            </p>
          </div>
        )}

        {state === "form" && data && (
          <div className="space-y-5">
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 sm:p-8 shadow border">
              <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-1">
                Plano de Ação — {data.employee_name}
              </h2>
              <p className="text-sm text-gray-500 mb-5">
                Ciclo {data.cycle_name}{data.company_name ? ` · ${data.company_name}` : ""}
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm mb-2">
                <div><span className="text-gray-400">Colaborador(a):</span> <span className="font-medium text-gray-800 dark:text-gray-200">{data.employee_name}</span></div>
                <div><span className="text-gray-400">Cargo / Área:</span> <span className="font-medium text-gray-800 dark:text-gray-200">{data.employee_cargo || "—"}</span></div>
                <div><span className="text-gray-400">Gestor(a) responsável:</span> <span className="font-medium text-gray-800 dark:text-gray-200">{data.manager_name || "—"}</span></div>
                <div><span className="text-gray-400">Período avaliado:</span> <span className="font-medium text-gray-800 dark:text-gray-200">
                  {data.period_start && data.period_end ? `${data.period_start} a ${data.period_end}` : "—"}
                </span></div>
                <div><span className="text-gray-400">Data de elaboração:</span> <span className="font-medium text-gray-800 dark:text-gray-200">hoje</span></div>
                <div><span className="text-gray-400">Data de reavaliação:</span> <span className="font-medium text-gray-800 dark:text-gray-200">{data.next_review_date || "—"}</span></div>
              </div>
            </div>

            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4">
              <p className="text-sm text-amber-800 dark:text-amber-200">
                Escolha exatamente <strong>{REQUIRED_ITEMS} competências prioritárias</strong> para o
                plano de desenvolvimento de {data.employee_name} nos próximos 12 meses. Competências em
                que houve nota 1 ou 2 nesta avaliação estão marcadas — mas você pode escolher quaisquer
                {" "}{REQUIRED_ITEMS} do catálogo.
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
          </div>
        )}
      </main>

      {/* Modal de revisão — dupla confirmação, no lugar da assinatura */}
      {showReview && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 sm:p-7 max-w-lg w-full shadow-2xl my-8">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-1">Revise antes de enviar</h3>
            <p className="text-sm text-gray-500 mb-4">
              Confira as informações abaixo. Depois de confirmado, o plano não poderá mais ser editado
              por este link.
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

      <GrupoVoeturFooter />
    </div>
  );
}
