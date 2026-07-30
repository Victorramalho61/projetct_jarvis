import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

const SOCIALS = [
  { label: "LinkedIn",  href: "https://www.linkedin.com/company/grupo-voetur/" },
  { label: "Instagram", href: "https://www.instagram.com/grupovoetur/" },
  { label: "Facebook",  href: "https://www.facebook.com/GrupoVoetur" },
  { label: "YouTube",   href: "https://www.youtube.com/@GrupoVoetur-br" },
];

const HR_EMAIL = "rh@voetur.com.br";

const PHASE_PCT: Record<string, number> = { total: 25, parcial: 12.5, nao_atingida: 0 };
const RESULT_OPTIONS: { value: string; label: string }[] = [
  { value: "total", label: "Meta Total Atingida" },
  { value: "parcial", label: "Meta Parcialmente Atingida" },
  { value: "nao_atingida", label: "Meta Não Atingida" },
];

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

interface CheckinItem {
  item_id: string;
  indicator_name: string;
  plan_text: string;
  cumulative_pct_before: number;
}

interface Answer {
  result: string;
  justification: string;
  phase4_override_100: boolean | null;
  phase4_final_justification: string;
}

export default function PublicActionPlanCheckinPage() {
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<"loading" | "error" | "form" | "done">("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [data, setData] = useState<any>(null);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    if (!token) { setState("error"); setErrorMsg("Link inválido."); return; }
    fetch(`/api/performance/public/action-plans/checkin/${token}`)
      .then(r => r.json().then(j => ({ ok: r.ok, data: j })))
      .then(({ ok, data }) => {
        if (!ok) { setState("error"); setErrorMsg(data.detail || "Link inválido."); return; }
        setData(data);
        setState("form");
      })
      .catch(() => { setState("error"); setErrorMsg("Erro de conexão."); });
  }, [token]);

  function getAnswer(itemId: string): Answer {
    return answers[itemId] || { result: "", justification: "", phase4_override_100: null, phase4_final_justification: "" };
  }

  function setAnswer(itemId: string, patch: Partial<Answer>) {
    setAnswers(a => ({ ...a, [itemId]: { ...getAnswer(itemId), ...patch } }));
  }

  function tentativePct(item: CheckinItem): number {
    const ans = getAnswer(item.item_id);
    if (!ans.result) return item.cumulative_pct_before;
    return Math.min(100, item.cumulative_pct_before + (PHASE_PCT[ans.result] ?? 0));
  }

  async function handleSubmit() {
    const items: CheckinItem[] = data?.items || [];
    for (const item of items) {
      const ans = getAnswer(item.item_id);
      if (!ans.result) { setSubmitError("Informe o resultado de todas as competências."); return; }
      if (ans.result !== "total" && !ans.justification.trim()) {
        setSubmitError("Justificativa é obrigatória quando a meta não foi totalmente atingida.");
        return;
      }
      if (data.is_final_phase && tentativePct(item) < 100) {
        if (ans.phase4_override_100 === null) {
          setSubmitError("Nesta última fase, confirme se o colaborador atingiu 100% de cada competência ou justifique.");
          return;
        }
        if (!ans.phase4_final_justification.trim()) {
          setSubmitError("Justificativa final é obrigatória na última fase.");
          return;
        }
      }
    }

    setSubmitting(true);
    setSubmitError("");
    try {
      const res = await fetch(`/api/performance/public/action-plans/checkin/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: items.map(item => {
            const ans = getAnswer(item.item_id);
            const needsOverride = data.is_final_phase && tentativePct(item) < 100;
            return {
              item_id: item.item_id,
              result: ans.result,
              justification: ans.result !== "total" ? ans.justification : null,
              phase4_override_100: needsOverride ? ans.phase4_override_100 : null,
              phase4_final_justification: needsOverride ? ans.phase4_final_justification : null,
            };
          }),
        }),
      });
      const json = await res.json();
      if (!res.ok) { setSubmitError(json.detail || "Erro ao enviar."); setSubmitting(false); return; }
      setState("done");
    } catch {
      setSubmitError("Erro de conexão.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950">
      <header className="bg-[#00694E] shadow-lg">
        <div className="h-1 bg-[#004F3A]" />
        <div className="max-w-2xl mx-auto px-5 py-4 flex items-center justify-between">
          <CompanyLogo />
          <div className="text-right">
            <div className="text-white font-semibold text-sm">Sistema Jarvis</div>
            <div className="text-white/60 text-xs">Acompanhamento do Plano de Ação</div>
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
            <h2 className="text-xl font-bold mb-2">Acompanhamento Enviado</h2>
            <p className="text-gray-600 dark:text-gray-400">
              Obrigado! O RH já foi informado do andamento desta fase.
            </p>
          </div>
        )}

        {state === "form" && data && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 sm:p-8 shadow border">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-1">
              Acompanhamento — {data.employee_name}
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              Ciclo {data.cycle_name} · Fase {data.phase_number}/4
              {data.is_final_phase ? " (última fase)" : ""} · vencimento {data.due_date}
            </p>

            {data.is_final_phase && (
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 mb-6">
                <p className="text-sm text-amber-800 dark:text-amber-200">
                  Esta é a última fase do acompanhamento (12 meses). Se o percentual acumulado de
                  alguma competência não chegar a 100%, confirme se o colaborador atingiu a meta
                  mesmo assim, ou justifique o que faltou.
                </p>
              </div>
            )}

            <div className="space-y-6">
              {(data.items as CheckinItem[]).map(item => {
                const ans = getAnswer(item.item_id);
                const tentative = tentativePct(item);
                const showOverride = data.is_final_phase && !!ans.result && tentative < 100;
                return (
                  <div key={item.item_id} className="border border-gray-200 dark:border-gray-700 rounded-xl p-4">
                    <h3 className="font-semibold text-gray-900 dark:text-white">{item.indicator_name}</h3>
                    {item.plan_text && (
                      <p className="text-xs text-gray-500 mt-1 mb-2">Plano: {item.plan_text}</p>
                    )}
                    <p className="text-xs text-gray-400 mb-3">
                      Progresso acumulado até aqui: <strong>{item.cumulative_pct_before}%</strong>
                    </p>

                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Como está o andamento da melhoria dessa competência por parte do colaborador?
                    </p>
                    <div className="flex flex-col gap-2 mb-3">
                      {RESULT_OPTIONS.map(opt => (
                        <label key={opt.value} className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                          <input type="radio" name={`result-${item.item_id}`} value={opt.value}
                            checked={ans.result === opt.value}
                            onChange={() => setAnswer(item.item_id, { result: opt.value })} />
                          {opt.label}
                        </label>
                      ))}
                    </div>

                    {ans.result && ans.result !== "total" && (
                      <textarea
                        value={ans.justification}
                        onChange={e => setAnswer(item.item_id, { justification: e.target.value })}
                        placeholder="Justifique o motivo desta avaliação..."
                        rows={3}
                        className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-3 py-2 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E] mb-2"
                      />
                    )}

                    {showOverride && (
                      <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-3 mt-2">
                        <p className="text-sm font-medium text-amber-800 dark:text-amber-200 mb-2">
                          O colaborador atingiu 100% nesta competência?
                        </p>
                        <div className="flex gap-4 mb-2">
                          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                            <input type="radio" name={`override-${item.item_id}`}
                              checked={ans.phase4_override_100 === true}
                              onChange={() => setAnswer(item.item_id, { phase4_override_100: true })} />
                            Sim, considerar 100%
                          </label>
                          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                            <input type="radio" name={`override-${item.item_id}`}
                              checked={ans.phase4_override_100 === false}
                              onChange={() => setAnswer(item.item_id, { phase4_override_100: false })} />
                            Não, manter {tentative}%
                          </label>
                        </div>
                        <textarea
                          value={ans.phase4_final_justification}
                          onChange={e => setAnswer(item.item_id, { phase4_final_justification: e.target.value })}
                          placeholder="Justifique a avaliação final desta competência..."
                          rows={3}
                          className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]"
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {submitError && (
              <div className="mt-5 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3">
                <p className="text-sm text-red-700 dark:text-red-300">{submitError}</p>
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="mt-6 w-full py-3.5 bg-[#00694E] hover:bg-[#004F3A] text-white font-bold rounded-xl transition-all disabled:opacity-60"
            >
              {submitting ? "Enviando..." : "Enviar Acompanhamento"}
            </button>
          </div>
        )}
      </main>

      <GrupoVoeturFooter />
    </div>
  );
}
