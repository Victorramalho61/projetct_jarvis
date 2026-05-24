import { useState } from "react";
import { Link } from "react-router-dom";

const SCORE_LABELS: Record<number, string> = {
  1: "Muito Abaixo", 2: "Abaixo do Esperado", 3: "No Esperado", 4: "Acima do Esperado", 5: "Excede as Expectativas"
};

function ScoreBadge({ score }: { score: number }) {
  const colors = ["","bg-red-100 text-red-700","bg-orange-100 text-orange-700","bg-yellow-100 text-yellow-700","bg-blue-100 text-blue-700","bg-green-100 text-green-700"];
  return (
    <span className={`px-2 py-1 rounded text-xs font-semibold ${colors[Math.round(score)] || ""}`}>
      {score} — {SCORE_LABELS[Math.round(score)] || ""}
    </span>
  );
}

type Step = "busca" | "resultado" | "confirmado";

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

export default function PublicCienciaPresencialPage() {
  const [step, setStep] = useState<Step>("busca");
  const [nome, setNome] = useState("");
  const [matricula, setMatricula] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [data, setData] = useState<any>(null);
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [acknowledgedAt, setAcknowledgedAt] = useState("");
  const [alreadyAcknowledged, setAlreadyAcknowledged] = useState(false);
  const [alreadyAcknowledgedAt, setAlreadyAcknowledgedAt] = useState("");

  // Validações frontend
  function validateForm(): string | null {
    if (!/^\d+$/.test(matricula.trim())) return "A matrícula deve conter apenas números.";
    if (matricula.trim().length === 0) return "Informe a matrícula.";
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
      const res = await fetch("/api/performance/public/ciencia-presencial/buscar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome: nome.trim(), matricula: matricula.trim() }),
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
      const res = await fetch("/api/performance/public/ciencia-presencial/confirmar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nome: nome.trim(),
          matricula: matricula.trim(),
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
    setNome("");
    setMatricula("");
    setSearchError("");
    setSubmitError("");
    setData(null);
    setShowModal(false);
    setAlreadyAcknowledged(false);
    setAlreadyAcknowledgedAt("");
    setAcknowledgedAt("");
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-2xl mx-auto px-4 py-4 flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-700 rounded-md flex items-center justify-center text-white font-bold text-sm">J</div>
          <div className="flex-1">
            <div className="font-semibold text-gray-900 dark:text-white text-sm">Jarvis — Ciência Presencial</div>
            <div className="text-xs text-gray-500">Voetur Viagens / VTCLog</div>
          </div>
          <Link
            to="/login"
            className="text-xs text-blue-600 hover:underline dark:text-blue-400"
          >
            Entrar no sistema →
          </Link>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">

        {/* PASSO 1: Busca */}
        {step === "busca" && (
          <div className="space-y-4">
            <div className="bg-blue-700 text-white rounded-xl p-6">
              <h1 className="text-xl font-bold mb-1">Registro de Ciência Presencial</h1>
              <p className="text-blue-100 text-sm">
                Para colaboradores sem e-mail corporativo. Informe os dados abaixo para buscar sua avaliação.
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
              <form onSubmit={handleBuscar} className="space-y-5">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Nome Completo
                  </label>
                  <input
                    type="text"
                    value={nome}
                    onChange={e => { setNome(e.target.value); setSearchError(""); setAlreadyAcknowledged(false); }}
                    placeholder="Ex: João Silva Santos"
                    autoComplete="name"
                    className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2.5 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                  />
                  <p className="text-xs text-gray-400 mt-1">Digite seu nome como consta na empresa (mínimo 2 palavras).</p>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Matrícula
                  </label>
                  <input
                    type="text"
                    value={matricula}
                    onChange={e => { setMatricula(e.target.value.replace(/\D/g, "")); setSearchError(""); setAlreadyAcknowledged(false); }}
                    placeholder="Ex: 12345"
                    inputMode="numeric"
                    pattern="[0-9]+"
                    autoComplete="off"
                    className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2.5 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                  />
                  <p className="text-xs text-gray-400 mt-1">Apenas números. Consulte seu holerite ou crachá.</p>
                </div>

                {searchError && (
                  <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                    <p className="text-sm text-red-700 dark:text-red-300">{searchError}</p>
                  </div>
                )}

                {/* Caso já tenha dado ciência */}
                {alreadyAcknowledged && data && (
                  <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl p-4 text-center">
                    <div className="text-3xl mb-2">✅</div>
                    <p className="font-semibold text-green-800 dark:text-green-200 mb-1">Ciência já registrada</p>
                    <p className="text-sm text-green-700 dark:text-green-300">
                      <strong>{data.employee_name}</strong>, sua ciência foi registrada em{" "}
                      <strong>{formatDate(alreadyAcknowledgedAt)}</strong>.
                    </p>
                    <button
                      type="button"
                      onClick={resetForm}
                      className="mt-4 text-sm text-blue-600 hover:underline dark:text-blue-400"
                    >
                      Registrar outro colaborador
                    </button>
                  </div>
                )}

                {!alreadyAcknowledged && (
                  <button
                    type="submit"
                    disabled={searching}
                    className="w-full py-3 bg-blue-700 hover:bg-blue-800 text-white font-bold rounded-xl transition-all disabled:opacity-60"
                  >
                    {searching ? "Buscando..." : "🔍 Buscar Avaliação"}
                  </button>
                )}
              </form>
            </div>
          </div>
        )}

        {/* PASSO 2: Resultado */}
        {step === "resultado" && data && (
          <div className="space-y-4">
            <button
              onClick={() => setStep("busca")}
              className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 mb-2"
            >
              ← Voltar
            </button>

            <div className="bg-blue-700 text-white rounded-xl p-6">
              <h1 className="text-xl font-bold mb-1">Avaliação de Desempenho</h1>
              <p className="text-blue-100 text-sm">{data.cycle_name}</p>
              <div className="mt-3 text-sm">
                <span>👤 <strong>{data.employee_name}</strong></span>
              </div>
            </div>

            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
              <p className="text-sm text-blue-800 dark:text-blue-200">
                📋 Avaliado por: <strong>{data.evaluator_name}</strong>
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="p-4 border-b border-gray-100 dark:border-gray-700">
                <h3 className="font-semibold text-gray-900 dark:text-white">Notas por Indicador</h3>
              </div>
              <table className="w-full">
                <tbody>
                  {data.indicator_scores?.map((s: any) => (
                    <tr key={s.indicator_id} className="border-b border-gray-50 dark:border-gray-700 last:border-0">
                      <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{s.indicator_name}</td>
                      <td className="px-4 py-3 text-right"><ScoreBadge score={s.score} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <span className="font-semibold text-gray-900 dark:text-white">Nota Final (Média)</span>
              <span className="text-2xl font-bold text-blue-700">{data.final_score?.toFixed(2)} <span className="text-sm text-gray-400">/ 5.00</span></span>
            </div>

            {submitError && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                <p className="text-sm text-red-700 dark:text-red-300">{submitError}</p>
              </div>
            )}

            <button
              onClick={() => setShowModal(true)}
              className="w-full py-4 bg-green-600 hover:bg-green-700 text-white font-bold text-lg rounded-xl shadow transition-all"
            >
              ✅ Dar Ciência
            </button>
          </div>
        )}

        {/* PASSO 3: Confirmado */}
        {step === "confirmado" && (
          <div className="space-y-4">
            <div className="bg-white dark:bg-gray-800 rounded-xl p-8 text-center shadow-sm border border-green-200 dark:border-green-900">
              <div className="text-5xl mb-4">✅</div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Ciência Registrada!</h2>
              <p className="text-gray-600 dark:text-gray-400 mb-1">
                <strong>{data?.employee_name}</strong>, sua ciência foi registrada com sucesso.
              </p>
              {acknowledgedAt && (
                <p className="text-sm text-gray-500 mb-4">
                  Registrada em: <strong>{formatDate(acknowledgedAt)}</strong>
                </p>
              )}
              <button
                onClick={resetForm}
                className="mt-4 w-full py-3 bg-blue-700 hover:bg-blue-800 text-white font-bold rounded-xl transition-all"
              >
                Registrar ciência de outro colaborador
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Modal de Ciência */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 max-w-md w-full shadow-xl">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-3">Confirmação de Ciência</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Confirmo que <strong>{data?.employee_name}</strong> está ciente da sua avaliação de desempenho atribuída por <strong>{data?.evaluator_name}</strong>.
            </p>
            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3 mb-5">
              <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                O colaborador recebeu feedback presencial do gestor explicando os motivos das notas?
              </p>
            </div>
            {submitError && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 mb-4">
                <p className="text-sm text-red-700 dark:text-red-300">{submitError}</p>
              </div>
            )}
            <div className="flex flex-col gap-3">
              <button
                onClick={() => handleCiencia(true)}
                disabled={submitting}
                className="w-full py-3 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg transition-all disabled:opacity-60"
              >
                ✅ Sim, recebeu feedback e está ciente
              </button>
              <button
                onClick={() => handleCiencia(false)}
                disabled={submitting}
                className="w-full py-3 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 font-semibold rounded-lg transition-all disabled:opacity-60"
              >
                ⏳ Ainda não recebeu feedback
              </button>
              <button
                onClick={() => setShowModal(false)}
                disabled={submitting}
                className="w-full py-2 text-sm text-gray-500 hover:text-gray-700"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      <footer className="text-center text-xs text-gray-400 py-6">
        Voetur Viagens / VTC Operadora Logística — Sistema Jarvis
      </footer>
    </div>
  );
}
