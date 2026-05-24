import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

// Tipos
type Indicator = { id: string; name: string; description?: string };
type Subordinate = { employee_id: string; name: string; matricula: string; cargo: string };
type FormData = { [employeeId: string]: { [indicatorId: string]: number } };

// Escala de notas
const SCORE_LABELS: Record<number, string> = {
  1: "Muito Abaixo",
  2: "Abaixo do Esperado",
  3: "No Esperado",
  4: "Acima do Esperado",
  5: "Excede as Expectativas",
};

export default function PublicEvaluationPage() {
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<"loading" | "error" | "form" | "success">("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [data, setData] = useState<any>(null);
  const [scores, setScores] = useState<FormData>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) { setState("error"); setErrorMsg("Link inválido."); return; }
    fetch(`/api/performance/public/avaliar/${token}`)
      .then(r => r.json().then(j => ({ ok: r.ok, data: j })))
      .then(({ ok, data }) => {
        if (!ok) { setState("error"); setErrorMsg(data.detail || "Link inválido."); return; }
        setState("form");
        setData(data);
        // Inicializar scores vazios
        const initialScores: FormData = {};
        (data.subordinates || []).forEach((s: Subordinate) => {
          initialScores[s.employee_id] = {};
        });
        setScores(initialScores);
      })
      .catch(() => { setState("error"); setErrorMsg("Erro de conexão. Tente novamente."); });
  }, [token]);

  const totalFields = data ? (data.subordinates?.length || 0) * (data.indicators?.length || 0) : 0;
  const filledFields = Object.values(scores).reduce((acc, s) => acc + Object.keys(s).length, 0);
  const allFilled = filledFields === totalFields && totalFields > 0;

  function handleScore(employeeId: string, indicatorId: string, score: number) {
    setScores(prev => ({
      ...prev,
      [employeeId]: { ...prev[employeeId], [indicatorId]: score },
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!allFilled) return;
    setSubmitting(true);
    const payload = {
      scores: Object.entries(scores).map(([employee_id, indicatorScores]) => ({
        employee_id,
        indicator_scores: Object.entries(indicatorScores).map(([indicator_id, score]) => ({ indicator_id, score })),
      })),
    };
    try {
      const res = await fetch(`/api/performance/public/avaliar/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!res.ok) { setErrorMsg(json.detail || "Erro ao enviar."); setSubmitting(false); return; }
      setState("success");
    } catch {
      setErrorMsg("Erro de conexão."); setSubmitting(false);
    }
  }

  // Layout público simples
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-700 rounded-md flex items-center justify-center text-white font-bold text-sm">J</div>
          <div>
            <div className="font-semibold text-gray-900 dark:text-white text-sm">Jarvis — Gestão de Desempenho</div>
            <div className="text-xs text-gray-500">Voetur Viagens / VTCLog</div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {state === "loading" && (
          <div className="flex justify-center py-20">
            <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {state === "error" && (
          <div className="bg-white dark:bg-gray-800 rounded-xl p-8 text-center shadow-sm border border-gray-200 dark:border-gray-700">
            <div className="text-4xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Link Inválido</h2>
            <p className="text-gray-600 dark:text-gray-400 mb-4">{errorMsg}</p>
            <p className="text-sm text-gray-500">Em caso de dúvidas, entre em contato com o RH.</p>
          </div>
        )}

        {state === "success" && (
          <div className="bg-white dark:bg-gray-800 rounded-xl p-8 text-center shadow-sm border border-green-200 dark:border-green-900">
            <div className="text-5xl mb-4">✅</div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Avaliação Registrada!</h2>
            <p className="text-gray-600 dark:text-gray-400">
              Obrigado, <strong>{data?.evaluator_name}</strong>. As notas foram salvas com sucesso.
            </p>
          </div>
        )}

        {state === "form" && data && (
          <form onSubmit={handleSubmit}>
            {/* Header do ciclo */}
            <div className="bg-blue-700 text-white rounded-xl p-6 mb-6 shadow-sm">
              <h1 className="text-xl font-bold mb-1">Formulário de Avaliação de Desempenho</h1>
              <p className="text-blue-100 text-sm">{data.cycle_name}</p>
              <div className="mt-3 flex flex-wrap gap-4 text-sm">
                <span>👤 <strong>{data.evaluator_name}</strong></span>
                <span>🏢 {data.company_name} / {data.branch_name}</span>
              </div>
            </div>

            {/* Progresso */}
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 mb-6 shadow-sm border border-gray-200 dark:border-gray-700">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-600 dark:text-gray-400">Progresso de preenchimento</span>
                <span className="font-semibold text-blue-600">{filledFields}/{totalFields} campos</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all"
                  style={{ width: totalFields > 0 ? `${(filledFields / totalFields) * 100}%` : "0%" }}
                />
              </div>
            </div>

            {/* Colaboradores */}
            {data.subordinates?.map((sub: Subordinate) => (
              <div key={sub.employee_id} className="bg-white dark:bg-gray-800 rounded-xl p-6 mb-6 shadow-sm border border-gray-200 dark:border-gray-700">
                <div className="mb-5 pb-4 border-b border-gray-100 dark:border-gray-700">
                  <h2 className="text-lg font-bold text-gray-900 dark:text-white">{sub.name}</h2>
                  <p className="text-sm text-gray-500">{sub.cargo} · Matrícula: {sub.matricula}</p>
                </div>
                {data.indicators?.map((ind: Indicator) => (
                  <div key={ind.id} className="mb-6">
                    <div className="mb-2">
                      <label className="font-semibold text-gray-800 dark:text-gray-200 text-sm">{ind.name}</label>
                      {ind.description && <p className="text-xs text-gray-500 mt-0.5">{ind.description}</p>}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {[1, 2, 3, 4, 5].map(n => {
                        const selected = scores[sub.employee_id]?.[ind.id] === n;
                        return (
                          <button
                            key={n}
                            type="button"
                            onClick={() => handleScore(sub.employee_id, ind.id, n)}
                            className={`flex flex-col items-center px-3 py-2 rounded-lg border-2 text-xs font-medium transition-all min-w-[70px] ${
                              selected
                                ? "border-blue-600 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
                                : "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-blue-300 hover:bg-blue-50/50"
                            }`}
                          >
                            <span className="text-lg font-bold">{n}</span>
                            <span className="text-center leading-tight">{SCORE_LABELS[n]}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            ))}

            {/* Botão enviar */}
            <div className="sticky bottom-4">
              <button
                type="submit"
                disabled={!allFilled || submitting}
                className={`w-full py-4 rounded-xl font-bold text-white text-lg transition-all shadow-lg ${
                  allFilled && !submitting
                    ? "bg-blue-700 hover:bg-blue-800 cursor-pointer"
                    : "bg-gray-400 cursor-not-allowed"
                }`}
              >
                {submitting ? "Enviando..." : allFilled ? "✅ Enviar Avaliação" : `Preencha todos os campos (${filledFields}/${totalFields})`}
              </button>
            </div>
          </form>
        )}
      </main>

      <footer className="text-center text-xs text-gray-400 py-6 mt-8">
        Voetur Viagens / VTC Operadora Logística — Sistema Jarvis
      </footer>
    </div>
  );
}
