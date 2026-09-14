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

function PlanSummary({ data }: { data: any }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 sm:p-8 shadow border">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-1">
        Plano de Ação — {data.employee_name}
      </h2>
      <p className="text-sm text-gray-500 mb-5">
        Ciclo {data.cycle_name} · Gestor(a): {data.manager_name}
      </p>
      <div className="space-y-4">
        {(data.items || []).map((it: any, i: number) => (
          <div key={i} className="border border-gray-100 dark:border-gray-700 rounded-lg p-4">
            <p className="font-semibold text-sm text-gray-900 dark:text-white mb-2">{it.indicator_name}</p>
            {[
              ["Situação observada", it.situacao_observada],
              ["Meta esperada / Objetivo", it.meta_esperada],
              ["Ações", it.acoes],
              ["Responsável pelo acompanhamento", it.responsavel_acompanhamento],
              ["Como será verificado", it.como_sera_verificado],
            ].map(([label, value]) => value && (
              <p key={label as string} className="text-xs text-gray-500 mt-1">
                <strong className="text-gray-700 dark:text-gray-300">{label}:</strong> {value as string}
              </p>
            ))}
          </div>
        ))}
        {data.frequencia_alinhamento && (
          <div className="border border-gray-100 dark:border-gray-700 rounded-lg p-4">
            <p className="font-semibold text-sm text-gray-900 dark:text-white mb-1">Combinados de acompanhamento</p>
            <p className="text-xs text-gray-500">{data.frequencia_alinhamento}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function PublicActionPlanCienciaPage() {
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<"loading" | "error" | "info">("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [data, setData] = useState<any>(null);
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    if (!token) { setState("error"); setErrorMsg("Link inválido."); return; }
    fetch(`/api/performance/public/action-plans/ciencia/${token}`)
      .then(r => r.json().then(j => ({ ok: r.ok, data: j })))
      .then(({ ok, data }) => {
        if (!ok) { setState("error"); setErrorMsg(data.detail || "Link inválido."); return; }
        setState("info");
        setData(data);
      })
      .catch(() => { setState("error"); setErrorMsg("Erro de conexão."); });
  }, [token]);

  async function handleConfirm() {
    setSubmitting(true);
    setSubmitError("");
    try {
      const res = await fetch(`/api/performance/public/action-plans/ciencia/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const json = await res.json();
      if (!res.ok) { setSubmitError(json.detail || "Erro."); setSubmitting(false); return; }
      setShowModal(false);
      setData((prev: any) => ({ ...prev, already_acknowledged: true, acknowledged_at: json.acknowledged_at }));
    } catch {
      setSubmitError("Erro de conexão."); setSubmitting(false);
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
            <div className="text-white/60 text-xs">Ciência do Plano de Ação</div>
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

        {state === "info" && data && (
          <div className="space-y-4">
            {data.already_acknowledged ? (
              <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl p-4 flex items-center gap-3">
                <span className="text-2xl">✅</span>
                <p className="text-sm text-green-800 dark:text-green-200">
                  Ciência já registrada{data.acknowledged_at ? ` em ${new Date(data.acknowledged_at).toLocaleString("pt-BR")}` : ""}.
                </p>
              </div>
            ) : (
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4">
                <p className="text-sm text-amber-800 dark:text-amber-200">
                  Confira abaixo o seu plano de ação e confirme que está ciente.
                </p>
              </div>
            )}

            <PlanSummary data={data} />

            {!data.already_acknowledged && (
              <button
                onClick={() => setShowModal(true)}
                className="w-full py-3.5 bg-[#00694E] hover:bg-[#004F3A] text-white font-bold rounded-xl transition-all"
              >
                Confirmar Ciência
              </button>
            )}
          </div>
        )}
      </main>

      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-7 max-w-md w-full shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-[#00694E] flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">Confirmação de Ciência</h3>
            </div>

            <p className="text-sm text-gray-600 dark:text-gray-400 mb-5 leading-relaxed">
              Declaro que tomei ciência do meu plano de ação, das competências prioritárias e dos
              combinados de acompanhamento definidos com {data?.manager_name}.
            </p>

            {submitError && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3 mb-4">
                <p className="text-sm text-red-700 dark:text-red-300">{submitError}</p>
              </div>
            )}

            <div className="flex flex-col gap-3">
              <button
                onClick={handleConfirm}
                disabled={submitting}
                className="w-full py-3.5 bg-green-600 hover:bg-green-700 text-white font-bold rounded-xl transition-all disabled:opacity-60"
              >
                {submitting ? "Enviando..." : "Sim, estou ciente"}
              </button>
              <button
                onClick={() => setShowModal(false)}
                disabled={submitting}
                className="w-full py-2 text-sm text-gray-400 hover:text-gray-600"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      <GrupoVoeturFooter />
    </div>
  );
}
