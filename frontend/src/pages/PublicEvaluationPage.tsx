import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

type Indicator = { id: string; name: string; description?: string };
type Employee  = { id: string; name: string; matricula: string; cargo: string; hierarchy_level?: number };

const SCORE_OPTIONS = [
  { value: 5, label: "EE",  desc: "Excede as Expectativas",              color: "border-purple-500 bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300" },
  { value: 4, label: "SE",  desc: "Supera as Expectativas",              color: "border-emerald-500 bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" },
  { value: 3, label: "AE",  desc: "Atende as Expectativas",              color: "border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" },
  { value: 2, label: "APE", desc: "Atende Parcialmente as Expectativas", color: "border-amber-500 bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300" },
  { value: 1, label: "NAE", desc: "Não Atende às Expectativas",          color: "border-red-500 bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300" },
];

const SCORE_COLOR: Record<number, string> = {
  5: "text-purple-700 dark:text-purple-300",
  4: "text-emerald-700 dark:text-emerald-300",
  3: "text-blue-700 dark:text-blue-300",
  2: "text-amber-700 dark:text-amber-300",
  1: "text-red-700 dark:text-red-300",
};

const SOCIALS = [
  { label: "LinkedIn",  href: "https://www.linkedin.com/company/grupo-voetur/" },
  { label: "Instagram", href: "https://www.instagram.com/grupovoetur/" },
  { label: "Facebook",  href: "https://www.facebook.com/GrupoVoetur" },
  { label: "YouTube",   href: "https://www.youtube.com/@GrupoVoetur-br" },
];

const HR_EMAIL = "rh@voetur.com.br";

function isVTCCompany(name: string) {
  const n = name?.toLowerCase() || "";
  return n.includes("vtc") || n.includes("logística") || n.includes("logistica");
}

function CompanyLogo({ companyName }: { companyName: string }) {
  const vtc = isVTCCompany(companyName);
  return (
    <img
      src={vtc
        ? "https://www.vtclog.com.br/wp-content/uploads/logo-vtclog.png"
        : "https://voeturviagens.com.br/wp-content/uploads/2025/07/voetur-viagens-logo-site.png"}
      alt={vtc ? "VTC Operadora Logística" : "Voetur Viagens"}
      className="h-9 max-w-[200px] object-contain brightness-0 invert"
      onError={(e) => {
        const el = e.currentTarget;
        el.style.display = "none";
        (el.parentElement!.querySelector(".logo-fallback") as HTMLElement | null)?.classList.remove("hidden");
      }}
    />
  );
}

