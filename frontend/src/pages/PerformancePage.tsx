import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

type Goal = {
  id: string;
  title: string;
  type: string;
  description?: string;
  target_value?: number;
  current_value?: number;
  unit?: string;
  weight?: number;
  period_start: string;
  period_end: string;
  status: string;
  owner_id?: string;
};

type Review = {
  id: string;
  cycle_id: string;
  employee_id: string;
  reviewer_id?: string;
  step: string;
  status: string;
  goals_score?: number;
  competencies_score?: number;
  behavior_score?: number;
  compliance_score?: number;
  final_score?: number;
  blocked_by?: string;
  comments?: string;
  manager_signed_at?: string;
  submitted_at?: string;
};

type Cycle = { id: string; name: string; period_start: string; period_end: string; status: string };

type Employee = { id: string; name: string; email?: string; department_id?: string; active: boolean };

type Dashboard = {
  total_reviews: number;
  by_status: Record<string, number>;
  score_distribution: Record<string, number>;
  blocked_by_compliance: number;
  completude_pct: number;
  pending_acknowledgments: number;
  pending_goal_acknowledgments: number;
};

type CalibrationCreate = { review_id: string; calibrated_score: number; justification: string };

// ── Helpers ───────────────────────────────────────────────────────────────────

const SCORE_LABELS: Record<number, string> = { 1: "Abaixo", 2: "Abaixo do esperado", 3: "Dentro do esperado", 4: "Acima", 5: "Excede" };

