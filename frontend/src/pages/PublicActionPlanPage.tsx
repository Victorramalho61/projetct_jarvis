import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

const SOCIALS = [
  { label: "LinkedIn",  href: "https://www.linkedin.com/company/grupo-voetur/" },
  { label: "Instagram", href: "https://www.instagram.com/grupovoetur/" },
  { label: "Facebook",  href: "https://www.facebook.com/GrupoVoetur" },
  { label: "YouTube",   href: "https://www.youtube.com/@GrupoVoetur-br" },
];

const HR_EMAIL = "rh@voetur.com.br";

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

interface PlanItem {
  item_id: string;
  indicator_name: string;
  indicator_description: string;
  original_score: number;
}

export default function PublicActionPlanPage() {
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<"loading" | "error" | "form" | "done">("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [data, setData] = useState<any>(null);
  const [planTexts, setPlanTexts] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

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

  async function handleSubmit() {
    const items: PlanItem[] = data?.items || [];
    const missing = items.some(i => !(planTexts[i.item_id] || "").trim());
    if (missing) {
      setSubmitError("Preencha o plano de ação de todas as competências antes de enviar.");
      return;
    }
    setSubmitting(true);
    setSubmitError("");
    try {
      const res = await fetch(`/api/performance/public/action-plans/inicial/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: items.map(i => ({ item_id: i.item_id, plan_text: planTexts[i.item_id] || "" })),
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
              e-mail em cada checkpoint para atualizar o progresso.
            </p>
          </div>
        )}

        {state === "form" && data && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 sm:p-8 shadow border">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-1">
              Plano de Ação — {data.employee_name}
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              Ciclo {data.cycle_name}{data.company_name ? ` · ${data.company_name}` : ""}
            </p>

            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 mb-6">
              <p className="text-sm text-amber-800 dark:text-amber-200">
                Nas competências abaixo, {data.employee_name} recebeu nota 1 ou 2 nesta avaliação de
                desempenho. Descreva o objetivo e as ações que serão desenvolvidas nos próximos 12
                meses para melhorar cada competência.
              </p>
            </div>

            <div className="space-y-5">
              {(data.items as PlanItem[]).map(item => (
                <div key={item.item_id} className="border border-gray-200 dark:border-gray-700 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-1">
                    <h3 className="font-semibold text-gray-900 dark:text-white">{item.indicator_name}</h3>
                    <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                      Nota {item.original_score}
                    </span>
                  </div>
                  {item.indicator_description && (
                    <p className="text-xs text-gray-500 mb-2">{item.indicator_description}</p>
                  )}
                  <textarea
                    value={planTexts[item.item_id] || ""}
                    onChange={e => setPlanTexts(p => ({ ...p, [item.item_id]: e.target.value }))}
                    placeholder="Descreva o objetivo e as ações de melhoria para esta competência..."
                    rows={4}
                    className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-3 py-2 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]"
                  />
                </div>
              ))}
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
              {submitting ? "Enviando..." : "Enviar Plano de Ação"}
            </button>
          </div>
        )}
      </main>

      <GrupoVoeturFooter />
    </div>
  );
}