function GrupoVoeturFooter({ vtc }: { vtc: boolean }) {
  return (
    <footer className="mt-6 border-t border-gray-200 dark:border-gray-800 pt-8 pb-10 text-center">
      <p className="text-sm font-bold tracking-widest text-gray-700 dark:text-gray-300 uppercase mb-0.5">
        Grupo Voetur
      </p>
      <p className="text-xs text-gray-400 italic mb-5">
        Movimentamos o melhor do Brasil
      </p>
      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 mb-4">
        {SOCIALS.map((s, i) => (
          <span key={s.label} className="flex items-center gap-x-4">
            <a href={s.href} target="_blank" rel="noopener noreferrer"
              className={`text-xs transition-colors ${vtc ? "text-gray-500 hover:text-teal-700" : "text-gray-500 hover:text-[#003D73]"}`}>
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
        <a href={`mailto:${HR_EMAIL}`}
          className={`transition-colors hover:underline ${vtc ? "text-teal-700 dark:text-teal-400" : "text-[#003D73] dark:text-blue-400"}`}>
          {HR_EMAIL}
        </a>
      </p>
      <p className="text-xs text-gray-400">Voetur Viagens · VTC Operadora Logística</p>
      <p className="text-xs text-gray-300 dark:text-gray-600 mt-1">Sistema Jarvis © 2025</p>
    </footer>
  );
}

// ── Painel de resumo ──────────────────────────────────────────────────────────

function ScoreBadge({ value }: { value: number }) {
  const opt = SCORE_OPTIONS.find(o => o.value === value);
  if (!opt) return <span>{value}</span>;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold border ${opt.color}`}>
      {opt.label} — {opt.desc}
    </span>
  );
}

function avgColor(avg: number, vtc: boolean): string {
  if (avg >= 4.5) return "text-purple-700 dark:text-purple-300";
  if (avg >= 3.5) return vtc ? "text-teal-700 dark:text-teal-300" : "text-emerald-700 dark:text-emerald-300";
  if (avg >= 2.5) return "text-blue-700 dark:text-blue-300";
  if (avg >= 1.5) return "text-amber-700 dark:text-amber-300";
  return "text-red-700 dark:text-red-300";
}

function avgLabel(avg: number): string {
  if (avg >= 4.5) return "Excede as Expectativas";
  if (avg >= 3.5) return "Supera as Expectativas";
  if (avg >= 2.5) return "Atende as Expectativas";
  if (avg >= 1.5) return "Atende Parcialmente";
  return "Não Atende às Expectativas";
}

interface SummaryPanelProps {
  indicators: Indicator[];
  scores: Record<string, number>;
  vtc: boolean;
  primaryBg: string;
  primaryBtn: string;
  onAdjust: () => void;
  onConfirm: () => void;
  submitting: boolean;
  submitError: string;
  employeeName: string;
}

function SummaryPanel({
  indicators, scores, vtc, primaryBg, primaryBtn,
  onAdjust, onConfirm, submitting, submitError, employeeName,
}: SummaryPanelProps) {
  const total = indicators.reduce((sum, ind) => sum + (scores[ind.id] ?? 0), 0);
  const avg   = indicators.length > 0 ? total / indicators.length : 0;

  return (
    <div className="space-y-5 animate-in fade-in duration-300">
      {/* Header resumo */}
      <div className={`${primaryBg} text-white rounded-2xl shadow-lg overflow-hidden`}>
        <div className="h-1 bg-gradient-to-r from-yellow-500 via-yellow-300 to-yellow-500" />
        <div className="p-6 text-center">
          <p className="text-white/70 text-xs font-semibold uppercase tracking-widest mb-2">
            Resumo da Avaliação
          </p>
          <p className="text-5xl font-black tracking-tight mb-1">{avg.toFixed(2)}</p>
          <p className="text-white/60 text-sm">média / 5,00</p>
          <p className="mt-2 text-sm font-semibold text-white/90">{avgLabel(avg)}</p>
        </div>
      </div>

      {/* Tabela de notas */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow border border-gray-100 dark:border-gray-700 overflow-hidden">
        <div className={`${primaryBg} px-5 py-3`}>
          <h3 className="text-white font-bold text-sm uppercase tracking-wide">Notas por Indicador</h3>
        </div>
        <div className="divide-y divide-gray-100 dark:divide-gray-700">
          {indicators.map((ind, idx) => {
            const sc = scores[ind.id];
            return (
              <div key={ind.id} className="flex items-center justify-between px-5 py-3 gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
                    ${vtc ? "bg-teal-600" : "bg-[#003D73]"} text-white`}>{idx + 1}</span>
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{ind.name}</p>
                </div>
                <div className="flex-shrink-0">
                  <ScoreBadge value={sc} />
                </div>
              </div>
            );
          })}
        </div>
        {/* Linha de média */}
        <div className="flex items-center justify-between px-5 py-3 bg-gray-50 dark:bg-gray-700/50 border-t border-gray-200 dark:border-gray-700">
          <span className="text-sm font-bold text-gray-700 dark:text-gray-300">Média Final</span>
          <span className={`text-xl font-black ${avgColor(avg, vtc)}`}>{avg.toFixed(2)}</span>
        </div>
      </div>

      {/* Aviso */}
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
        <p className="text-sm text-blue-800 dark:text-blue-300 leading-relaxed">
          Confira as notas acima. Após confirmar, a avaliação será salva e{" "}
          <strong>{employeeName}</strong> será notificado(a) por e-mail.
        </p>
      </div>

      {submitError && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-4">
          <p className="text-sm text-red-700 dark:text-red-300">{submitError}</p>
        </div>
      )}

      {/* Botões */}
      <div className="flex gap-3 sticky bottom-4">
        <button
          type="button"
          onClick={onAdjust}
          disabled={submitting}
          className="flex-1 py-3.5 rounded-2xl font-semibold text-sm bg-white dark:bg-gray-800
            border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300
            hover:bg-gray-50 dark:hover:bg-gray-700 transition-all shadow"
        >
          ← Ajustar
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={submitting}
          className={`flex-[2] py-3.5 rounded-2xl font-bold text-white text-sm transition-all shadow-lg
            ${submitting ? "bg-gray-300 dark:bg-gray-700 cursor-not-allowed" : `${primaryBtn} cursor-pointer`}`}
        >
          {submitting ? "Enviando..." : "✓ Confirmar e Enviar Avaliação"}
        </button>
      </div>
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