function ScoreSelect({ value, onChange }: { value: number | undefined; onChange: (v: number) => void }) {
  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
    >
      <option value="">Selecione...</option>
      {[1, 2, 3, 4, 5].map((n) => (
        <option key={n} value={n}>{n} — {SCORE_LABELS[n]}</option>
      ))}
    </select>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    draft: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    active: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    pending_self: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    pending_manager: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    pending_ack: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
    completed: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    disputed: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  };
  const labels: Record<string, string> = {
    draft: "Rascunho",
    active: "Ativa",
    pending_self: "Autoavaliação",
    pending_manager: "Aguard. Gestor",
    pending_ack: "Aguard. Ciência",
    completed: "Concluída",
    disputed: "Contestada",
    pending_hr: "Aguard. RH",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${styles[status] ?? "bg-gray-100 text-gray-600"}`}>
      {labels[status] ?? status}
    </span>
  );
}

// ── Tab: Meus Objetivos ────────────────────────────────────────────────────────

function MyGoalsTab({ token }: { token: string | null }) {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [acks, setAcks] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [signing, setSigning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Goal[]>("/api/performance/goals", { token });
      setGoals(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar metas");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function handleAcknowledge(goalId: string) {
    setSigning(goalId);
    setError(null);
    try {
      await apiFetch(`/api/performance/goals/${goalId}/acknowledge`, { method: "POST", token, json: {} });
      setAcks((prev) => new Set([...prev, goalId]));
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao assinar meta");
    } finally {
      setSigning(null);
    }
  }

  if (loading) return <div className="p-8 text-sm text-gray-400">Carregando metas...</div>;

  return (
    <div className="p-6">
      <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">Meus Objetivos</h3>
      {error && <div className="mb-4 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</div>}
      {goals.length === 0 ? (
        <p className="text-sm text-gray-400 dark:text-gray-500">Nenhuma meta atribuída.</p>
      ) : (
        <div className="space-y-3">
          {goals.map((g) => (
            <div key={g.id} className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-semibold text-gray-900 dark:text-gray-100">{g.title}</p>
                    <StatusBadge status={g.status} />
                    {g.status === "draft" && !acks.has(g.id) && (
                      <span className="inline-flex items-center rounded-full bg-amber-100 dark:bg-amber-900/30 px-2.5 py-0.5 text-xs font-semibold text-amber-700 dark:text-amber-400">
                        Aguardando assinatura
                      </span>
                    )}
                  </div>
                  {g.description && <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{g.description}</p>}
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400 dark:text-gray-500">
                    <span>Tipo: {g.type}</span>
                    {g.target_value != null && <span>Meta: {g.target_value} {g.unit}</span>}
                    {g.current_value != null && <span>Atual: {g.current_value} {g.unit}</span>}
                    <span>Período: {new Date(g.period_start).toLocaleDateString("pt-BR")} – {new Date(g.period_end).toLocaleDateString("pt-BR")}</span>
                  </div>
                </div>
                {g.status === "draft" && !acks.has(g.id) && (
                  <button
                    disabled={signing === g.id}
                    onClick={() => handleAcknowledge(g.id)}
                    className="shrink-0 rounded-lg bg-brand-green px-4 py-2 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-50 transition-colors"
                  >
                    {signing === g.id ? "Assinando..." : "Assinar e Aceitar"}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tab: Minha Avaliação ─────────────────────────────────────────────────────

function MyReviewTab({ token }: { token: string | null }) {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<string | null>(null);
  const [disputeComments, setDisputeComments] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<Review[]>("/api/performance/evaluations/reviews", { token });
      setReviews(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar avaliações");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function handleAcknowledge(reviewId: string, action: "acknowledged" | "disputed") {
    if (action === "disputed" && !disputeComments[reviewId]?.trim()) {
      setError("Informe o motivo da contestação.");
      return;
    }
    setActing(reviewId);
    setError(null);
    try {
      await apiFetch(`/api/performance/evaluations/reviews/${reviewId}/acknowledge`, {
        method: "POST", token,
        json: { action, comments: disputeComments[reviewId] || null },
      });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao responder avaliação");
    } finally {
      setActing(null);
    }
  }

  if (loading) return <div className="p-8 text-sm text-gray-400">Carregando avaliações...</div>;

  return (
    <div className="p-6">
      <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">Minha Avaliação</h3>
      {error && <div className="mb-4 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</div>}
      {reviews.length === 0 ? (
        <p className="text-sm text-gray-400 dark:text-gray-500">Nenhuma avaliação no momento.</p>
      ) : (
        <div className="space-y-4">
          {reviews.map((r) => (
            <div key={r.id} className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
              <div className="flex items-center gap-3 flex-wrap mb-3">
                <span className="font-semibold text-gray-900 dark:text-gray-100">Avaliação</span>
                <StatusBadge status={r.status} />
                {r.status === "pending_ack" && (
                  <span className="inline-flex items-center rounded-full bg-purple-100 dark:bg-purple-900/30 px-2.5 py-0.5 text-xs font-semibold text-purple-700 dark:text-purple-400">
                    Resultado disponível
                  </span>
                )}
              </div>
              {r.final_score != null && (
                <div className="mb-3 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                  <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3">
                    <div className="text-xs text-gray-400 dark:text-gray-500">Score Final</div>
                    <div className="text-xl font-bold text-gray-900 dark:text-gray-100">{r.final_score}</div>
                    {r.blocked_by && <div className="text-xs text-red-500">Bloqueado: {r.blocked_by}</div>}
                  </div>
                  {r.goals_score != null && <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3"><div className="text-xs text-gray-400">Metas</div><div className="font-bold text-gray-900 dark:text-gray-100">{r.goals_score}</div></div>}
                  {r.competencies_score != null && <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3"><div className="text-xs text-gray-400">Competências</div><div className="font-bold text-gray-900 dark:text-gray-100">{r.competencies_score}</div></div>}
                  {r.compliance_score != null && <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3"><div className="text-xs text-gray-400">Compliance</div><div className="font-bold text-gray-900 dark:text-gray-100">{r.compliance_score}</div></div>}
                </div>
              )}
              {r.comments && <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">{r.comments}</p>}
              {r.status === "pending_ack" && (
                <div className="mt-3 space-y-3">
                  <textarea
                    placeholder="Comentários (obrigatório ao contestar)"
                    value={disputeComments[r.id] ?? ""}
                    onChange={(e) => setDisputeComments((p) => ({ ...p, [r.id]: e.target.value }))}
                    rows={2}
                    className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green"
                  />
                  <div className="flex gap-2">
                    <button
                      disabled={acting === r.id}
                      onClick={() => handleAcknowledge(r.id, "acknowledged")}
                      className="rounded-lg bg-brand-green px-4 py-2 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-50 transition-colors"
                    >
                      {acting === r.id ? "..." : "Tomar Ciência"}
                    </button>
                    <button
                      disabled={acting === r.id}
                      onClick={() => handleAcknowledge(r.id, "disputed")}
                      className="rounded-lg border border-red-300 dark:border-red-700 px-4 py-2 text-sm font-semibold text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50 transition-colors"
                    >
                      Contestar
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tab: Avaliar Liderados ────────────────────────────────────────────────────

function TeamReviewTab({ token }: { token: string | null }) {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Record<string, Partial<Review>>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [signing, setSigning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<Review[]>("/api/performance/evaluations/reviews", { token });
      // Gestores veem reviews em que são reviewer
      setReviews(data.filter((r) => r.status === "pending_manager" || r.status === "pending_hr"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar avaliações");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  function getEdit(id: string, review: Review): Partial<Review> {
    return editing[id] ?? {
      goals_score: review.goals_score,
      competencies_score: review.competencies_score,
      behavior_score: review.behavior_score,
      compliance_score: review.compliance_score,
      comments: review.comments,
    };
  }

  function computePreview(e: Partial<Review>) {
    const g = e.goals_score ?? 0;
    const c = e.competencies_score ?? 0;
    const b = e.behavior_score ?? 0;
    const cp = e.compliance_score ?? 0;
    const raw = g * 0.50 + c * 0.25 + b * 0.15 + cp * 0.10;
    const norm = Math.max(1, Math.min(5, raw));
    const blocked = cp < 2.0;
    const final = blocked ? Math.min(norm, 2.5) : norm;
    return { raw: raw.toFixed(2), final: final.toFixed(2), blocked };
  }

  async function handleSave(id: string) {
    setSaving(id);
    setError(null);
    try {
      await apiFetch(`/api/performance/evaluations/reviews/${id}`, { method: "PUT", token, json: editing[id] ?? {} });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao salvar");
    } finally {
      setSaving(null);
    }
  }

  async function handleSign(id: string) {
    setSigning(id);
    setError(null);
    try {
      await apiFetch(`/api/performance/evaluations/reviews/${id}/sign`, { method: "POST", token, json: {} });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao assinar");
    } finally {
      setSigning(null);
    }
  }

  if (loading) return <div className="p-8 text-sm text-gray-400">Carregando...</div>;

  return (
    <div className="p-6">
      <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">Avaliar Liderados</h3>
      {error && <div className="mb-4 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</div>}
      {reviews.length === 0 ? (
        <p className="text-sm text-gray-400 dark:text-gray-500">Nenhuma avaliação pendente.</p>
      ) : (
        <div className="space-y-6">
          {reviews.map((r) => {
            const e = getEdit(r.id, r);
            const preview = computePreview(e);
            return (
              <div key={r.id} className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
                <div className="flex items-center gap-3 mb-4">
                  <span className="font-semibold text-gray-900 dark:text-gray-100">Liderado ID: {r.employee_id.slice(0, 8)}...</span>
                  <StatusBadge status={r.status} />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                  {(["goals_score", "competencies_score", "behavior_score", "compliance_score"] as const).map((field) => {
                    const labels: Record<string, string> = {
                      goals_score: "Metas (50%)",
                      competencies_score: "Competências (25%)",
                      behavior_score: "Comportamento (15%)",
                      compliance_score: "Compliance (10%)",
                    };
                    return (
                      <div key={field}>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{labels[field]}</label>
                        <ScoreSelect
                          value={e[field] as number | undefined}
                          onChange={(v) => setEditing((p) => ({ ...p, [r.id]: { ...p[r.id], [field]: v } }))}
                        />
                      </div>
                    );
                  })}
                </div>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Comentários</label>
                  <textarea
                    rows={3}
                    value={e.comments ?? ""}
                    onChange={(ev) => setEditing((p) => ({ ...p, [r.id]: { ...p[r.id], comments: ev.target.value } }))}
                    className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green"
                  />
                </div>

                {/* Score preview */}
                <div className="mb-4 rounded-lg bg-gray-50 dark:bg-gray-800 px-4 py-3 flex items-center gap-4 text-sm">
                  <span className="text-gray-500">Score estimado:</span>
                  <span className={`font-bold text-lg ${preview.blocked ? "text-red-500" : "text-brand-green"}`}>{preview.final}</span>
                  {preview.blocked && <span className="text-xs text-red-500">⚠ Bloqueado por compliance (cap 2.5)</span>}
                </div>

                <div className="flex gap-3">
                  <button
                    disabled={saving === r.id}
                    onClick={() => handleSave(r.id)}
                    className="rounded-lg border border-gray-300 dark:border-gray-700 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
                  >
                    {saving === r.id ? "Salvando..." : "Salvar rascunho"}
                  </button>
                  <button
                    disabled={signing === r.id}
                    onClick={() => handleSign(r.id)}
                    className="rounded-lg bg-brand-green px-4 py-2 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-50 transition-colors"
                  >
                    {signing === r.id ? "Assinando..." : "Assinar Avaliação"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Tab: Ciclos (RH/Admin) ────────────────────────────────────────────────────

function CyclesTab({ token }: { token: string | null }) {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [opening, setOpening] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", period_start: "", period_end: "" });
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<Cycle[]>("/api/performance/evaluations/cycles", { token });
      setCycles(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar ciclos");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await apiFetch("/api/performance/evaluations/cycles", { method: "POST", token, json: form });
      setForm({ name: "", period_start: "", period_end: "" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao criar ciclo");
    } finally {
      setCreating(false);
    }
  }

  async function handleOpen(id: string) {
    if (!confirm("Abrir ciclo e criar avaliações para todos os funcionários ativos?")) return;
    setOpening(id);
    setError(null);
    try {
      const result = await apiFetch<{ reviews_created: number }>(`/api/performance/evaluations/cycles/${id}/open`, { method: "POST", token, json: {} });
      alert(`Ciclo aberto. ${result.reviews_created} avaliações criadas.`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao abrir ciclo");
    } finally {
      setOpening(null);
    }
  }

  return (
    <div className="p-6">
      <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">Ciclos de Avaliação</h3>
      {error && <div className="mb-4 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</div>}

      <form onSubmit={handleCreate} className="mb-6 rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm space-y-4">
        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Novo Ciclo</h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <input required placeholder="Nome do ciclo" value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green" />
          <input required type="date" value={form.period_start} onChange={(e) => setForm((p) => ({ ...p, period_start: e.target.value }))}
            className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green" />
          <input required type="date" value={form.period_end} onChange={(e) => setForm((p) => ({ ...p, period_end: e.target.value }))}
            className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green" />
        </div>
        <button type="submit" disabled={creating}
          className="rounded-lg bg-brand-green px-5 py-2 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-50 transition-colors">
          {creating ? "Criando..." : "Criar Ciclo"}
        </button>
      </form>

      {loading ? <div className="text-sm text-gray-400">Carregando...</div> : (
        <div className="overflow-hidden rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm">
          <table className="min-w-full divide-y divide-gray-100 dark:divide-gray-800">
            <thead className="bg-gray-50 dark:bg-gray-800/50">
              <tr>{["Ciclo", "Período", "Status", "Ações"].map((h) => (
                <th key={h} className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{h}</th>
              ))}</tr>
            </thead>
            <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
              {cycles.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-5 py-4 font-medium text-gray-900 dark:text-gray-100">{c.name}</td>
                  <td className="px-5 py-4 text-sm text-gray-500 dark:text-gray-400">{new Date(c.period_start).toLocaleDateString("pt-BR")} – {new Date(c.period_end).toLocaleDateString("pt-BR")}</td>
                  <td className="px-5 py-4"><StatusBadge status={c.status} /></td>
                  <td className="px-5 py-4">
                    {c.status === "draft" && (
                      <button disabled={opening === c.id} onClick={() => handleOpen(c.id)}
                        className="rounded-lg bg-brand-green px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-deep disabled:opacity-50 transition-colors">
                        {opening === c.id ? "..." : "Abrir Ciclo"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Tab: Dashboard (RH/Admin) ─────────────────────────────────────────────────

function DashboardTab({ token }: { token: string | null }) {
  const [data, setData] = useState<Dashboard | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [calibForm, setCalibForm] = useState<Partial<CalibrationCreate>>({});
  const [calibSaving, setCalibSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dash, emps] = await Promise.all([
        apiFetch<Dashboard>("/api/performance/admin/dashboard", { token }),
        apiFetch<Employee[]>("/api/performance/admin/employees", { token }),
      ]);
      setData(dash);
      setEmployees(emps);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar dashboard");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function handleSync() {
    setSyncing(true);
    setError(null);
    try {
      const result = await apiFetch<Record<string, unknown>>("/api/performance/admin/sync-benner", { method: "POST", token, json: {} });
      alert(`Sync concluído: ${JSON.stringify(result)}`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao sincronizar");
    } finally {
      setSyncing(false);
    }
  }

  async function handleCalibrate(e: React.FormEvent) {
    e.preventDefault();
    if (!calibForm.review_id || calibForm.calibrated_score == null || !calibForm.justification) return;
    setCalibSaving(true);
    setError(null);
    try {
      await apiFetch("/api/performance/admin/calibrations", {
        method: "POST", token,
        json: { review_id: calibForm.review_id, calibrated_score: calibForm.calibrated_score, justification: calibForm.justification },
      });
      setCalibForm({});
      alert("Calibração salva.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao calibrar");
    } finally {
      setCalibSaving(false);
    }
  }

  if (loading) return <div className="p-8 text-sm text-gray-400">Carregando dashboard...</div>;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">Dashboard</h3>
        <button disabled={syncing} onClick={handleSync}
          className="rounded-lg border border-gray-300 dark:border-gray-700 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors">
          {syncing ? "Sincronizando..." : "Sync Benner"}
        </button>
      </div>

      {error && <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "Total Avaliações", value: data.total_reviews },
              { label: "Completude", value: `${data.completude_pct}%` },
              { label: "Bloqueadas (compliance)", value: data.blocked_by_compliance },
              { label: "Aguard. Ciência", value: data.pending_acknowledgments },
            ].map((kpi) => (
              <div key={kpi.label} className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 shadow-sm text-center">
                <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{kpi.value}</div>
                <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">{kpi.label}</div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Por Status</h4>
              <div className="space-y-2">
                {Object.entries(data.by_status).map(([s, count]) => (
                  <div key={s} className="flex items-center justify-between text-sm">
                    <StatusBadge status={s} />
                    <span className="font-medium text-gray-900 dark:text-gray-100">{count}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Distribuição de Notas</h4>
              <div className="space-y-2">
                {Object.entries(data.score_distribution).map(([score, count]) => (
                  <div key={score} className="flex items-center gap-3 text-sm">
                    <span className="w-4 font-medium text-gray-900 dark:text-gray-100">{score}</span>
                    <div className="flex-1 rounded-full bg-gray-100 dark:bg-gray-800 h-2">
                      <div className="rounded-full bg-brand-green h-2" style={{ width: `${data.total_reviews ? (count / data.total_reviews) * 100 : 0}%` }} />
                    </div>
                    <span className="text-gray-400">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Calibração */}
      <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Calibrar Score</h4>
        <form onSubmit={handleCalibrate} className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <input required placeholder="Review ID" value={calibForm.review_id ?? ""}
            onChange={(e) => setCalibForm((p) => ({ ...p, review_id: e.target.value }))}
            className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green" />
          <input required type="number" min={1} max={5} step={0.1} placeholder="Score calibrado (1–5)"
            value={calibForm.calibrated_score ?? ""}
            onChange={(e) => setCalibForm((p) => ({ ...p, calibrated_score: Number(e.target.value) }))}
            className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green" />
          <input required placeholder="Justificativa" value={calibForm.justification ?? ""}
            onChange={(e) => setCalibForm((p) => ({ ...p, justification: e.target.value }))}
            className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green" />
          <button type="submit" disabled={calibSaving}
            className="sm:col-span-3 rounded-lg bg-brand-green px-5 py-2 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-50 transition-colors">
            {calibSaving ? "Salvando..." : "Aplicar Calibração"}
          </button>
        </form>
      </div>

      {/* Employees */}
      <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Funcionários ({employees.length})</h4>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100 dark:divide-gray-800 text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800/50">
              <tr>{["Nome", "E-mail", "Ativo"].map((h) => <th key={h} className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{h}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
              {employees.slice(0, 20).map((e) => (
                <tr key={e.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-4 py-3 text-gray-900 dark:text-gray-100">{e.name}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{e.email ?? "—"}</td>
                  <td className="px-4 py-3">{e.active ? <span className="text-green-600 dark:text-green-400">Ativo</span> : <span className="text-gray-400">Inativo</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {employees.length > 20 && <p className="px-4 pt-2 text-xs text-gray-400">+{employees.length - 20} funcionários omitidos</p>}
        </div>
      </div>
    </div>
  );
}

// ── Tab: Gestão (RH/Admin/Gestor Ciclo) ──────────────────────────────────────

type GestaoSubTab = "visao-geral" | "slas" | "relatorios" | "notificacoes";

type OverviewGroup = {
  id: string; name: string; total: number;
  by_status: Record<string, number>; completion_rate: number;
};

type OverviewData = {
  cycle_id: string; total_reviews: number;
  by_company: OverviewGroup[]; by_branch: OverviewGroup[]; by_manager: OverviewGroup[];
};

type SlaViolation = { phase: string; phase_label: string; item_id: string; days_overdue: number; max_days: number; employee_id?: string };
type SlaData = { configs: { phase: string; max_days: number }[]; violations: SlaViolation[]; total_violations: number; compliance_pct: number };

type ReminderLog = { id: string; cycle_id: string; employee_id: string; phase: string; sent_at: string; sent_by: string | null };

const PHASES = [
  { key: "goal_signing",    label: "Assinatura de Metas",   defaultDays: 5 },
  { key: "self_assessment", label: "Autoavaliação",         defaultDays: 10 },
  { key: "manager_review",  label: "Avaliação do Gestor",   defaultDays: 7 },
  { key: "acknowledgment",  label: "Ciência do Resultado",  defaultDays: 5 },
];

function ProgressBar({ pct, color = "bg-brand-green" }: { pct: number; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="text-xs text-gray-500 w-8 text-right">{pct}%</span>
    </div>
  );
}

function ComplianceBadge({ pct }: { pct: number }) {
  const color = pct >= 90 ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
    : pct >= 70 ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
    : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>{pct}%</span>;
}

function GestaoOverviewSection({ title, groups }: { title: string; groups: OverviewGroup[] }) {
  const [open, setOpen] = useState(true);
  if (groups.length === 0) return null;
  return (
    <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm">
      <button onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3.5 text-sm font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors rounded-xl">
        {title}
        <svg className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100 dark:divide-gray-800">
            <thead className="bg-gray-50 dark:bg-gray-800/50">
              <tr>
                {["Dimensão", "Total", "% Concluído", "Metas Ass.", "Autoaval.", "Av.Gestor", "Ciência"].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
              {groups.map((g) => (
                <tr key={g.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100 text-sm max-w-[180px] truncate">{g.name || g.id}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{g.total}</td>
                  <td className="px-4 py-3 min-w-[140px]"><ProgressBar pct={g.completion_rate} /></td>
                  <td className="px-4 py-3 text-sm text-gray-500">{g.by_status?.completed ?? 0}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{g.by_status?.pending_self ?? 0}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{g.by_status?.pending_manager ?? 0}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{g.by_status?.pending_ack ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function GestaoTab({ token }: { token: string | null }) {
  const [subTab, setSubTab] = useState<GestaoSubTab>("visao-geral");
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [selectedCycleId, setSelectedCycleId] = useState("");

  // Visão Geral state
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);

  // SLAs state
  const [slaData, setSlaData] = useState<SlaData | null>(null);
  const [slaLoading, setSlaLoading] = useState(false);
  const [slaForm, setSlaForm] = useState<Record<string, number>>({});
  const [slaSaving, setSlaSaving] = useState(false);

  // Notificações state
  const [notifPhase, setNotifPhase] = useState("self_assessment");
  const [dryRunResult, setDryRunResult] = useState<{ name: string; email: string }[] | null>(null);
  const [notifLoading, setNotifLoading] = useState(false);
  const [notifHistory, setNotifHistory] = useState<ReminderLog[]>([]);

  // Advance/revert state
  const [reviewIdInput, setReviewIdInput] = useState("");
  const [transitionReason, setTransitionReason] = useState("");
  const [transitioning, setTransitioning] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Cycle[]>("/api/performance/evaluations/cycles", { token })
      .then((data) => {
        setCycles(data);
        const open = data.find((c) => c.status === "open" || c.status === "evaluation");
        setSelectedCycleId(open?.id ?? data[0]?.id ?? "");
      })
      .catch(() => {});
  }, [token]);

  // Load overview when cycle or subtab changes
  useEffect(() => {
    if (subTab !== "visao-geral" || !selectedCycleId) return;
    setOverviewLoading(true);
    setError(null);
    apiFetch<OverviewData>(`/api/performance/management/overview?cycle_id=${selectedCycleId}`, { token })
      .then(setOverview)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erro ao carregar visão geral"))
      .finally(() => setOverviewLoading(false));
  }, [subTab, selectedCycleId, token]);

  // Load SLA data
  useEffect(() => {
    if (subTab !== "slas" || !selectedCycleId) return;
    setSlaLoading(true);
    setError(null);
    Promise.all([
      apiFetch<SlaData>(`/api/performance/management/sla?cycle_id=${selectedCycleId}`, { token }),
      apiFetch<{ phase: string; max_days: number }[]>(`/api/performance/management/sla-configs?cycle_id=${selectedCycleId}`, { token }),
    ])
      .then(([sla, configs]) => {
        setSlaData(sla);
        const map: Record<string, number> = {};
        PHASES.forEach((p) => {
          const found = configs.find((c) => c.phase === p.key);
          map[p.key] = found?.max_days ?? p.defaultDays;
        });
        setSlaForm(map);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erro ao carregar SLAs"))
      .finally(() => setSlaLoading(false));
  }, [subTab, selectedCycleId, token]);

  // Load notif history
  useEffect(() => {
    if (subTab !== "notificacoes" || !selectedCycleId) return;
    apiFetch<ReminderLog[]>(`/api/performance/management/notify-history?cycle_id=${selectedCycleId}`, { token })
      .then(setNotifHistory)
      .catch(() => {});
  }, [subTab, selectedCycleId, token]);

  async function handleSaveSla() {
    setSlaSaving(true);
    setError(null);
    try {
      await Promise.all(
        PHASES.map((p) =>
          apiFetch("/api/performance/management/sla-configs", {
            method: "POST", token,
            json: { cycle_id: selectedCycleId, phase: p.key, max_days: slaForm[p.key] ?? p.defaultDays },
          })
        )
      );
      setSuccess("SLAs salvos com sucesso.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao salvar SLAs");
    } finally {
      setSlaSaving(false);
    }
  }

  async function handleDryRun() {
    setNotifLoading(true);
    setDryRunResult(null);
    setError(null);
    try {
      const res = await apiFetch<{ dry_run_list: { name: string; email: string }[] }>(
        "/api/performance/management/notify-pending",
        { method: "POST", token, json: { cycle_id: selectedCycleId, phase: notifPhase, dry_run: true } }
      );
      setDryRunResult(res.dry_run_list ?? []);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao pré-visualizar");
    } finally {
      setNotifLoading(false);
    }
  }

  async function handleSendNotif() {
    if (!confirm(`Enviar e-mails para todos os pendentes na fase selecionada?`)) return;
    setNotifLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{ sent: number; skipped: number }>(
        "/api/performance/management/notify-pending",
        { method: "POST", token, json: { cycle_id: selectedCycleId, phase: notifPhase, dry_run: false } }
      );
      setSuccess(`Enviados: ${res.sent}, ignorados: ${res.skipped}`);
      setDryRunResult(null);
      const history = await apiFetch<ReminderLog[]>(`/api/performance/management/notify-history?cycle_id=${selectedCycleId}`, { token });
      setNotifHistory(history);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao enviar notificações");
    } finally {
      setNotifLoading(false);
    }
  }

  async function handleTransition(action: "advance" | "revert") {
    if (!reviewIdInput.trim() || !transitionReason.trim()) {
      setError("Informe o ID da review e o motivo.");
      return;
    }
    setTransitioning(true);
    setError(null);
    try {
      const result = await apiFetch<{ status: string }>(
        `/api/performance/management/reviews/${reviewIdInput.trim()}/${action}`,
        { method: "PATCH", token, json: { reason: transitionReason } }
      );
      setSuccess(`Review ${action === "advance" ? "avançada" : "revertida"} para "${result.status}".`);
      setReviewIdInput("");
      setTransitionReason("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : `Erro ao ${action === "advance" ? "avançar" : "reverter"}`);
    } finally {
      setTransitioning(false);
    }
  }

  function downloadReport(path: string, filename: string) {
    const url = `${path}${path.includes("?") ? "&" : "?"}format=csv`;
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((res) => {
        if (!res.ok) throw new Error(`Erro ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch(() => setError("Erro ao exportar relatório"));
  }

  const SUB_TABS: { id: GestaoSubTab; label: string }[] = [
    { id: "visao-geral",     label: "Visão Geral" },
    { id: "slas",            label: "SLAs" },
    { id: "relatorios",      label: "Relatórios" },
    { id: "notificacoes",    label: "Notificações" },
  ];

  return (
    <div className="p-6">
      <div className="flex flex-wrap items-center gap-4 mb-5">
        <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">Gestão do Ciclo</h3>
        <select
          value={selectedCycleId}
          onChange={(e) => setSelectedCycleId(e.target.value)}
          className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green"
        >
          {cycles.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      {/* Sub-tabs */}
      <div className="flex gap-1 border-b border-gray-100 dark:border-gray-800 mb-5 overflow-x-auto">
        {SUB_TABS.map((t) => (
          <button key={t.id} onClick={() => { setSubTab(t.id); setError(null); setSuccess(null); }}
            className={`whitespace-nowrap px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              subTab === t.id
                ? "border-brand-green text-brand-deep dark:text-brand-mid"
                : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {error && <div className="mb-4 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</div>}
      {success && <div className="mb-4 rounded-lg border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 px-4 py-3 text-sm text-green-700 dark:text-green-300">{success}</div>}

      {/* ── Visão Geral ── */}
      {subTab === "visao-geral" && (
        <div className="space-y-4">
          {overviewLoading ? (
            <div className="text-sm text-gray-400">Carregando...</div>
          ) : overview ? (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                {[
                  { label: "Total Avaliações", value: overview.total_reviews },
                  { label: "Por Empresa", value: overview.by_company.length },
                  { label: "Por Filial", value: overview.by_branch.length },
                ].map((k) => (
                  <div key={k.label} className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 shadow-sm text-center">
                    <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{k.value}</div>
                    <div className="text-xs text-gray-400 mt-1">{k.label}</div>
                  </div>
                ))}
              </div>
              <GestaoOverviewSection title="Por Empresa" groups={overview.by_company} />
              <GestaoOverviewSection title="Por Filial" groups={overview.by_branch} />
              <GestaoOverviewSection title="Por Gestor" groups={overview.by_manager} />
            </>
          ) : (
            <p className="text-sm text-gray-400">Selecione um ciclo para visualizar.</p>
          )}
        </div>
      )}

      {/* ── SLAs ── */}
      {subTab === "slas" && (
        <div className="space-y-5">
          <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Configurar SLAs do Ciclo</h4>
            {slaLoading ? (
              <div className="text-sm text-gray-400">Carregando...</div>
            ) : (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {PHASES.map((p) => (
                    <div key={p.key}>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{p.label}</label>
                      <div className="flex items-center gap-2">
                        <input
                          type="number" min={1} max={60}
                          value={slaForm[p.key] ?? p.defaultDays}
                          onChange={(e) => setSlaForm((prev) => ({ ...prev, [p.key]: Number(e.target.value) }))}
                          className="w-24 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green"
                        />
                        <span className="text-sm text-gray-500">dias</span>
                      </div>
                    </div>
                  ))}
                </div>
                <button onClick={handleSaveSla} disabled={slaSaving || !selectedCycleId}
                  className="mt-4 rounded-lg bg-brand-green px-5 py-2 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-50 transition-colors">
                  {slaSaving ? "Salvando..." : "Salvar SLAs"}
                </button>
              </>
            )}
          </div>

          {slaData && (
            <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Violações de SLA</h4>
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  Compliance: <ComplianceBadge pct={slaData.compliance_pct} />
                </div>
              </div>
              {slaData.violations.length === 0 ? (
                <p className="text-sm text-green-600 dark:text-green-400">Nenhuma violação de SLA no ciclo.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-100 dark:divide-gray-800 text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-800/50">
                      <tr>
                        {["Fase", "Item", "Dias em Atraso", "Prazo"].map((h) => (
                          <th key={h} className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                      {slaData.violations.map((v) => (
                        <tr key={`${v.phase}-${v.item_id}`} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                          <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{v.phase_label}</td>
                          <td className="px-4 py-3 font-mono text-xs text-gray-500">{v.item_id.slice(0, 8)}...</td>
                          <td className="px-4 py-3"><span className="rounded-full bg-red-100 dark:bg-red-900/30 px-2 py-0.5 text-xs font-semibold text-red-600 dark:text-red-400">+{v.days_overdue}d</span></td>
                          <td className="px-4 py-3 text-gray-500">{v.max_days} dias</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Relatórios ── */}
      {subTab === "relatorios" && (
        <div className="space-y-5">
          <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Exportar Relatórios</h4>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {[
                { label: "Completude por Empresa", path: `/api/performance/management/reports/completion?cycle_id=${selectedCycleId}&dimension=company`, filename: "completude_empresa.csv" },
                { label: "Completude por Filial",  path: `/api/performance/management/reports/completion?cycle_id=${selectedCycleId}&dimension=branch`,  filename: "completude_filial.csv" },
                { label: "Completude por Gestor",  path: `/api/performance/management/reports/completion?cycle_id=${selectedCycleId}&dimension=manager`, filename: "completude_gestor.csv" },
                { label: "Violações de SLA",        path: `/api/performance/management/reports/sla?cycle_id=${selectedCycleId}`,                           filename: "sla_violations.csv" },
                { label: "Notas por Colaborador",   path: `/api/performance/management/reports/scores?cycle_id=${selectedCycleId}`,                        filename: "scores.csv" },
              ].map((r) => (
                <button
                  key={r.label}
                  disabled={!selectedCycleId}
                  onClick={() => downloadReport(r.path, r.filename)}
                  className="flex items-center gap-2 rounded-lg border border-gray-200 dark:border-gray-700 px-4 py-3 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors text-left"
                >
                  <svg className="w-4 h-4 shrink-0 text-brand-green" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Notificações ── */}
      {subTab === "notificacoes" && (
        <div className="space-y-5">
          {/* Send notifications */}
          <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Notificar Pendentes</h4>
            <div className="flex flex-wrap items-end gap-4 mb-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Fase</label>
                <select value={notifPhase} onChange={(e) => setNotifPhase(e.target.value)}
                  className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green">
                  {PHASES.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
                </select>
              </div>
              <button onClick={handleDryRun} disabled={notifLoading || !selectedCycleId}
                className="rounded-lg border border-gray-300 dark:border-gray-700 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors">
                {notifLoading ? "..." : "Pré-visualizar"}
              </button>
              <button onClick={handleSendNotif} disabled={notifLoading || !selectedCycleId}
                className="rounded-lg bg-brand-green px-4 py-2 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-50 transition-colors">
                {notifLoading ? "Enviando..." : "Enviar E-mails"}
              </button>
            </div>
            {dryRunResult && (
              <div className="mt-3">
                <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2">
                  {dryRunResult.length === 0 ? "Nenhum pendente encontrado." : `${dryRunResult.length} destinatário(s) que receberiam o e-mail:`}
                </p>
                {dryRunResult.map((d, i) => (
                  <div key={i} className="text-sm text-gray-600 dark:text-gray-400">{d.name} &lt;{d.email}&gt;</div>
                ))}
              </div>
            )}
          </div>

          {/* Flow control */}
          <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Controle de Fluxo</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Review ID</label>
                <input value={reviewIdInput} onChange={(e) => setReviewIdInput(e.target.value)}
                  placeholder="UUID da review"
                  className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Motivo</label>
                <input value={transitionReason} onChange={(e) => setTransitionReason(e.target.value)}
                  placeholder="Justificativa obrigatória"
                  className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-brand-green" />
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={() => handleTransition("advance")} disabled={transitioning}
                className="rounded-lg bg-brand-green px-4 py-2 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-50 transition-colors">
                {transitioning ? "..." : "Avançar"}
              </button>
              <button onClick={() => handleTransition("revert")} disabled={transitioning}
                className="rounded-lg border border-amber-300 dark:border-amber-700 px-4 py-2 text-sm font-semibold text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20 disabled:opacity-50 transition-colors">
                {transitioning ? "..." : "Reverter"}
              </button>
            </div>
          </div>

          {/* History */}
          {notifHistory.length > 0 && (
            <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Histórico de Lembretes</h4>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-100 dark:divide-gray-800 text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800/50">
                    <tr>
                      {["Fase", "Colaborador", "Enviado em", "Por"].map((h) => (
                        <th key={h} className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                    {notifHistory.slice(0, 20).map((h) => (
                      <tr key={h.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-4 py-2.5 text-gray-700 dark:text-gray-300">{h.phase}</td>
                        <td className="px-4 py-2.5 font-mono text-xs text-gray-500">{h.employee_id?.slice(0, 8)}...</td>
                        <td className="px-4 py-2.5 text-gray-500">{new Date(h.sent_at).toLocaleString("pt-BR")}</td>
                        <td className="px-4 py-2.5 text-gray-500">{h.sent_by ?? "automático"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

type Tab = "meus-objetivos" | "minha-avaliacao" | "avaliar-liderados" | "ciclos" | "dashboard" | "gestao";

const TABS: { id: Tab; label: string; roles: string[] }[] = [
  { id: "meus-objetivos",    label: "Meus Objetivos",   roles: ["admin", "rh", "gestor", "coordenador", "supervisor", "colaborador"] },
  { id: "minha-avaliacao",   label: "Minha Avaliação",  roles: ["admin", "rh", "gestor", "coordenador", "supervisor", "colaborador"] },
  { id: "avaliar-liderados", label: "Avaliar Liderados", roles: ["admin", "rh", "gestor", "coordenador", "supervisor"] },
  { id: "ciclos",            label: "Ciclos",            roles: ["admin", "rh"] },
  { id: "dashboard",         label: "Dashboard",         roles: ["admin", "rh"] },
  { id: "gestao",            label: "Gestão",            roles: ["admin", "rh", "gestor_ciclo"] },
];

export default function PerformancePage() {
  const { user, token } = useAuth();
  const role = user?.role ?? "colaborador";

  const visibleTabs = TABS.filter((t) => t.roles.includes(role));
  const [activeTab, setActiveTab] = useState<Tab>(visibleTabs[0]?.id ?? "meus-objetivos");

  return (
    <div className="flex flex-col min-h-full">
      <div className="border-b border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 px-6 pt-6">
        <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Gestão de Desempenho</h2>
        <p className="mt-1 mb-4 text-sm text-gray-500 dark:text-gray-400">Metas, avaliações e ciclos de performance Voetur</p>
        <div className="flex gap-1 overflow-x-auto">
          {visibleTabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`whitespace-nowrap px-4 py-2.5 text-[13px] font-medium border-b-2 transition-colors ${
                activeTab === t.id
                  ? "border-brand-green text-brand-deep dark:text-brand-mid"
                  : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 bg-gray-50 dark:bg-gray-950">
        {activeTab === "meus-objetivos"    && <MyGoalsTab token={token} />}
        {activeTab === "minha-avaliacao"   && <MyReviewTab token={token} />}
        {activeTab === "avaliar-liderados" && <TeamReviewTab token={token} />}
        {activeTab === "ciclos"            && <CyclesTab token={token} />}
        {activeTab === "dashboard"         && <DashboardTab token={token} />}
        {activeTab === "gestao"            && <GestaoTab token={token} />}
      </div>
    </div>
  );
}
