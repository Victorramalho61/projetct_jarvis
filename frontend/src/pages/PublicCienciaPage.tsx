import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

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

export default function PublicCienciaPage() {
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<"loading" | "error" | "info" | "acknowledged">("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [data, setData] = useState<any>(null);
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
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
      const res = await fetch(`/api/performance/public/ciencia/${token}`, {
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
      return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch { return iso; }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-2xl mx-auto px-4 py-4 flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-700 rounded-md flex items-center justify-center text-white font-bold text-sm">J</div>
          <div>
            <div className="font-semibold text-gray-900 dark:text-white text-sm">Jarvis — Resultado da Avaliação</div>
            <div className="text-xs text-gray-500">Voetur Viagens / VTCLog</div>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">
        {state === "loading" && <div className="flex justify-center py-20"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>}

        {state === "error" && (
          <div className="bg-white dark:bg-gray-800 rounded-xl p-8 text-center shadow-sm border">
            <div className="text-4xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold mb-2">Link Inválido</h2>
            <p className="text-gray-600 dark:text-gray-400 mb-2">{errorMsg}</p>
            <p className="text-sm text-gray-500">Em caso de dúvidas, entre em contato com o RH.</p>
          </div>
        )}

        {state === "acknowledged" && (
          <div className="bg-white dark:bg-gray-800 rounded-xl p-8 text-center shadow-sm border border-green-200">
            <div className="text-5xl mb-4">✅</div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Ciência Registrada</h2>
            {acknowledgedAt && <p className="text-gray-600 dark:text-gray-400 mb-1">Registrada em: <strong>{formatDate(acknowledgedAt)}</strong></p>}
            <p className="text-sm text-gray-500">Seu registro foi salvo com sucesso.</p>
          </div>
        )}

        {state === "info" && data && (
          <div className="space-y-4">
            <div className="bg-blue-700 text-white rounded-xl p-6">
              <h1 className="text-xl font-bold mb-1">Sua Avaliação de Desempenho</h1>
              <p className="text-blue-100 text-sm">{data.cycle_name}</p>
              <div className="mt-3 text-sm">
                <span>👤 Olá, <strong>{data.employee_name}</strong></span>
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

            <button onClick={() => setShowModal(true)} className="w-full py-4 bg-green-600 hover:bg-green-700 text-white font-bold text-lg rounded-xl shadow transition-all">
              ✅ Dar Ciência
            </button>
          </div>
        )}
      </main>

      {/* Modal de Ciência */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 max-w-md w-full shadow-xl">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-3">Confirmação de Ciência</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Confirmo que estou ciente da minha avaliação de desempenho atribuída por <strong>{data?.evaluator_name}</strong>.
            </p>
            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3 mb-5">
              <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                Você recebeu feedback presencial do gestor explicando os motivos das notas?
              </p>
            </div>
            <div className="flex flex-col gap-3">
              <button onClick={() => handleCiencia(true)} disabled={submitting}
                className="w-full py-3 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg transition-all disabled:opacity-60">
                ✅ Sim, recebi feedback e estou ciente
              </button>
              <button onClick={() => handleCiencia(false)} disabled={submitting}
                className="w-full py-3 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 font-semibold rounded-lg transition-all disabled:opacity-60">
                ⏳ Ainda não recebi feedback
              </button>
              <button onClick={() => setShowModal(false)} disabled={submitting}
                className="w-full py-2 text-sm text-gray-500 hover:text-gray-700">Cancelar</button>
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