export default function PublicEvaluationPage() {
  const { token } = useParams<{ token: string }>();
  const [state,       setState]       = useState<"loading" | "error" | "form" | "summary" | "success">("loading");
  const [errorMsg,    setErrorMsg]    = useState("");
  const [data,        setData]        = useState<any>(null);
  const [scores,      setScores]      = useState<Record<string, number>>({});
  const [submitting,  setSubmitting]  = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    if (!token) { setState("error"); setErrorMsg("Link inválido."); return; }
    fetch(`/api/performance/public/avaliar/${token}`)
      .then(r => r.json().then(j => ({ ok: r.ok, data: j })))
      .then(({ ok, data }) => {
        if (!ok) { setState("error"); setErrorMsg(data.detail || "Link inválido."); return; }
        setState("form");
        setData(data);
        setScores({});
      })
      .catch(() => { setState("error"); setErrorMsg("Erro de conexão. Tente novamente."); });
  }, [token]);

  const indicators: Indicator[] = data?.indicators || [];
  const employee: Employee | null = data?.employee || null;
  const totalFields  = indicators.length;
  const filledFields = Object.keys(scores).length;
  const allFilled    = filledFields === totalFields && totalFields > 0;

  const vtc           = isVTCCompany(data?.company_name || "");
  const primaryBg     = vtc ? "bg-teal-800"                  : "bg-[#003D73]";
  const primaryText   = vtc ? "text-teal-800"                : "text-[#003D73]";
  const primaryBorder = vtc ? "border-teal-600"              : "border-[#003D73]";
  const primaryBtn    = vtc ? "bg-teal-700 hover:bg-teal-800": "bg-[#003D73] hover:bg-[#002d57]";
  const progressColor = vtc ? "bg-teal-600"                  : "bg-[#003D73]";

  async function handleConfirmSubmit() {
    setSubmitting(true);
    setSubmitError("");
    const payload = {
      indicator_scores: Object.entries(scores).map(([indicator_id, score]) => ({ indicator_id, score })),
    };
    try {
      const res  = await fetch(`/api/performance/public/avaliar/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!res.ok) { setSubmitError(json.detail || "Erro ao enviar."); setSubmitting(false); return; }
      setState("success");
    } catch {
      setSubmitError("Erro de conexão."); setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950">

      {/* ── Header ── */}
      <header className={`${primaryBg} shadow-lg`}>
        <div className="h-1.5 bg-gradient-to-r from-yellow-500 via-yellow-300 to-yellow-500" />
        <div className="max-w-3xl mx-auto px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CompanyLogo companyName={data?.company_name || ""} />
            <span className="logo-fallback hidden text-white font-bold text-lg">
              {vtc ? "VTCLog" : "Voetur Viagens"}
            </span>
          </div>
          <div className="text-right">
            <div className="text-white font-semibold text-sm">Sistema Jarvis</div>
            <div className="text-white/60 text-xs">Gestão de Desempenho</div>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">

        {/* Loading */}
        {state === "loading" && (
          <div className="flex justify-center py-20">
            <div className={`w-10 h-10 border-4 ${vtc ? "border-teal-600" : "border-[#003D73]"} border-t-transparent rounded-full animate-spin`} />
          </div>
        )}

        {/* Erro */}
        {state === "error" && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-10 text-center shadow border border-gray-200 dark:border-gray-700">
            <div className="text-5xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Link Inválido</h2>
            <p className="text-gray-600 dark:text-gray-400 mb-4">{errorMsg}</p>
            <p className="text-sm text-gray-500">
              Em caso de dúvidas, entre em contato com o RH:{" "}
              <a href={`mailto:${HR_EMAIL}`} className={`hover:underline ${vtc ? "text-teal-700" : "text-[#003D73]"}`}>{HR_EMAIL}</a>
            </p>
          </div>
        )}

        {/* Sucesso */}
        {state === "success" && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-10 text-center shadow border border-green-200 dark:border-green-900">
            <div className="w-20 h-20 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-5">
              <svg className="w-10 h-10 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Avaliação Registrada!</h2>
            <p className="text-gray-600 dark:text-gray-400 mb-1">
              Obrigado, <strong>{data?.evaluator_name}</strong>.
            </p>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              A avaliação de <strong>{data?.employee?.name}</strong> foi salva com sucesso.
            </p>
            <p className="text-sm text-gray-400">
              Caso haja mais colaboradores para avaliar, acesse o link específico de cada um.
            </p>
          </div>
        )}

        {/* Resumo (confirmar antes de enviar) */}
        {state === "summary" && data && employee && (
          <SummaryPanel
            indicators={indicators}
            scores={scores}
            vtc={vtc}
            primaryBg={primaryBg}
            primaryBtn={primaryBtn}
            onAdjust={() => setState("form")}
            onConfirm={handleConfirmSubmit}
            submitting={submitting}
            submitError={submitError}
            employeeName={employee.name}
          />
        )}

        {/* Formulário */}
        {state === "form" && data && employee && (
          <div className="space-y-5">

            {/* Banner do ciclo */}
            <div className={`${primaryBg} text-white rounded-2xl shadow-lg overflow-hidden`}>
              <div className="h-1 bg-gradient-to-r from-yellow-500 via-yellow-300 to-yellow-500" />
              <div className="p-6">
                <p className="text-white/70 text-xs font-semibold uppercase tracking-widest mb-1">
                  Formulário de Avaliação de Desempenho
                </p>
                <h1 className="text-xl font-bold mb-3">{data.cycle_name}</h1>
                <div className="flex flex-wrap gap-3 text-sm">
                  <span className="flex items-center gap-1.5 bg-white/15 rounded-full px-3 py-1">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    {data.evaluator_name}
                  </span>
                  <span className="flex items-center gap-1.5 bg-white/15 rounded-full px-3 py-1">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                    </svg>
                    {data.company_name} / {data.branch_name}
                  </span>
                </div>
              </div>
            </div>

            {/* Colaborador */}
            <div className={`bg-white dark:bg-gray-800 rounded-2xl p-5 shadow border-l-4 ${primaryBorder}`}>
              <p className={`text-xs font-semibold uppercase tracking-widest ${primaryText} dark:text-blue-400 mb-1`}>
                Colaborador a Avaliar
              </p>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">{employee.name}</h2>
              <p className="text-sm text-gray-500 mt-0.5">{employee.cargo} · Matrícula: {employee.matricula}</p>
            </div>

            {/* Legenda da escala */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-4 shadow border border-gray-100 dark:border-gray-700">
              <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
                Escala de Avaliação
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-5 gap-2">
                {SCORE_OPTIONS.map(opt => (
                  <div key={opt.value}
                    className={`flex flex-col items-center py-2 px-2 rounded-xl border ${opt.color} text-center`}>
                    <span className="text-xs font-black mb-0.5">{opt.label}</span>
                    <span className="text-[10px] leading-tight">{opt.desc}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Progresso */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-4 shadow border border-gray-100 dark:border-gray-700">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-500 dark:text-gray-400">Progresso</span>
                <span className="font-bold text-gray-800 dark:text-white">
                  {filledFields}/{totalFields} indicadores ({totalFields > 0 ? Math.round(filledFields / totalFields * 100) : 0}%)
                </span>
              </div>
              <div className="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-2.5 overflow-hidden">
                <div
                  className={`${progressColor} h-2.5 rounded-full transition-all duration-300`}
                  style={{ width: totalFields > 0 ? `${(filledFields / totalFields) * 100}%` : "0%" }}
                />
              </div>
            </div>

            {/* Indicadores */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow border border-gray-100 dark:border-gray-700 overflow-hidden">
              <div className={`${primaryBg} px-6 py-4`}>
                <h3 className="text-white font-bold text-sm uppercase tracking-wide">Avaliação por Indicador</h3>
              </div>
              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {indicators.map((ind: Indicator, idx: number) => {
                  const selected = scores[ind.id];
                  return (
                    <div key={ind.id} className="p-5">
                      <div className="flex items-start gap-3 mb-3">
                        <span className={`flex-shrink-0 w-7 h-7 rounded-full ${selected ? (vtc ? "bg-teal-600" : "bg-[#003D73]") : "bg-gray-200 dark:bg-gray-700"} flex items-center justify-center text-xs font-bold ${selected ? "text-white" : "text-gray-500 dark:text-gray-400"} transition-colors`}>
                          {selected ? "✓" : idx + 1}
                        </span>
                        <div>
                          <p className="font-semibold text-gray-900 dark:text-white text-sm leading-snug">{ind.name}</p>
                          {ind.description && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 leading-relaxed">{ind.description}</p>
                          )}
                        </div>
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pl-10">
                        {SCORE_OPTIONS.map(opt => {
                          const isSelected = scores[ind.id] === opt.value;
                          return (
                            <button
                              key={opt.value}
                              type="button"
                              onClick={() => setScores(prev => ({ ...prev, [ind.id]: opt.value }))}
                              className={`flex flex-col items-center py-3 px-2 rounded-xl border-2 text-xs font-semibold transition-all ${
                                isSelected
                                  ? opt.color + " shadow-sm scale-[1.03]"
                                  : "border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-gray-300 bg-white dark:bg-gray-800"
                              }`}
                            >
                              <span className="text-sm font-bold mb-0.5">{opt.label}</span>
                              <span className="text-center leading-tight text-[10px]">{opt.desc}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Botão ver resumo */}
            <div className="sticky bottom-4 pt-2">
              <button
                type="button"
                disabled={!allFilled}
                onClick={() => { setSubmitError(""); setState("summary"); }}
                className={`w-full py-4 rounded-2xl font-bold text-white text-base transition-all shadow-lg ${
                  allFilled
                    ? `${primaryBtn} cursor-pointer`
                    : "bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed"
                }`}
              >
                {allFilled
                  ? `Ver Resumo e Confirmar →`
                  : `Preencha todos os indicadores (${filledFields}/${totalFields})`}
              </button>
            </div>
          </div>
        )}
      </main>

      <GrupoVoeturFooter vtc={vtc} />
    </div>
  );
}
