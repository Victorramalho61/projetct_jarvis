import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";

interface Opportunity {
  category: string;
  title: string;
  description: string;
  count: number;
  score: number;
  effort: string;
}

const CATEGORY_STYLE: Record<string, string> = {
  blocked_proposals: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  recurring_errors:  "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  low_uptime:        "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
  failing_agents:    "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
};

const CATEGORY_LABEL: Record<string, string> = {
  blocked_proposals: "Proposals bloqueadas",
  recurring_errors:  "Erros recorrentes",
  low_uptime:        "Uptime baixo",
  failing_agents:    "Agentes falhando",
};

const EFFORT_STYLE: Record<string, string> = {
  baixo: "text-green-600 dark:text-green-400",
  médio: "text-yellow-600 dark:text-yellow-400",
  alto:  "text-red-600 dark:text-red-400",
};

function fmt(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export default function OpportunitiesPage() {
  const { token } = useAuth();
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const data = await apiFetch<{ opportunities: Opportunity[]; generated_at: string | null }>(
        "/api/agents/orchestrator/opportunities",
        { token }
      );
      setOpportunities(data.opportunities || []);
      setGeneratedAt(data.generated_at ?? null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const totalScore = opportunities.reduce((s, o) => s + (o.score ?? 0), 0);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Oportunidades</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Radar de oportunidades detectadas pelo Opportunity Scout
            {generatedAt && <span className="ml-2 text-gray-400">— atualizado {fmt(generatedAt)}</span>}
          </p>
        </div>
        <button
          onClick={load}
          className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
        >
          Atualizar
        </button>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-sm text-gray-400">Carregando...</div>
      ) : opportunities.length === 0 ? (
        <div className="py-12 text-center text-sm text-gray-400">
          Nenhuma oportunidade mapeada. Execute o pipeline de governança para gerar dados.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-center">
              <p className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">{opportunities.length}</p>
              <p className="text-xs text-gray-500 mt-1">Oportunidades ativas</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-center">
              <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">{totalScore}</p>
              <p className="text-xs text-gray-500 mt-1">Score total de impacto</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-center">
              <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                {opportunities.filter(o => o.effort === "baixo").length}
              </p>
              <p className="text-xs text-gray-500 mt-1">Esforço baixo</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-center">
              <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                {opportunities.filter(o => o.effort === "alto").length}
              </p>
              <p className="text-xs text-gray-500 mt-1">Esforço alto</p>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-700">
            {opportunities.map((opp, idx) => (
              <div key={idx} className="p-4 flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
                  <span className="text-sm font-bold text-gray-500 dark:text-gray-400">#{idx + 1}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${CATEGORY_STYLE[opp.category] ?? "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"}`}>
                      {CATEGORY_LABEL[opp.category] ?? opp.category}
                    </span>
                    <span className={`text-xs font-medium ${EFFORT_STYLE[opp.effort] ?? "text-gray-500"}`}>
                      esforço {opp.effort}
                    </span>
                  </div>
                  <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">{opp.title}</p>
                  {opp.description && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{opp.description}</p>
                  )}
                </div>
                <div className="flex-shrink-0 text-right">
                  <p className="text-lg font-bold text-gray-700 dark:text-gray-300">{opp.score}</p>
                  <p className="text-xs text-gray-400">score</p>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
