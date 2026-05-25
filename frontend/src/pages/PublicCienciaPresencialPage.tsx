import { useState } from "react";
import { Link } from "react-router-dom";

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

const HR_EMAIL    = "rh@voetur.com.br";
const PRIMARY_BG  = "bg-[#003D73]";
const PRIMARY_COL = "#003D73";

type Step = "busca" | "resultado" | "confirmado";

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

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

function applyCpfMask(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 11);
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 3)}.${digits.slice(3)}`;
  if (digits.length <= 9) return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6)}`;
  return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
}

function GrupoVoeturFooter() {
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
              className="text-xs text-gray-500 hover:text-[#003D73] transition-colors"
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
        <a href={`mailto:${HR_EMAIL}`} className="text-[#003D73] dark:text-blue-400 hover:underline">
          {HR_EMAIL}
        </a>
      </p>
      <p className="text-xs text-gray-400">Voetur Viagens · VTC Operadora Logística</p>
      <p className="text-xs text-gray-300 dark:text-gray-600 mt-1">Sistema Jarvis © 2025</p>
    </footer>
  );
}

export default function PublicCienciaPresencialPage() {
  const [step,                  setStep]                  = useState<Step>("busca");
  const [nome,                  setNome]                  = useState("");
  const [cpf,                   setCpf]                   = useState("");
  const [searching,             setSearching]             = useState(false);
  const [searchError,           setSearchError]           = useState("");
  const [data,                  setData]                  = useState<any>(null);
  const [showModal,             setShowModal]             = useState(false);
  const [submitting,            setSubmitting]            = useState(false);
  const [submitError,           setSubmitError]           = useState("");
  const [acknowledgedAt,        setAcknowledgedAt]        = useState("");
  const [alreadyAcknowledged,   setAlreadyAcknowledged]   = useState(false);
  const [alreadyAcknowledgedAt, setAlreadyAcknowledgedAt] = useState("");

  function validateForm(): string | null {
    const cpfDigits = cpf.replace(/\D/g, "");
    if (cpfDigits.length !== 11) return "CPF inválido. Informe os 11 dígitos.";
    const words = nome.trim().split(/\s+/).filter(Boolean);
    if (words.length < 2) return "Informe o nome completo (mínimo 2 palavras).";
    return null;
  }

  async function handleBuscar(e: React.FormEvent) {
    e.preventDefault();
    const err = validateForm();
    if (err) { setSearchError(err); return; }
    setSearchError("");
    setSearching(true);
    try {
      const res  = await fetch("/api/performance/public/ciencia-presencial/buscar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome: nome.trim(), cpf: cpf.replace(/\D/g, "") }),
      });
      const json = await res.json();
      if (!res.ok) { setSearchError(json.detail || "Colaborador não encontrado."); setSearching(false); return; }
      if (json.already_acknowledged) {
        setAlreadyAcknowledged(true);
        setAlreadyAcknowledgedAt(json.acknowledged_at || "");
        setData(json);
      } else {
        setAlreadyAcknowledged(false);
        setData(json);
        setStep("resultado");
      }
    } catch {
      setSearchError("Erro de conexão. Tente novamente.");
    } finally {
      setSearching(false);
    }
  }

  async function handleCiencia(feedbackReceived: boolean) {
    setSubmitting(true);
    setSubmitError("");
    try {
      const res  = await fetch("/api/performance/public/ciencia-presencial/confirmar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cpf: cpf.replace(/\D/g, ""),
          review_id: data?.review_id,
          feedback_received: feedbackReceived,
        }),
      });
      const json = await res.json();
      if (!res.ok) { setSubmitError(json.detail || "Erro ao registrar."); setSubmitting(false); return; }
      setShowModal(false);
      setAcknowledgedAt(json.acknowledged_at || "");
      setStep("confirmado");
    } catch {
      setSubmitError("Erro de conexão.");
    } finally {
      setSubmitting(false);
    }
  }

  function resetForm() {
    setStep("busca");
    setNome(""); setCpf("");
    setSearchError(""); setSubmitError("");
    setData(null); setShowModal(false);
    setAlreadyAcknowledged(false);
    setAlreadyAcknowledgedAt(""); setAcknowledgedAt("");
  }

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950">

      {/* ── Header ── */}
      <header className={`${PRIMARY_BG} shadow-lg`}>
        <div className="h-1.5 bg-gradient-to-r from-yellow-500 via-yellow-300 to-yellow-500" />
        <div className="max-w-2xl mx-auto px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img
              src="https://voeturviagens.com.br/wp-content/uploads/2025/07/voetur-viagens-logo-site.png"
              alt="Voetur Viagens"
              className="h-9 max-w-[190px] object-contain brightness-0 invert"
              onError={(e) => { e.currentTarget.style.display = "none"; }}
            />
            <span className="text-white/60 text-xs hidden sm:block">| Grupo Voetur</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-white font-semibold text-sm">Sistema Jarvis</div>
              <div className="text-white/60 text-xs">Ciência Presencial</div>
            </div>
            <Link
              to="/login"
              className="text-xs text-white/70 hover:text-white border border-white/30 px-3 py-1.5 rounded-lg transition-colors"
            >
              Entrar →
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">

        {/* ── Passo 1: Busca ── */}
        {step === "busca" && (
          <div className="space-y-4">
            <div className={`${PRIMARY_BG} text-white rounded-2xl shadow-lg overflow-hidden`}>
              <div className="h-1 bg-gradient-to-r from-yellow-500 via-yellow-300 to-yellow-500" />
              <div className="p-6">
                <p className="text-white/70 text-xs font-semibold uppercase tracking-widest mb-1">
                  Registro de Ciência
                </p>
                <h1 className="text-xl font-bold mb-1">Ciência Presencial</h1>
                <p className="text-white/80 text-sm">
                  Para colaboradores sem e-mail corporativo. Informe os dados abaixo para buscar sua avaliação.
                </p>
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow border border-gray-100 dark:border-gray-700">
              <form onSubmit={handleBuscar} className="space-y-5">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1.5">
                    Nome Completo
                  </label>
                  <input
                    type="text"
                    value={nome}
                    onChange={e => { setNome(e.target.value); setSearchError(""); setAlreadyAcknowledged(false); }}
                    placeholder="Ex: João Silva Santos"
                    autoComplete="name"
                    style={{ "--tw-ring-color": PRIMARY_COL } as React.CSSProperties}
                    className="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700
                               px-4 py-3 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400
                               focus:outline-none focus:ring-2 focus:ring-[#003D73] transition"
                  />
                  <p className="text-xs text-gray-400 mt-1.5">
                    Digite seu nome como consta na empresa (mínimo 2 palavras).
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1.5">CPF</label>
                  <input
                    type="text"
                    value={cpf}
                    onChange={e => { setCpf(applyCpfMask(e.target.value)); setSearchError(""); setAlreadyAcknowledged(false); }}
                    placeholder="000.000.000-00"
                    inputMode="numeric"
                    autoComplete="off"
                    maxLength={14}
                    className="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700
                               px-4 py-3 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400
                               focus:outline-none focus:ring-2 focus:ring-[#003D73] transition"
                  />
                  <p className="text-xs text-gray-400 mt-1.5">
                    Digite com ou sem pontuação — o sistema aceita das duas formas.
                  </p>
                </div>

                {searchError && (
                  <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3">
                    <p className="text-sm text-red-700 dark:text-red-300">{searchError}</p>
                  </div>
                )}

                {alreadyAcknowledged && data && (
                  <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-2xl p-5 text-center">
                    <div className="w-14 h-14 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
                      <svg className="w-7 h-7 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <p className="font-bold text-green-800 dark:text-green-200 mb-1">Ciência já registrada</p>
                    <p className="text-sm text-green-700 dark:text-green-300">
                      <strong>{data.employee_name}</strong>, sua ciência foi registrada em{" "}
                      <strong>{formatDate(alreadyAcknowledgedAt)}</strong>.
                    </p>
                    <button
                      type="button"
                      onClick={resetForm}
                      className="mt-4 text-sm text-[#003D73] hover:underline dark:text-blue-400"
                    >
                      Registrar outro colaborador →
                    </button>
                  </div>
                )}

                {!alreadyAcknowledged && (
                  <button
                    type="submit"
                    disabled={searching}
                    className={`w-full py-3.5 ${PRIMARY_BG} hover:bg-[#002d57] text-white font-bold rounded-xl transition-all disabled:opacity-60`}
                  >
                    {searching ? "Buscando..." : "Buscar Avaliação"}
                  </button>
                )}
              </form>
            </div>
          </div>
        )}

        {/* ── Passo 2: Resultado ── */}
        {step === "resultado" && data && (
          <div className="space-y-4">
            <button
              onClick={() => setStep("busca")}
              className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              ← Voltar
            </button>

            <div className={`${PRIMARY_BG} text-white rounded-2xl shadow-lg overflow-hidden`}>
              <div className="h-1 bg-gradient-to-r from-yellow-500 via-yellow-300 to-yellow-500" />
              <div className="p-6">
                <p className="text-white/70 text-xs font-semibold uppercase tracking-widest mb-1">
                  Resultado da Avaliação
                </p>
                <h1 className="text-xl font-bold mb-1">{data.cycle_name}</h1>
                <p className="text-white/80 text-sm mt-2">
                  <strong>{data.employee_name}</strong>
                </p>
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl p-4 shadow border-l-4 border-[#003D73] flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-[#003D73]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <div>
                <p className="text-xs text-gray-500">Avaliado por</p>
                <p className="font-semibold text-gray-900 dark:text-white">{data.evaluator_name}</p>
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow border border-gray-100 dark:border-gray-700 overflow-hidden">
              <div className={`${PRIMARY_BG} px-5 py-3`}>
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

            <div className="bg-white dark:bg-gray-800 rounded-2xl p-5 shadow border-2 border-[#003D73] flex items-center justify-between">
              <span className="font-bold text-gray-900 dark:text-white text-lg">Nota Final (Média)</span>
              <div className="text-right">
                <span className="text-3xl font-black text-[#003D73] dark:text-blue-400">
                  {data.final_score?.toFixed(2)}
                </span>
                <span className="text-sm text-gray-400 ml-1">/ 4,00</span>
              </div>
            </div>

            {submitError && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3">
                <p className="text-sm text-red-700 dark:text-red-300">{submitError}</p>
              </div>
            )}

            <button
              onClick={() => setShowModal(true)}
              className="w-full py-4 bg-green-600 hover:bg-green-700 text-white font-bold text-lg rounded-2xl shadow-lg transition-all"
            >
              Dar Ciência da Avaliação
            </button>
          </div>
        )}

        {/* ── Passo 3: Confirmado ── */}
        {step === "confirmado" && (
          <div className="space-y-4">
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-10 text-center shadow border border-green-200 dark:border-green-900">
              <div className="w-20 h-20 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-5">
                <svg className="w-10 h-10 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Ciência Registrada!</h2>
              <p className="text-gray-600 dark:text-gray-400 mb-1">
                <strong>{data?.employee_name}</strong>, ciência registrada com sucesso.
              </p>
              {acknowledgedAt && (
                <p className="text-sm text-gray-500 mb-6">
                  Registrada em: <strong>{formatDate(acknowledgedAt)}</strong>
                </p>
              )}
              <button
                onClick={resetForm}
                className={`w-full py-3.5 ${PRIMARY_BG} hover:bg-[#002d57] text-white font-bold rounded-xl transition-all`}
              >
                Registrar ciência de outro colaborador
              </button>
            </div>
          </div>
        )}
      </main>

      {/* ── Modal de Ciência ── */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-7 max-w-md w-full shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-10 h-10 rounded-xl ${PRIMARY_BG} flex items-center justify-center`}>
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">Confirmação de Ciência</h3>
            </div>

            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 leading-relaxed">
              Confirmo que <strong>{data?.employee_name}</strong> está ciente da sua avaliação de desempenho
              atribuída por <strong>{data?.evaluator_name}</strong>.
            </p>

            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 mb-5">
              <p className="text-sm font-semibold text-amber-800 dark:text-amber-200">
                O colaborador recebeu feedback presencial do gestor explicando os motivos das notas?
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
                Sim, recebeu feedback e está ciente
              </button>
              <button
                onClick={() => handleCiencia(false)}
                disabled={submitting}
                className="w-full py-3.5 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 font-semibold rounded-xl transition-all disabled:opacity-60"
              >
                Ainda não recebeu feedback
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
