import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

const SCORE_MAP: Record<number, { label: string; desc: string; color: string }> = {
  5: { label: "EE",  desc: "Excede as Expectativas",              color: "bg-purple-100 text-purple-700 border-purple-300 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-700" },
  4: { label: "SE",  desc: "Supera as Expectativas",              color: "bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-700" },
  3: { label: "AE",  desc: "Atende as Expectativas",              color: "bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700" },
  2: { label: "APE", desc: "Atende Parcialmente as Expectativas", color: "bg-amber-100 text-amber-700 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700" },
  1: { label: "NAE", desc: "Não Atende às Expectativas",          color: "bg-red-100 text-red-700 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700" },
};

const SOCIALS = [
  { label: "LinkedIn",  href: "https://www.linkedin.com/company/grupo-voetur/" },
  { label: "Instagram", href: "https://www.instagram.com/grupovoetur/" },
  { label: "Facebook",  href: "https://www.facebook.com/GrupoVoetur" },
  { label: "YouTube",   href: "https://www.youtube.com/@GrupoVoetur-br" },
];

const HR_EMAIL = "rh@voetur.com.br";

// Grupo Voetur — paleta única
const BRAND    = "#00694E";
const BRAND_DARK = "#004F3A";

function ScoreBadge({ score }: { score: number }) {
  const rounded = Math.round(score);
  const s = SCORE_MAP[rounded];
  if (!s)
    return (
      <span className="px-2 py-1 rounded border text-xs font-semibold bg-gray-100 text-gray-700 border-gray-300">
        {score}
      </span>
    );
  return (
    <span className={`px-3 py-1 rounded-full border text-xs font-bold ${s.color}`}>
      {s.label} <span className="font-normal">— {s.desc}</span>
    </span>
  );
}

function avgLabel(avg: number): string {
  if (avg >= 4.5) return "Excede as Expectativas";
  if (avg >= 3.5) return "Supera as Expectativas";
  if (avg >= 2.5) return "Atende as Expectativas";
  if (avg >= 1.5) return "Atende Parcialmente";
  return "Não Atende às Expectativas";
}

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

