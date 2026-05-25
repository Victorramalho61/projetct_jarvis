import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

const SCORE_MAP: Record<number, { label: string; desc: string; color: string }> = {
  4: { label: "SE",  desc: "Supera o Esperado",              color: "bg-emerald-100 text-emerald-700 border-emerald-300" },
  3: { label: "AE",  desc: "Atende o Esperado",              color: "bg-blue-100 text-blue-700 border-blue-300" },
  2: { label: "APE", desc: "Atende Parcialmente o Esperado", color: "bg-amber-100 text-amber-700 border-amber-300" },
  1: { label: "NAE", desc: "Não Atende o Esperado",          color: "bg-red-100 text-red-700 border-red-300" },
};

const SOCIALS = [
  { label: "LinkedIn",  href: "https://www.linkedin.com/company/grupo-voetur/" },
  { label: "Instagram", href: "https://www.instagram.com/grupovoetur/" },
  { label: "Facebook",  href: "https://www.facebook.com/GrupoVoetur" },
  { label: "YouTube",   href: "https://www.youtube.com/@GrupoVoetur-br" },
];

const HR_EMAIL = "rh@voetur.com.br";

function isVTCCompany(name?: string) {
  const n = name?.toLowerCase() || "";
  return n.includes("vtc") || n.includes("logística") || n.includes("logistica");
}

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

function CompanyLogo({ companyName }: { companyName?: string }) {
  const vtc = isVTCCompany(companyName);
  return (
    <img
      src={vtc
        ? "https://www.vtclog.com.br/wp-content/uploads/logo-vtclog.png"
        : "https://voeturviagens.com.br/wp-content/uploads/2025/07/voetur-viagens-logo-site.png"}
      alt={vtc ? "VTC Operadora Logística" : "Voetur Viagens"}
      className="h-9 max-w-[200px] object-contain brightness-0 invert"
      onError={(e) => { e.currentTarget.style.display = "none"; }}
    />
  );
}

