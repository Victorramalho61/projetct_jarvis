import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";

type Indicator = { id: string; name: string; description?: string };

const SCORE_OPTIONS = [
  { value: 1, label: "1", sublabel: "NAE", desc: "Não Atende às Expectativas",          color: "border-red-500 bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300" },
  { value: 2, label: "2", sublabel: "APE", desc: "Atende Parcialmente as Expectativas", color: "border-amber-500 bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300" },
  { value: 3, label: "3", sublabel: "AE",  desc: "Atende as Expectativas",              color: "border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" },
  { value: 4, label: "4", sublabel: "SE",  desc: "Supera as Expectativas",              color: "border-emerald-500 bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" },
  { value: 5, label: "5", sublabel: "EE",  desc: "Excede as Expectativas",              color: "border-purple-500 bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300" },
];

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
        <a href={`mailto:${HR_EMAIL}`} className="text-[#00694E] hover:underline transition-colors">
          {HR_EMAIL}
        </a>
      </p>
      <p className="text-xs text-gray-300 dark:text-gray-600 mt-1">Sistema Jarvis &copy; 2026 — Grupo Voetur</p>
    </footer>
  );
}

function ScoreBadge({ value }: { value: number }) {
  const opt = SCORE_OPTIONS.find(o => o.value === value);
  if (!opt) return <span>{value}</span>;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold border ${opt.color}`}>
      {opt.label} — {opt.desc}
    </span>
  );
}

function avgColor(avg: number): string {
  if (avg >= 4.5) return "text-purple-700 dark:text-purple-300";
  if (avg >= 3.5) return "text-[#00694E] dark:text-emerald-400";
  if (avg >= 2.5) return "text-[#00694E] dark:text-emerald-400";
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

// ── Modal de confirmação ──────────────────────────────────────────────────────

interface ConfirmModalProps {
  indicators: Indicator[];
  scores: Record<string, number>;
  observations: string;
  employeeName: string;
  primaryBg: string;
  primaryBtn: string;
  onClose: () => void;
  onConfirm: () => void;
  submitting: boolean;
  submitError: string;
}

function ConfirmModal({
  indicators, scores, observations, primaryBg, primaryBtn,
  onClose, onConfirm, submitting, submitError,
}: ConfirmModalProps) {
  const total = indicators.reduce((s, ind) => s + (scores[ind.id] ?? 0), 0);
  const avg   = indicators.length > 0 ? total / indicators.length : 0;
  const modalRef = useRef<HTMLDivElement>(null);

  function handleBackdropClick(e: React.MouseEvent) {
    if (e.target === e.currentTarget && !submitting) onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4
                 bg-black/60 backdrop-blur-sm"
      onClick={handleBackdropClick}
    >
      <div
        ref={modalRef}
        className="bg-white dark:bg-gray-800 w-full sm:max-w-lg rounded-t-3xl sm:rounded-2xl
                   shadow-2xl flex flex-col max-h-[92vh] sm:max-h-[88vh]
                   animate-in slide-in-from-bottom-8 duration-300"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex justify-center pt-3 pb-1 sm:hidden flex-shrink-0">
          <div className="w-10 h-1 rounded-full bg-gray-300 dark:bg-gray-600" />
        </div>

        <div className={`${primaryBg} px-6 py-5 flex-shrink-0 rounded-t-3xl sm:rounded-t-2xl overflow-hidden`}>
          <div className="h-0.5 bg-gradient-to-r from-yellow-500 via-yellow-300 to-yellow-500 -mx-6 -mt-5 mb-4" />
          <div className="text-center">
            <p className="text-white/70 text-xs font-semibold uppercase tracking-widest mb-1">
              Confirmar Auto-Avaliação
            </p>
            <p className="text-4xl font-black text-white">{avg.toFixed(2)}</p>
            <p className="text-white/50 text-xs mb-1">média / 5,00</p>
            <span className="inline-block bg-white/20 text-white text-xs font-semibold px-3 py-0.5 rounded-full">
              {avgLabel(avg)}
            </span>
          </div>
        </div>

        <div className="overflow-y-auto flex-1 p-5 space-y-4">
          <div className="rounded-xl border border-gray-100 dark:border-gray-700 overflow-hidden">
            <div className="bg-gray-50 dark:bg-gray-700/50 px-4 py-2.5">
              <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Suas Notas por Indicador
              </p>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {indicators.map((ind, idx) => (
                <div key={ind.id} className="flex items-center justify-between px-4 py-3 gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="flex-shrink-0 w-5 h-5 rounded-full bg-[#00694E] text-white text-[10px] font-bold flex items-center justify-center">
                      {idx + 1}
                    </span>
                    <p className="text-sm text-gray-800 dark:text-gray-200 truncate">{ind.name}</p>
                  </div>
                  <ScoreBadge value={scores[ind.id]} />
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-700/50 border-t border-gray-200 dark:border-gray-700">
              <span className="text-sm font-bold text-gray-700 dark:text-gray-300">Média Final</span>
              <div className="flex items-baseline gap-1">
                <span className={`text-xl font-black ${avgColor(avg)}`}>{avg.toFixed(2)}</span>
                <span className="text-xs text-gray-400">/ 5,00</span>
              </div>
            </div>
          </div>

          {observations.trim() && (
            <div className="rounded-xl border border-gray-100 dark:border-gray-700 overflow-hidden">
              <div className="bg-gray-50 dark:bg-gray-700/50 px-4 py-2.5">
                <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  Comentários sobre seu desempenho (auto avaliação)
                </p>
              </div>
              <div className="px-4 py-3">
                <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap line-clamp-5">
                  {observations}
                </p>
              </div>
            </div>
          )}

          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
            <p className="text-sm text-blue-800 dark:text-blue-300 leading-relaxed">
              📋 Esta é sua <strong>auto-avaliação</strong>. Ao confirmar, sua percepção sobre seu desempenho será registrada e compartilhada com seu gestor.
            </p>
          </div>

          {submitError && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-4">
              <p className="text-sm text-red-700 dark:text-red-300">{submitError}</p>
            </div>
          )}
        </div>

        <div className="flex-shrink-0 p-4 border-t border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-800
                        rounded-b-3xl sm:rounded-b-2xl flex gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="flex-1 py-3.5 rounded-xl font-semibold text-sm bg-white dark:bg-gray-700
                       border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300
                       hover:bg-gray-50 dark:hover:bg-gray-600 transition-all disabled:opacity-50"
          >
            ← Voltar e Ajustar
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={submitting}
            className={`flex-[2] py-3.5 rounded-xl font-bold text-white text-sm transition-all shadow-lg
              ${submitting ? "bg-gray-300 dark:bg-gray-700 cursor-not-allowed" : `${primaryBtn} cursor-pointer`}`}
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                Enviando...
              </span>
            ) : "✓ Confirmar e Enviar Auto-Avaliação"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Página de Auto-Avaliação ──────────────────────────────────────────────────

export default function PublicSelfEvaluationPage() {
  const { token } = useParams<{ token: string }>();
  const [state,          setState]          = useState<"loading" | "error" | "form" | "success">("loading");
  const [errorMsg,       setErrorMsg]       = useState("");
  const [data,           setData]           = useState<any>(null);
  const [scores,         setScores]         = useState<Record<string, number>>({});
  const [justifications, setJustifications] = useState<Record<string, string>>({});
  const [observations,   setObservations]   = useState("");
  const [showModal,      setShowModal]      = useState(false);
  const [submitting,     setSubmitting]     = useState(false);
  const [submitError,    setSubmitError]    = useState("");

  useEffect(() => {
    if (!token) { setState("error"); setErrorMsg("Link inválido."); return; }
    fetch(`/api/performance/public/auto-avaliar/${token}`)
      .then(r => r.json().then(j => ({ ok: r.ok, data: j })))
      .then(({ ok, data }) => {
        if (!ok) { setState("error"); setErrorMsg(data.detail || "Link inválido."); return; }
        setState("form");
        setData(data);
      })
      .catch(() => { setState("error"); setErrorMsg("Erro ao carregar formulário."); });
  }, [token]);

  const indicators: Indicator[] = data?.indicators ?? [];
  const employee = data?.employee ?? { id: "", name: "", cargo: "" };
  const totalFields  = indicators.length;
  const filledFields = Object.keys(scores).length;

  // Justificativa obrigatória para notas 1 (NAE) e 5 (EE)
  const justOk = Object.entries(scores).every(
    ([indId, score]) => score !== 1 && score !== 5 || (justifications[indId] || "").trim().length > 0
  );
  const allFilled = filledFields === totalFields && totalFields > 0 && justOk;

  const primaryBg   = "bg-[#00694E]";
  const primaryBtn  = "bg-[#00694E] hover:bg-[#004F3A]";

  async function handleConfirmSubmit() {
    setSubmitting(true);
    setSubmitError("");
    const payload = {
      indicator_scores: Object.entries(scores).map(([indicator_id, score]) => ({
        indicator_id,
        score,
        justification: justifications[indicator_id]?.trim() || null,
      })),
      observations: observations.trim() || null,
    };
    try {
      const res  = await fetch(`/api/performance/public/auto-avaliar/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!res.ok) {
        setSubmitError(json.detail || "Erro ao enviar. Tente novamente.");
        setSubmitting(false);
        return;
      }
      setShowModal(false);
      setState("success");
    } catch {
      setSubmitError("Erro de conexão. Verifique sua internet e tente novamente.");
      setSubmitting(false);
    }
  }

  function handleScoreChange(indicatorId: string, value: number) {
    setScores(prev => ({ ...prev, [indicatorId]: value }));
    if (value !== 1 && value !== 5) {
      setJustifications(prev => {
        const next = { ...prev };
        delete next[indicatorId];
        return next;
      });
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950">

      {/* Modal de confirmação */}
      {showModal && data && (
        <ConfirmModal
          indicators={indicators}
          scores={scores}
          observations={observations}
          employeeName={employee.name}
          primaryBg={primaryBg}
          primaryBtn={primaryBtn}
          onClose={() => { if (!submitting) { setShowModal(false); setSubmitError(""); } }}
          onConfirm={handleConfirmSubmit}
          submitting={submitting}
          submitError={submitError}
        />
      )}

      <header className={`${primaryBg} shadow-lg`}>
        <div className="h-1 bg-[#004F3A]" />
        <div className="max-w-3xl mx-auto px-5 py-4 flex items-center justify-between">
          <CompanyLogo />
          <div className="text-right">
            <p className="text-white/70 text-[10px] font-semibold uppercase tracking-widest">Sistema Jarvis</p>
            <p className="text-white text-xs font-bold">Auto-Avaliação de Desempenho</p>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 space-y-4">

        {/* Loading */}
        {state === "loading" && (
          <div className="flex justify-center py-20">
            <div className="w-10 h-10 border-4 border-[#00694E] border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {/* Erro */}
        {state === "error" && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-10 text-center shadow border border-gray-200 dark:border-gray-700">
            <div className="text-5xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Link Inválido</h2>
            <p className="text-gray-500 dark:text-gray-400 text-sm">{errorMsg}</p>
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
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Auto-Avaliação Enviada!</h2>
            <p className="text-gray-500 dark:text-gray-400 text-sm">
              Sua auto-avaliação foi registrada com sucesso. Obrigado pela sua participação!
            </p>
          </div>
        )}

        {/* Formulário */}
        {state === "form" && data && (
          <>
            {/* Card do colaborador */}
            <div className={`${primaryBg} rounded-2xl p-5 shadow-lg`}>
              <p className="text-white/70 text-xs font-semibold uppercase tracking-widest mb-1">
                🔄 Ciclo — {data.cycle_name}
              </p>
              <p className="text-white text-xl font-bold leading-snug">{employee.name}</p>
              <p className="text-white/70 text-sm mt-0.5">{employee.cargo}</p>
              {data.company_name && (
                <p className="text-white/50 text-xs mt-1">{data.company_name}</p>
              )}
            </div>

            {/* Banner auto-avaliação */}
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-2xl p-4">
              <p className="text-sm text-blue-800 dark:text-blue-300 leading-relaxed">
                💡 <strong>Auto-Avaliação:</strong> Avalie seu próprio desempenho com sinceridade.
                Sua percepção é valiosa para o processo de desenvolvimento. A justificativa é <strong>opcional</strong>.
              </p>
            </div>

            {/* Progresso */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-4 shadow border border-gray-100 dark:border-gray-700">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-500 dark:text-gray-400">Progresso</span>
                <span className="font-bold text-gray-800 dark:text-white">
                  {filledFields}/{totalFields} indicadores
                </span>
              </div>
              <div className="h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${
                    allFilled ? "bg-[#00694E]" : "bg-[#00694E]/60"
                  }`}
                  style={{ width: `${totalFields > 0 ? (filledFields / totalFields) * 100 : 0}%` }}
                />
              </div>
            </div>

            {/* ── Indicadores ── */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow border border-gray-100 dark:border-gray-700 overflow-hidden">
              <div className={`${primaryBg} px-6 py-4`}>
                <h3 className="text-white font-bold text-sm uppercase tracking-wide">Como você avalia seu desempenho?</h3>
                <p className="text-white/60 text-xs mt-0.5">
                  Para notas 1 (NAE) ou 5 (EE), a justificativa é obrigatória
                </p>
              </div>
              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {indicators.map((ind: Indicator, idx: number) => {
                  const selected = scores[ind.id];
                  const needsJust = selected === 1 || selected === 5;
                  const justVal  = justifications[ind.id] || "";

                  return (
                    <div key={ind.id} className="p-5">
                      {/* Número + nome */}
                      <div className="flex items-start gap-3 mb-3">
                        <span className={`flex-shrink-0 w-7 h-7 rounded-full transition-colors
                          ${selected ? "bg-[#00694E]" : "bg-gray-200 dark:bg-gray-700"}
                          flex items-center justify-center text-xs font-bold
                          ${selected ? "text-white" : "text-gray-500 dark:text-gray-400"}`}>
                          {selected ? "✓" : idx + 1}
                        </span>
                        <div>
                          <p className="font-semibold text-gray-900 dark:text-white text-sm leading-snug">{ind.name}</p>
                          {ind.description && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 leading-relaxed">{ind.description}</p>
                          )}
                        </div>
                      </div>

                      {/* Botões de nota */}
                      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pl-10">
                        {SCORE_OPTIONS.map(opt => {
                          const isSelected = scores[ind.id] === opt.value;
                          return (
                            <button
                              key={opt.value}
                              type="button"
                              onClick={() => handleScoreChange(ind.id, opt.value)}
                              className={`flex flex-col items-center py-3 px-2 rounded-xl border-2 text-xs font-semibold transition-all ${
                                isSelected
                                  ? opt.color + " shadow-sm scale-[1.03]"
                                  : "border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-gray-300 bg-white dark:bg-gray-800"
                              }`}
                            >
                              <span className="text-sm font-bold mb-0.5">{opt.sublabel} <span className="text-[10px] font-normal opacity-60">({opt.label})</span></span>
                              <span className="text-center leading-tight text-[10px]">{opt.desc}</span>
                            </button>
                          );
                        })}
                      </div>

                      {/* Campo de justificativa — obrigatório para notas 1 e 5 */}
                      {needsJust && (
                        <div className={`mt-4 ml-10 rounded-xl border-2 overflow-hidden ${!justVal.trim() ? "border-red-300 dark:border-red-700" : "border-[#00694E]/30 dark:border-[#00694E]/40"}`}>
                          <div className={`px-3 py-2 text-xs font-semibold ${!justVal.trim() ? "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400" : "bg-[#E6F4F0] dark:bg-[#00694E]/10 text-[#00694E] dark:text-emerald-400"}`}>
                            💬 Descreva com exemplos concretos esta nota atribuída. *
                          </div>
                          <textarea
                            value={justVal}
                            onChange={e => setJustifications(prev => ({ ...prev, [ind.id]: e.target.value }))}
                            placeholder="Descreva com exemplos concretos esta nota atribuída…"
                            rows={2}
                            className="w-full text-sm px-3 py-2.5 resize-none focus:outline-none
                                       bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200
                                       placeholder:text-gray-400 dark:placeholder:text-gray-500"
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* ── Observações (opcional) ── */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow border border-gray-100 dark:border-gray-700 overflow-hidden">
              <div className={`${primaryBg} px-6 py-4 flex items-center justify-between`}>
                <div>
                  <h3 className="text-white font-bold text-sm uppercase tracking-wide">
                    Comentários sobre seu desempenho (auto avaliação)
                  </h3>
                  <p className="text-white/60 text-xs mt-0.5">(opcional) — comentário livre sobre este ciclo</p>
                </div>
                {observations.trim().length > 0 && (
                  <span className="text-xs font-semibold bg-white/20 text-white px-2.5 py-1 rounded-full">
                    ✓ Preenchido
                  </span>
                )}
              </div>
              <div className="p-5">
                <div className="rounded-xl border-2 border-gray-200 dark:border-gray-600 overflow-hidden transition-all focus-within:border-[#00694E]/40">
                  <textarea
                    value={observations}
                    onChange={e => setObservations(e.target.value)}
                    placeholder="Ex.: Foi um ciclo de grandes aprendizados. Gostaria de aprimorar minha organização nas demandas diárias."
                    rows={2}
                    className="w-full text-sm px-4 py-3 resize-none focus:outline-none
                               bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200
                               placeholder:text-gray-400 dark:placeholder:text-gray-500"
                  />
                </div>
              </div>
            </div>

            {/* ── Botão enviar ── */}
            <div className="sticky bottom-4 pt-2">
              {!allFilled && (
                <p className="text-center text-xs text-gray-500 dark:text-gray-400 mb-2 px-4">
                  ⏳ Preencha todos os indicadores ({filledFields}/{totalFields})
                </p>
              )}
              <button
                type="button"
                disabled={!allFilled}
                onClick={() => { setSubmitError(""); setShowModal(true); }}
                className={`w-full py-4 rounded-2xl font-bold text-white text-base transition-all shadow-lg ${
                  allFilled
                    ? `${primaryBtn} cursor-pointer`
                    : "bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed"
                }`}
              >
                {allFilled ? "Ver Resumo e Confirmar Auto-Avaliação →" : `Preencha todos os indicadores (${filledFields}/${totalFields})`}
              </button>
            </div>
          </>
        )}

        <GrupoVoeturFooter />
      </main>
    </div>
  );
}