// ── Painel de resultado (reutilizado em info + acknowledged) ──────────────────
function ResultPanel({
  data, vtc, primaryBg, primaryText, primaryBorder, acknowledged, acknowledgedAt, onOpenModal,
}: {
  data: any; vtc: boolean; primaryBg: string; primaryText: string; primaryBorder: string;
  acknowledged: boolean; acknowledgedAt?: string; onOpenModal?: () => void;
}) {
  function formatDate(iso: string) {
    try { return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
    catch { return iso; }
  }

  return (
    <div className="space-y-4">
      {/* Banner */}
      <div className={`${primaryBg} text-white rounded-2xl shadow-lg overflow-hidden`}>
        <div className="h-1 bg-gradient-to-r from-yellow-500 via-yellow-300 to-yellow-500" />
        <div className="p-6">
          <p className="text-white/70 text-xs font-semibold uppercase tracking-widest mb-1">
            Resultado da Avaliação de Desempenho
          </p>
          <h1 className="text-xl font-bold mb-1">{data.cycle_name}</h1>
          <p className="text-white/80 text-sm mt-2">
            Olá, <strong>{data.employee_name}</strong>
          </p>
        </div>
      </div>

      {/* Ciência já registrada — banner informativo (não bloqueia visualização) */}
      {acknowledged && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl p-4 flex items-center gap-3">
          <svg className="w-5 h-5 text-green-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="text-sm font-semibold text-green-800 dark:text-green-200">Ciência já registrada</p>
            {acknowledgedAt && (
              <p className="text-xs text-green-600 dark:text-green-400 mt-0.5">
                em {formatDate(acknowledgedAt)}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Avaliador */}
      <div className={`bg-white dark:bg-gray-800 rounded-2xl p-4 shadow border-l-4 ${primaryBorder} flex items-center gap-3`}>
        <div className="w-9 h-9 rounded-full bg-[#E6F4F0] dark:bg-[#00694E]/20 flex items-center justify-center flex-shrink-0">
          <svg className={`w-5 h-5 ${primaryText}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        </div>
        <div>
          <p className="text-xs text-gray-500">Avaliado por</p>
          <p className="font-semibold text-gray-900 dark:text-white">{data.evaluator_name}</p>
        </div>
      </div>

      {/* Notas por indicador */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow border border-gray-100 dark:border-gray-700 overflow-hidden">
        <div className={`${primaryBg} px-5 py-3`}>
          <h3 className="text-white font-bold text-sm uppercase tracking-wide">Notas por Indicador</h3>
        </div>
        <div className="divide-y divide-gray-50 dark:divide-gray-700">
          {data.indicator_scores?.map((s: any) => (
            <div key={s.indicator_id}>
              <div className="flex items-center justify-between px-5 py-3 gap-3">
                <span className="text-sm text-gray-700 dark:text-gray-300 flex-1 min-w-0">{s.indicator_name}</span>
                <ScoreBadge score={s.score} />
              </div>
              {/* Justificativa para notas extremas */}
              {s.justification && (
                <div className="px-5 pb-3 -mt-1">
                  <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg px-3 py-2 border-l-2 border-gray-300 dark:border-gray-600">
                    <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-0.5">
                      Justificativa do gestor
                    </p>
                    <p className="text-xs text-gray-600 dark:text-gray-400 italic leading-relaxed">
                      "{s.justification}"
                    </p>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Nota final */}
      <div className={`bg-white dark:bg-gray-800 rounded-2xl p-5 shadow border-2 ${primaryBorder} flex items-center justify-between`}>
        <div>
          <span className="font-bold text-gray-900 dark:text-white text-lg">Nota Final</span>
          <p className="text-xs text-gray-400 mt-0.5">{avgLabel(data.final_score ?? 0)}</p>
        </div>
        <div className="text-right">
          <span className={`text-3xl font-black ${primaryText} dark:text-blue-400`}>
            {data.final_score?.toFixed(2)}
          </span>
          <span className="text-sm text-gray-400 ml-1">/ 5,00</span>
        </div>
      </div>

      {/* Observações do gestor */}
      {data.observations && (
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow border border-gray-100 dark:border-gray-700 overflow-hidden">
          <div className="bg-gray-50 dark:bg-gray-700/50 px-5 py-3">
            <h3 className="text-sm font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
              📝 Observações do Gestor
            </h3>
          </div>
          <div className="px-5 py-4">
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
              {data.observations}
            </p>
          </div>
        </div>
      )}

      {/* Botão de ciência — apenas se ainda não registrou */}
      {!acknowledged && onOpenModal && (
        <button
          onClick={onOpenModal}
          className="w-full py-4 bg-green-600 hover:bg-green-700 text-white font-bold text-lg rounded-2xl shadow-lg transition-all"
        >
          ✓ Dar Ciência da Avaliação
        </button>
      )}

      {/* Se já confirmou — botão desativado para clareza */}
      {acknowledged && (
        <div className="w-full py-4 bg-gray-100 dark:bg-gray-700/50 text-gray-400 dark:text-gray-500 font-semibold text-base rounded-2xl text-center border border-gray-200 dark:border-gray-700">
          ✓ Ciência registrada — obrigado(a)
        </div>
      )}
    </div>
  );
}

export default function PublicCienciaPage() {
  const { token } = useParams<{ token: string }>();
  const [state,          setState]          = useState<"loading" | "error" | "info">("loading");
  const [errorMsg,       setErrorMsg]       = useState("");
  const [data,           setData]           = useState<any>(null);
  const [showModal,      setShowModal]      = useState(false);
  const [submitting,     setSubmitting]     = useState(false);
  const [submitError,    setSubmitError]    = useState("");

  useEffect(() => {
    if (!token) { setState("error"); setErrorMsg("Link inválido."); return; }
    fetch(`/api/performance/public/ciencia/${token}`)
      .then(r => r.json().then(j => ({ ok: r.ok, data: j })))
      .then(({ ok, data }) => {
        if (!ok) { setState("error"); setErrorMsg(data.detail || "Link inválido."); return; }
        setState("info");
        setData(data);
      })
      .catch(() => { setState("error"); setErrorMsg("Erro de conexão."); });
  }, [token]);

  async function handleCiencia(feedbackReceived: boolean) {
    setSubmitting(true);
    setSubmitError("");
    try {
      const res  = await fetch(`/api/performance/public/ciencia/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback_received: feedbackReceived }),
      });
      const json = await res.json();
      if (!res.ok) { setSubmitError(json.detail || "Erro."); setSubmitting(false); return; }
      setShowModal(false);
      // Atualiza data com acknowledged e acknowledged_at para mostrar o banner
      setData((prev: any) => ({
        ...prev,
        already_acknowledged: true,
        acknowledged_at: json.acknowledged_at || new Date().toISOString(),
      }));
    } catch {
      setSubmitError("Erro de conexão."); setSubmitting(false);
    }
  }

  // Grupo Voetur — paleta única
  const primaryBg     = "bg-[#00694E]";
  const primaryText   = "text-[#00694E]";
  const primaryBorder = "border-[#00694E]";

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950">

      {/* ── Header ── */}
      <header className={`${primaryBg} shadow-lg`}>
        <div className="h-1 bg-[#004F3A]" />
        <div className="max-w-2xl mx-auto px-5 py-4 flex items-center justify-between">
          <CompanyLogo />
          <div className="text-right">
            <div className="text-white font-semibold text-sm">Sistema Jarvis</div>
            <div className="text-white/60 text-xs">Resultado da Avaliação</div>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">

        {/* Loading */}
        {state === "loading" && (
          <div className="flex justify-center py-20">
            <div className="w-10 h-10 border-4 border-[#00694E] border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {/* Erro */}
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

        {/* Resultado — acessível a qualquer momento, ciência ou não */}
        {state === "info" && data && (
          <>
            {submitError && (
              <div className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3">
                <p className="text-sm text-red-700 dark:text-red-300">{submitError}</p>
              </div>
            )}
            <ResultPanel
              data={data}
              vtc={vtc}
              primaryBg={primaryBg}
              primaryText={primaryText}
              primaryBorder={primaryBorder}
              acknowledged={data.already_acknowledged}
              acknowledgedAt={data.acknowledged_at}
              onOpenModal={() => setShowModal(true)}
            />
          </>
        )}
      </main>

      {/* ── Modal de Ciência ── */}
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

            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 leading-relaxed">
              Confirmo que estou ciente da minha avaliação de desempenho atribuída por{" "}
              <strong>{data?.evaluator_name}</strong> no ciclo{" "}
              <strong>{data?.cycle_name}</strong>.
            </p>

            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 mb-5">
              <p className="text-sm font-semibold text-amber-800 dark:text-amber-200">
                Você recebeu feedback presencial do gestor explicando os motivos das notas?
              </p>
            </div>

            {submitError && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3 mb-4">
                <p className="text-sm text-red-700 dark:text-red-300">{submitError}</p>
              </div>
            )}

            <div className="flex flex-col gap-3">
              <button
                onClick={() => handleCiencia(true)}
                disabled={submitting}
                className="w-full py-3.5 bg-green-600 hover:bg-green-700 text-white font-bold rounded-xl transition-all disabled:opacity-60"
              >
                Sim, recebi feedback e estou ciente
              </button>
              <button
                onClick={() => handleCiencia(false)}
                disabled={submitting}
                className="w-full py-3.5 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 font-semibold rounded-xl transition-all disabled:opacity-60"
              >
                Ainda não recebi feedback
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