function GrupoVoeturFooter({ vtc }: { vtc: boolean }) {
  return (
    <footer className="mt-6 border-t border-gray-200 dark:border-gray-800 pt-8 pb-10 text-center">
      <p className="text-sm font-bold tracking-widest text-gray-700 dark:text-gray-300 uppercase mb-0.5">
        Grupo Voetur
      </p>
      <p className="text-xs text-gray-400 italic mb-5">Movimentamos o melhor do Brasil</p>

      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 mb-4">
        {SOCIALS.map((s, i) => (
          <span key={s.label} className="flex items-center gap-x-4">
            <a
              href={s.href}
              target="_blank"
              rel="noopener noreferrer"
              className={`text-xs transition-colors ${vtc ? "text-gray-500 hover:text-teal-700" : "text-gray-500 hover:text-[#003D73]"}`}
            >
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
        <a
          href={`mailto:${HR_EMAIL}`}
          className={`hover:underline ${vtc ? "text-teal-700 dark:text-teal-400" : "text-[#003D73] dark:text-blue-400"}`}
        >
          {HR_EMAIL}
        </a>
      </p>
      <p className="text-xs text-gray-400">Voetur Viagens · VTC Operadora Logística</p>
      <p className="text-xs text-gray-300 dark:text-gray-600 mt-1">Sistema Jarvis © 2025</p>
    </footer>
  );
}

export default function PublicCienciaPage() {
  const { token } = useParams<{ token: string }>();
  const [state,          setState]          = useState<"loading" | "error" | "info" | "acknowledged">("loading");
  const [errorMsg,       setErrorMsg]       = useState("");
  const [data,           setData]           = useState<any>(null);
  const [showModal,      setShowModal]      = useState(false);
  const [submitting,     setSubmitting]     = useState(false);
  const [acknowledgedAt, setAcknowledgedAt] = useState("");

  useEffect(() => {
    if (!token) { setState("error"); setErrorMsg("Link inválido."); return; }
    fetch(`/api/performance/public/ciencia/${token}`)
      .then(r => r.json().then(j => ({ ok: r.ok, data: j })))
      .then(({ ok, data }) => {
        if (!ok) { setState("error"); setErrorMsg(data.detail || "Link inválido."); return; }
        if (data.already_acknowledged) {
          setState("acknowledged");
          setAcknowledgedAt(data.acknowledged_at || "");
          setData(data);
        } else {
          setState("info");
          setData(data);
        }
      })
      .catch(() => { setState("error"); setErrorMsg("Erro de conexão."); });
  }, [token]);

  async function handleCiencia(feedbackReceived: boolean) {
    setSubmitting(true);
    try {
      const res  = await fetch(`/api/performance/public/ciencia/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback_received: feedbackReceived }),
      });
      const json = await res.json();
      if (!res.ok) { setErrorMsg(json.detail || "Erro."); setSubmitting(false); return; }
      setShowModal(false);
      setAcknowledgedAt(json.acknowledged_at || "");
      setState("acknowledged");
    } catch {
      setErrorMsg("Erro de conexão."); setSubmitting(false);
    }
  }

  function formatDate(iso: string) {
    try {
      return new Date(iso).toLocaleString("pt-BR", {
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    } catch { return iso; }
  }

  const vtc         = isVTCCompany(data?.company_name);
  const primaryBg   = vtc ? "bg-teal-800"   : "bg-[#003D73]";
  const primaryText = vtc ? "text-teal-800"  : "text-[#003D73]";
  const primaryBorder = vtc ? "border-teal-600" : "border-[#003D73]";

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950">

      {/* ── Header ── */}
      <header className={`${primaryBg} shadow-lg`}>
        <div className="h-1.5 bg-gradient-to-r from-yellow-500 via-yellow-300 to-yellow-500" />
        <div className="max-w-2xl mx-auto px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CompanyLogo companyName={data?.company_name} />
            <span className="text-white/60 text-xs hidden sm:block">| Grupo Voetur</span>
          </div>
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
            <div className={`w-10 h-10 border-4 ${vtc ? "border-teal-600" : "border-[#003D73]"} border-t-transparent rounded-full animate-spin`} />
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
              <a href={`mailto:${HR_EMAIL}`} className={`hover:underline ${vtc ? "text-teal-700" : "text-[#003D73]"}`}>{HR_EMAIL}</a>
            </p>
          </div>
        )}

        {/* Ciência já registrada */}
        {state === "acknowledged" && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-10 text-center shadow border border-green-200">
            <div className="w-20 h-20 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-5">
              <svg className="w-10 h-10 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Ciência Registrada</h2>
            {acknowledgedAt && (
              <p className="text-gray-600 dark:text-gray-400 mb-1">
                Registrada em: <strong>{formatDate(acknowledgedAt)}</strong>
              </p>
            )}
            <p className="text-sm text-gray-500">Seu registro foi salvo com sucesso.</p>
          </div>
        )}

        {/* Resultado + botão de ciência */}
        {state === "info" && data && (
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

            {/* Avaliador */}
            <div className={`bg-white dark:bg-gray-800 rounded-2xl p-4 shadow border-l-4 ${primaryBorder} flex items-center gap-3`}>
              <div className={`w-9 h-9 rounded-full ${vtc ? "bg-teal-100" : "bg-blue-100"} flex items-center justify-center flex-shrink-0`}>
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
                  <div key={s.indicator_id} className="flex items-center justify-between px-5 py-3 gap-3">
                    <span className="text-sm text-gray-700 dark:text-gray-300 flex-1 min-w-0">{s.indicator_name}</span>
                    <ScoreBadge score={s.score} />
                  </div>
                ))}
              </div>
            </div>

            {/* Nota final */}
            <div className={`bg-white dark:bg-gray-800 rounded-2xl p-5 shadow border-2 ${primaryBorder} flex items-center justify-between`}>
              <span className="font-bold text-gray-900 dark:text-white text-lg">Nota Final (Média)</span>
              <div className="text-right">
                <span className={`text-3xl font-black ${primaryText} dark:text-blue-400`}>
                  {data.final_score?.toFixed(2)}
                </span>
                <span className="text-sm text-gray-400 ml-1">/ 4,00</span>
              </div>
            </div>

            <button
              onClick={() => setShowModal(true)}
              className="w-full py-4 bg-green-600 hover:bg-green-700 text-white font-bold text-lg rounded-2xl shadow-lg transition-all"
            >
              Dar Ciência da Avaliação
            </button>
          </div>
        )}
      </main>

      {/* ── Modal de Ciência ── */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-7 max-w-md w-full shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-10 h-10 rounded-xl ${vtc ? "bg-teal-600" : "bg-[#003D73]"} flex items-center justify-center`}>
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

      <GrupoVoeturFooter vtc={vtc} />
    </div>
  );
}
