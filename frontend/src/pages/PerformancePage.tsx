import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from "recharts";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";

// ─── Tipos ───────────────────────────────────────────────────────────────────

type AppRole = "admin" | "user" | "rh" | "gerente" | "coordenador_supervisor" | "administrativo_operacional" | "administrativo" | "operacional";

type TabDef = { id: string; label: string; icon: string; roles: AppRole[] };

const TABS: TabDef[] = [
  { id: "dashboard",  label: "Dashboard",   icon: "📊", roles: ["admin", "rh", "gerente"] },
  { id: "indicadores", label: "Competências", icon: "🎯", roles: ["admin", "rh"] },
  { id: "hierarquia", label: "Hierarquia",  icon: "🏢", roles: ["admin", "rh"] },
  { id: "gestao-rh",  label: "Gestão RH",   icon: "⚙️", roles: ["admin", "rh"] },
  { id: "ciclo",      label: "Ciclo",       icon: "🔄", roles: ["admin", "rh"] },
  { id: "avaliacoes", label: "Avaliações",  icon: "✅", roles: ["gerente", "coordenador_supervisor"] },
  // Ciência Presencial e Auto-Aval. Presencial removidas do menu —
  // links disponíveis apenas no banner do Gestão RH para controle de distribuição
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function Badge({ children, color = "gray" }: { children: React.ReactNode; color?: string }) {
  const map: Record<string, string> = {
    gray:   "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
    green:  "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    red:    "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    blue:   "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    amber:  "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    violet: "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${map[color] ?? map.gray}`}>
      {children}
    </span>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

function StatCard({ label, value, color = "blue", onClick }: { label: string; value: string | number; color?: string; onClick?: () => void }) {
  const colorMap: Record<string, string> = {
    blue: "text-[#00694E] dark:text-emerald-400",
    green: "text-green-700 dark:text-green-400",
    amber: "text-amber-700 dark:text-amber-400",
    red: "text-red-700 dark:text-red-400",
    violet: "text-violet-700 dark:text-violet-400",
  };
  const clickable = !!onClick;
  return (
    <Card className={`p-5 ${clickable ? "cursor-pointer hover:shadow-md hover:border-[#00694E]/40 dark:hover:border-[#00694E]/40 transition-all" : ""}`}>
      {clickable ? (
        <button onClick={onClick} className="w-full text-left">
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-1">{label}</p>
          <p className={`text-3xl font-bold ${colorMap[color] ?? colorMap.blue}`}>{value}</p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Clique para ver detalhes</p>
        </button>
      ) : (
        <>
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-1">{label}</p>
          <p className={`text-3xl font-bold ${colorMap[color] ?? colorMap.blue}`}>{value}</p>
        </>
      )}
    </Card>
  );
}

function ModalWrapper({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b border-gray-100 dark:border-gray-700">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="h-8 w-8 grid place-items-center rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700 transition-all">✕</button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

// ─── Tab Dashboard ────────────────────────────────────────────────────────────

type DrilldownModal = "pending-evaluators" | "pending-ciencia" | "pending-self-eval" | "calibrated" | null;

function TabDashboard({ companies }: { companies: any[] }) {
  const { token } = useAuth();
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ empresa: "", filial: "", ciclo: "" });
  const [branches, setBranches] = useState<any[]>([]);
  const [cycles, setCycles] = useState<any[]>([]);
  const [drilldown, setDrilldown] = useState<DrilldownModal>(null);
  const [drilldownData, setDrilldownData] = useState<any[]>([]);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const [expandedManagers, setExpandedManagers] = useState<Set<number>>(new Set());
  const [exporting, setExporting] = useState(false);
  const initialLoaded = useRef(false);

  useEffect(() => {
    initialLoaded.current = false;
    setLoading(true);
    Promise.all([
      apiFetch<any[]>("/api/performance/admin/cycles", { token }).catch(() => []),
      apiFetch<any>("/api/performance/admin/dashboard", { token }).catch(() => null),
    ]).then(([cy, d]) => {
      setCycles(cy || []);
      setStats(d);
      initialLoaded.current = true;
    }).finally(() => setLoading(false));
  }, [token]);

  // Carregar filiais quando empresa muda
  useEffect(() => {
    if (!filters.empresa) { setBranches([]); setFilters(f => ({ ...f, filial: "" })); return; }
    apiFetch<any[]>(`/api/performance/admin/branches?company_id=${filters.empresa}`, { token })
      .then(b => setBranches(b || [])).catch(() => setBranches([]));
    setFilters(f => ({ ...f, filial: "" }));
  }, [filters.empresa]);

  useEffect(() => {
    if (!initialLoaded.current) return;
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.empresa) params.set("company_id", filters.empresa);
    if (filters.filial)  params.set("branch_id",  filters.filial);
    if (filters.ciclo)   params.set("cycle_id",   filters.ciclo);
    apiFetch<any>(`/api/performance/admin/dashboard?${params}`, { token })
      .then(setStats).catch(() => setStats(null)).finally(() => setLoading(false));
  }, [filters]);

  function openDrilldown(type: DrilldownModal) {
    setDrilldown(type);
    setDrilldownData([]);
    setDrilldownLoading(true);
    const params = new URLSearchParams();
    if (filters.empresa) params.set("company_id", filters.empresa);
    if (filters.filial)  params.set("branch_id",  filters.filial);
    if (filters.ciclo)   params.set("cycle_id",   filters.ciclo);
    // "calibrated" usa list_evaluations com filtro de status
    if (type === "calibrated") {
      params.set("status", "calibrated");
      apiFetch<any[]>(`/api/performance/admin/evaluations?${params}`, { token })
        .then(d => setDrilldownData(d || [])).catch(() => setDrilldownData([]))
        .finally(() => setDrilldownLoading(false));
    } else {
      apiFetch<any[]>(`/api/performance/admin/dashboard/${type}?${params}`, { token })
        .then(d => setDrilldownData(d || [])).catch(() => setDrilldownData([]))
        .finally(() => setDrilldownLoading(false));
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (filters.empresa) params.set("company_id", filters.empresa);
      if (filters.filial)  params.set("branch_id",  filters.filial);
      if (filters.ciclo)   params.set("cycle_id",   filters.ciclo);
      const res = await fetch(`/api/performance/admin/dashboard/export?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const cd = res.headers.get("Content-Disposition") || "";
      a.download = cd.match(/filename="([^"]+)"/)?.[1] || "desempenho.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch {}
    finally { setExporting(false); }
  }

  return (
    <div className="space-y-6">
      <Card className="p-4 flex flex-wrap gap-3 items-center">
        <select value={filters.empresa} onChange={e => setFilters(f => ({ ...f, empresa: e.target.value }))}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]">
          <option value="">Todas as empresas</option>
          {companies.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {branches.length > 0 && (
          <select value={filters.filial} onChange={e => setFilters(f => ({ ...f, filial: e.target.value }))}
            className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]">
            <option value="">Todas as filiais</option>
            {branches.map((b: any) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        )}
        <select value={filters.ciclo} onChange={e => setFilters(f => ({ ...f, ciclo: e.target.value }))}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#00694E]">
          <option value="">Ciclo atual</option>
          {cycles.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <div className="flex-1" />
        <button onClick={handleExport} disabled={exporting || !stats}
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#00694E] hover:bg-[#004F3A] text-white text-sm font-semibold rounded-lg transition-all disabled:opacity-50">
          {exporting ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : "⬇"}
          Exportar XLSX
        </button>
      </Card>

      {loading ? (
        <div className="flex justify-center py-16"><div className="w-8 h-8 border-4 border-[#00694E] border-t-transparent rounded-full animate-spin" /></div>
      ) : !stats ? (
        <Card className="p-8 text-center text-gray-500">Nenhum dado disponível.</Card>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatCard label="Total Avaliados" value={stats.total_evaluated ?? "—"} color="blue" />
            <StatCard label="Completude" value={`${stats.completion_pct ?? 0}%`} color="green" />
            <StatCard label="Pendentes Ciência" value={stats.pending_acknowledgment ?? "—"} color="amber"
              onClick={() => openDrilldown("pending-ciencia")} />
            <StatCard label="Sem Avaliação" value={stats.without_evaluation ?? "—"} color="red"
              onClick={() => openDrilldown("pending-evaluators")} />
            {(() => {
              const pct = stats.self_eval_pct ?? 0;
              const goalColor = pct >= 80 ? "green" : pct >= 60 ? "amber" : "red";
              return (
                <StatCard label={`Auto-Avaliações (Meta 80%)`} value={`${pct}%`} color={goalColor}
                  onClick={() => openDrilldown("pending-self-eval")} />
              );
            })()}
            <StatCard label="Calibrações" value={`${stats.calibrations_count ?? 0}`} color="blue"
              onClick={() => openDrilldown("calibrated")} />
          </div>
          {stats.indicator_averages?.length > 0 && (
            <Card className="p-5">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Médias por Indicador</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={stats.indicator_averages} margin={{ top: 0, right: 8, left: -16, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-30} textAnchor="end" interval={0} />
                  <YAxis domain={[0, 5]} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: any) => [Number(v).toFixed(2), "Média"]} />
                  <Bar dataKey="avg" fill="#00694E" radius={[4, 4, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}
        </>
      )}

      {/* Drilldown: Gestores pendentes */}
      <ModalWrapper open={drilldown === "pending-evaluators"}
        onClose={() => { setDrilldown(null); setExpandedManagers(new Set()); }}
        title="Gestores com Avaliações Pendentes">
        {drilldownLoading ? (
          <div className="flex justify-center py-8"><div className="w-6 h-6 border-4 border-[#00694E] border-t-transparent rounded-full animate-spin" /></div>
        ) : drilldownData.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-4">Nenhum gestor com avaliações pendentes.</p>
        ) : (
          <div className="space-y-2">
            <p className="text-xs text-gray-400 mb-3">{drilldownData.length} gestor{drilldownData.length !== 1 ? "es" : ""} — clique para expandir</p>
            {drilldownData.map((mgr: any, i: number) => {
              const isOpen = expandedManagers.has(i);
              const count = mgr.pending_employees?.length ?? 0;
              return (
                <div key={i} className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
                  <button onClick={() => setExpandedManagers(prev => { const n = new Set(prev); isOpen ? n.delete(i) : n.add(i); return n; })}
                    className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-full bg-[#E6F4F0] dark:bg-[#00694E]/20 flex items-center justify-center flex-shrink-0">
                        <svg className="w-4 h-4 text-[#00694E]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold text-gray-900 dark:text-white text-sm truncate">{mgr.manager_name}</p>
                        {mgr.manager_email && <p className="text-xs text-gray-400 truncate">{mgr.manager_email}</p>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400">{count} pendente{count !== 1 ? "s" : ""}</span>
                      <svg className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${isOpen ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="m9 6 6 6-6 6" /></svg>
                    </div>
                  </button>
                  {isOpen && (
                    <div className="border-t border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/30 px-4 py-3 space-y-2">
                      {mgr.pending_employees?.map((emp: any, j: number) => (
                        <div key={j} className="flex items-center gap-2 text-xs">
                          <span className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
                          <span className="text-gray-700 dark:text-gray-300 font-medium">{emp.name}</span>
                          <span className="text-gray-400">— {emp.cargo}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </ModalWrapper>

      {/* Drilldown: Pendentes de ciência */}
      <ModalWrapper open={drilldown === "pending-ciencia"} onClose={() => setDrilldown(null)} title="Colaboradores Pendentes de Ciência">
        {drilldownLoading ? (
          <div className="flex justify-center py-8"><div className="w-6 h-6 border-4 border-[#00694E] border-t-transparent rounded-full animate-spin" /></div>
        ) : drilldownData.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-4">Nenhum colaborador pendente de ciência.</p>
        ) : (
          <div className="space-y-2">
            {drilldownData.map((emp: any, i: number) => (
              <div key={i} className="flex items-center justify-between border border-gray-100 dark:border-gray-700 rounded-lg px-4 py-3">
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white text-sm">{emp.employee_name}</p>
                  <p className="text-xs text-gray-400">{emp.employee_cargo} · Avaliado por: {emp.evaluator_name}</p>
                </div>
                <div className="text-right">
                  <span className="text-sm font-bold text-amber-600">{emp.final_score != null ? Number(emp.final_score).toFixed(2) : "—"}</span>
                  <p className="text-xs text-gray-400">Nota</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </ModalWrapper>

      {/* Drilldown: Auto-avaliações pendentes */}
      <ModalWrapper open={drilldown === "pending-self-eval"} onClose={() => setDrilldown(null)} title="Colaboradores Pendentes de Auto-Avaliação">
        {drilldownLoading ? (
          <div className="flex justify-center py-8"><div className="w-6 h-6 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" /></div>
        ) : drilldownData.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-4">Todos os colaboradores concluíram a auto-avaliação! 🎉</p>
        ) : (
          <div className="space-y-1">
            <p className="text-xs text-gray-400 mb-3">{drilldownData.length} colaborador{drilldownData.length !== 1 ? "es" : ""} pendente{drilldownData.length !== 1 ? "s" : ""}</p>
            {drilldownData.map((emp: any, i: number) => (
              <div key={i} className="flex items-center justify-between border border-gray-100 dark:border-gray-700 rounded-lg px-4 py-2.5">
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white text-sm">{emp.employee_name}</p>
                  <p className="text-xs text-gray-400">{emp.employee_cargo} · {emp.hierarchy_level}{emp.branch_name ? ` · ${emp.branch_name}` : ""}</p>
                </div>
                <Badge color="violet">⏳ Pendente</Badge>
              </div>
            ))}
          </div>
        )}
      </ModalWrapper>

      {/* Drilldown: Calibrações */}
      <ModalWrapper open={drilldown === "calibrated"} onClose={() => setDrilldown(null)} title="Avaliações em Calibração">
        {drilldownLoading ? (
          <div className="flex justify-center py-8"><div className="w-6 h-6 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" /></div>
        ) : drilldownData.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-4">Nenhuma avaliação em fase de calibração.</p>
        ) : (
          <div className="space-y-2">
            <p className="text-xs text-gray-400 mb-3">{drilldownData.length} avaliação{drilldownData.length !== 1 ? "ões" : ""} calibrada{drilldownData.length !== 1 ? "s" : ""}</p>
            {drilldownData.map((ev: any, i: number) => (
              <div key={i} className="flex items-center justify-between border border-blue-100 dark:border-blue-900/30 rounded-lg px-4 py-3 bg-blue-50/30 dark:bg-blue-900/10">
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white text-sm">{ev.employee_name}</p>
                  <p className="text-xs text-gray-400">Avaliado por: {ev.evaluator_name}</p>
                </div>
                <div className="text-right">
                  <span className="text-sm font-bold text-blue-600 dark:text-blue-400">{ev.final_score != null ? Number(ev.final_score).toFixed(2) : "—"}</span>
                  <p className="text-xs text-gray-400">Nota calibrada</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </ModalWrapper>
    </div>
  );
}

// ─── Tab Indicadores ──────────────────────────────────────────────────────────

type Indicator = { id: string; name: string; description?: string; active: boolean; hierarchy_level?: number | null; perfil?: string };

const IND_LEVEL_LABELS: Record<number, string> = { 4: "N4 — Diretoria", 1: "N1 — Gerente", 2: "N2 — Coord./Supervisor", 3: "N3" };
const IND_LEVEL_COLORS: Record<number, string> = { 4: "amber", 1: "violet", 2: "blue", 3: "green" };

function TabIndicadores() {
  const { token } = useAuth();
  const [list, setList] = useState<Indicator[]>([]);
  const [loading, setLoading] = useState(true);
  const [levelFilter, setLevelFilter] = useState<string>("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [modal, setModal] = useState<{ open: boolean; item: Partial<Indicator> | null }>({ open: false, item: null });
  const [saving, setSaving] = useState(false);
  const [formErr, setFormErr] = useState("");

  function toggleExpand(id: string) {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function load() {
    setLoading(true);
    const params = new URLSearchParams({ active_only: "false" });
    if (levelFilter === "3-operacional") {
      params.set("hierarchy_level", "3"); params.set("perfil", "operacional");
    } else if (levelFilter === "3") {
      params.set("hierarchy_level", "3"); params.set("perfil", "administrativo");
    } else if (levelFilter) {
      params.set("hierarchy_level", levelFilter);
    }
    apiFetch<Indicator[]>(`/api/performance/indicators?${params}`, { token })
      .then(setList).catch(() => setList([]))
      .finally(() => setLoading(false));
  }
  useEffect(() => { load(); }, [token, levelFilter]);

  function openCreate() { setModal({ open: true, item: { name: "", description: "", active: true, hierarchy_level: null } }); setFormErr(""); }
  function openEdit(it: Indicator) { setModal({ open: true, item: { ...it } }); setFormErr(""); }
  function closeModal() { setModal({ open: false, item: null }); setFormErr(""); }

  async function handleSave() {
    const it = modal.item!;
    if (!it.name?.trim()) { setFormErr("Nome é obrigatório."); return; }
    if (!it.hierarchy_level) { setFormErr("Selecione o nível hierárquico."); return; }
    setSaving(true);
    try {
      if (it.id) {
        await apiFetch(`/api/performance/indicators/${it.id}`, { token, method: "PUT", json: it });
      } else {
        await apiFetch("/api/performance/indicators", { token, method: "POST", json: it });
      }
      closeModal(); load();
    } catch (e: any) { setFormErr(e instanceof ApiError ? e.message : "Erro ao salvar."); }
    finally { setSaving(false); }
  }

  async function toggleActive(it: Indicator) {
    try {
      await apiFetch(`/api/performance/indicators/${it.id}`, { token, method: "PUT", json: { active: !it.active } });
      load();
    } catch {}
  }

  return (
    <div>
      <div className="flex flex-wrap justify-between items-center mb-4 gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-base font-semibold text-gray-700 dark:text-gray-300">Competências de Avaliação</h2>
          <select value={levelFilter} onChange={e => setLevelFilter(e.target.value)}
            className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-2 py-1.5 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-[#00694E]">
            <option value="">Todos os níveis</option>
            <option value="1">N1 — Gerente (Estratégico)</option>
            <option value="2">N2 — Coord./Supervisor (Tático)</option>
            <option value="3">N3 — Administrativo</option>
            <option value="3-operacional">N3 — Operacional</option>
          </select>
        </div>
        <button onClick={openCreate} className="px-4 py-2 bg-[#00694E] hover:bg-[#004F3A] text-white text-sm font-semibold rounded-lg transition-all">+ Nova Competência</button>
      </div>
      <Card>
        {loading ? (
          <div className="flex justify-center py-12"><div className="w-7 h-7 border-4 border-[#00694E] border-t-transparent rounded-full animate-spin" /></div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-700">
                {["Nível/Perfil", "Nome (clique para descrição)", "Status", "Ações"].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {list.length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">Nenhuma competência cadastrada.</td></tr>}
              {list.map(it => {
                const perfLabel = it.perfil === "operacional" ? "Operacional" : it.perfil === "administrativo" ? "Administrativo" : "";
                return (
                <tr key={it.id} className="border-b border-gray-50 dark:border-gray-700/50 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-0.5">
                      {it.hierarchy_level ? <Badge color={IND_LEVEL_COLORS[it.hierarchy_level] ?? "gray"}>{IND_LEVEL_LABELS[it.hierarchy_level] ?? `N${it.hierarchy_level}`}</Badge> : <Badge color="gray">—</Badge>}
                      {perfLabel && <span className="text-xs text-gray-400">{perfLabel}</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => it.description && toggleExpand(it.id!)}
                      className={`text-left group ${it.description ? "cursor-pointer" : ""}`}
                      title={it.description ? "Clique para ver a descrição" : ""}>
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100 group-hover:text-[#00694E] dark:group-hover:text-emerald-400 transition-colors">
                        {it.name}
                        {it.description && (
                          <span className="ml-1.5 text-xs text-gray-400">{expanded.has(it.id!) ? "▲" : "▼"}</span>
                        )}
                      </span>
                      {expanded.has(it.id!) && it.description && (
                        <p className="mt-1.5 text-xs text-gray-600 dark:text-gray-400 leading-relaxed max-w-sm whitespace-normal">{it.description}</p>
                      )}
                    </button>
                  </td>
                  <td className="hidden" />
                  <td className="px-4 py-3"><Badge color={it.active ? "green" : "gray"}>{it.active ? "Ativo" : "Inativo"}</Badge></td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => openEdit(it)} className="text-xs text-[#00694E] hover:underline dark:text-emerald-400">Editar</button>
                      <button onClick={() => toggleActive(it)} className="text-xs text-gray-500 hover:underline dark:text-gray-400">{it.active ? "Desativar" : "Ativar"}</button>
                    </div>
                  </td>
                </tr>
              );
              })}
            </tbody>
          </table>
        )}
      </Card>

      <ModalWrapper open={modal.open} onClose={closeModal} title={modal.item?.id ? "Editar Competência" : "Nova Competência"}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Nível Hierárquico *</label>
            <select value={modal.item?.hierarchy_level ?? ""}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, hierarchy_level: e.target.value ? Number(e.target.value) : null } }))}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100">
              <option value="">Selecione o nível</option>
              <option value="4">N4 — Diretoria</option>
              <option value="1">N1 — Gerente (Estratégico)</option>
              <option value="2">N2 — Coordenador/Supervisor (Tático)</option>
              <option value="3">N3 — Administrativo</option>
              <option value="3-op">N3 — Operacional</option>
            </select>
          </div>
          {/* Perfil: aparece apenas quando N3 */}
          {(modal.item?.hierarchy_level === 3) && (
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Perfil N3 *</label>
              <select value={(modal.item as any)?.perfil ?? ""}
                onChange={e => setModal(m => ({ ...m, item: { ...m.item!, perfil: e.target.value } }))}
                className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100">
                <option value="">Selecione</option>
                <option value="administrativo">Administrativo</option>
                <option value="operacional">Operacional</option>
              </select>
            </div>
          )}
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Nome *</label>
            <input type="text" value={modal.item?.name ?? ""}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, name: e.target.value } }))}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100" />
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Descrição (competência)</label>
            <textarea value={modal.item?.description ?? ""}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, description: e.target.value } }))}
              rows={3}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100" />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="active-check" checked={modal.item?.active ?? true}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, active: e.target.checked } }))}
              className="rounded" />
            <label htmlFor="active-check" className="text-sm text-gray-700 dark:text-gray-300">Ativo</label>
          </div>
          {formErr && <p className="text-sm text-red-600 dark:text-red-400">{formErr}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={handleSave} disabled={saving} className="flex-1 py-2.5 bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold rounded-lg text-sm transition-all disabled:opacity-60">
              {saving ? "Salvando..." : "Salvar"}
            </button>
            <button onClick={closeModal} className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm transition-all">Cancelar</button>
          </div>
        </div>
      </ModalWrapper>
    </div>
  );
}

// ─── Tab Hierarquia ───────────────────────────────────────────────────────────

type Employee = {
  id: string; name: string; matricula: string; cargo: string;
  level: string; manager_id?: string; manager_name?: string;
  email?: string; branch_id: string; company_id: string;
};

const LEVEL_LABELS: Record<string, string> = {
  diretoria: "Diretoria",
  gerente: "Gerente",
  coordenador_supervisor: "Coord./Supervisor",
  administrativo: "Administrativo",
  operacional: "Operacional",
  administrativo_operacional: "Adm./Operacional", // legado
};

function LevelBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    gerente: "violet",
    coordenador_supervisor: "blue",
    administrativo_operacional: "gray",
    administrativo: "green",
    operacional: "amber",
  };
  return <Badge color={colors[level] ?? "gray"}>{LEVEL_LABELS[level] ?? level}</Badge>;
}

function TabHierarquia({ companies }: { companies: any[] }) {
  const { token } = useAuth();
  const [branches, setBranches] = useState<any[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(false);
  const [selCompany, setSelCompany] = useState("");
  const [selBranch, setSelBranch] = useState("");
  const [selLevel, setSelLevel] = useState("");
  const [selManager, setSelManager] = useState("");
  const [modal, setModal] = useState<{ open: boolean; item: Partial<Employee & { active?: boolean }> | null }>({ open: false, item: null });
  const [saving, setSaving] = useState(false);
  const [formErr, setFormErr] = useState("");
  const [importErrors, setImportErrors] = useState<string[]>([]);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Branches e managers para o form modal (baseados na empresa selecionada no FORM, não no filtro)
  const [modalBranches, setModalBranches] = useState<any[]>([]);
  const [modalManagers, setModalManagers] = useState<any[]>([]);

  // Carrega filiais quando empresa do form muda; gestores de TODAS as empresas (gestor pode ser de outra empresa)
  useEffect(() => {
    const cid = (modal.item as any)?.company_id;
    if (!cid) { setModalBranches([]); return; }
    apiFetch<any[]>(`/api/performance/admin/branches?company_id=${cid}`, { token })
      .then(b => setModalBranches(b || [])).catch(() => setModalBranches([]));
  }, [(modal.item as any)?.company_id, token]);

  // Gestores de todas as empresas — carrega uma vez quando o modal abre
  useEffect(() => {
    if (!modal.open) return;
    apiFetch<any[]>(`/api/performance/admin/employees`, { token })
      .then(emps => setModalManagers((emps || []).filter((e: any) => e.level === "diretoria" || e.level === "gerente" || e.level === "coordenador_supervisor")))
      .catch(() => setModalManagers([]));
  }, [modal.open, token]);

  useEffect(() => {
    if (!selCompany) { setBranches([]); setSelBranch(""); return; }
    apiFetch<any[]>(`/api/performance/admin/branches?company_id=${selCompany}`, { token }).then(setBranches).catch(() => {});
    setSelBranch("");
  }, [token, selCompany]);

  function loadEmployees() {
    if (!selCompany) { setEmployees([]); return; }
    setLoading(true);
    const params = new URLSearchParams({ company_id: selCompany });
    if (selBranch) params.set("branch_id", selBranch);
    apiFetch<Employee[]>(`/api/performance/admin/employees?${params}`, { token })
      .then(setEmployees).catch(() => setEmployees([]))
      .finally(() => setLoading(false));
  }

  // Derivados para filtros client-side
  // Gestores relevantes = apenas quem tem pelo menos 1 subordinado no conjunto
  // filtrado por nível (evita circular: não aplica selManager aqui)
  const levelFiltered = selLevel ? employees.filter(e => e.level === selLevel) : employees;
  const relevantMgrIds = new Set(levelFiltered.map(e => (e as any).manager_id).filter(Boolean));
  const managers = employees.filter(
    e => (e.level === "diretoria" || e.level === "gerente" || e.level === "coordenador_supervisor") && relevantMgrIds.has(e.id)
  );
  const filteredEmployees = employees.filter(e => {
    if (selLevel && e.level !== selLevel) return false;
    if (selManager === "__no_manager__" && (e as any).manager_id) return false;
    if (selManager && selManager !== "__no_manager__" && (e as any).manager_id !== selManager) return false;
    return true;
  });

  useEffect(() => { loadEmployees(); }, [token, selCompany, selBranch]);

  function openCreate() {
    setModal({ open: true, item: { company_id: selCompany, branch_id: selBranch, level: "administrativo", active: true } });
    setFormErr("");
  }
  function openEdit(e: Employee) { setModal({ open: true, item: { ...e } }); setFormErr(""); }
  function closeModal() { setModal({ open: false, item: null }); setFormErr(""); }

  function validateCPF(cpf: string): boolean {
    const d = cpf.replace(/\D/g, "");
    if (d.length !== 11 || /^(\d)\1+$/.test(d)) return false;
    const calc = (n: number) => {
      const s = d.slice(0, n).split("").reduce((acc, c, i) => acc + parseInt(c) * (n + 1 - i), 0);
      const r = s % 11; return r < 2 ? 0 : 11 - r;
    };
    return calc(9) === parseInt(d[9]) && calc(10) === parseInt(d[10]);
  }

  async function handleSave() {
    const it = { ...modal.item!, name: (modal.item!.name || "").trim().toUpperCase() };
    if (!it.name) { setFormErr("Nome é obrigatório."); return; }
    if (!it.company_id) { setFormErr("Empresa é obrigatória."); return; }
    if (!it.branch_id) { setFormErr("Filial é obrigatória. Selecione na lista acima."); return; }
    const cpfRaw = ((it as any).cpf || "").replace(/\D/g, "");
    if (!cpfRaw) { setFormErr("CPF é obrigatório para todos os colaboradores."); return; }
    if (!validateCPF(cpfRaw)) { setFormErr("CPF inválido. Verifique os dígitos verificadores."); return; }
    setSaving(true);
    try {
      if (it.id) {
        await apiFetch(`/api/performance/admin/employees/${it.id}`, { token, method: "PUT", json: it });
      } else {
        await apiFetch("/api/performance/admin/employees", { token, method: "POST", json: it });
      }
      closeModal(); loadEmployees();
    } catch (e: any) { setFormErr(e instanceof ApiError ? e.message : "Erro ao salvar."); }
    finally { setSaving(false); }
  }

  async function handleDeactivate() {
    const it = modal.item!;
    if (!it.id) return;
    if (!confirm(`Desativar "${it.name}"? Ele não aparecerá mais na lista.`)) return;
    setSaving(true);
    try {
      await apiFetch(`/api/performance/admin/employees/${it.id}`, { token, method: "PUT", json: { active: false } });
      closeModal(); loadEmployees();
    } catch (e: any) { setFormErr(e instanceof ApiError ? e.message : "Erro ao desativar."); }
    finally { setSaving(false); }
  }

  async function handleDownloadTemplate() {
    try {
      const res = await fetch("/api/performance/admin/employees/template", { headers: { Authorization: `Bearer ${token}` } });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "template_hierarquia.xlsx"; a.click();
      URL.revokeObjectURL(url);
    } catch {}
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true); setImportErrors([]);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch("/api/performance/admin/employees/import", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const json = await res.json();
      if (!res.ok) {
        setImportErrors(json.errors || [json.detail || "Erro na importação."]);
      } else if (json.errors?.length > 0) {
        // O servidor retorna 200 mesmo com erros de validação — exibir aqui
        setImportErrors(json.errors);
      } else {
        // Sucesso real
        const warnings: string[] = json.manager_warnings || [];
        setImportErrors([
          `✅ ${json.imported} colaborador(es) importado(s) com sucesso!`,
          ...warnings.map((w: string) => `⚠️ ${w}`),
        ]);
        loadEmployees();
      }
    } catch { setImportErrors(["Erro de conexão."]); }
    finally { setImporting(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  // managersForModal agora é o estado modalManagers (carregado pela empresa do form)

  return (
    <div>
      <div className="flex flex-wrap gap-3 items-center mb-4">
        <select value={selCompany} onChange={e => setSelCompany(e.target.value)}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-800 dark:text-gray-200">
          <option value="">Selecione a empresa</option>
          {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {branches.length > 0 && (
          <select value={selBranch} onChange={e => setSelBranch(e.target.value)}
            className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-800 dark:text-gray-200">
            <option value="">Todas as filiais</option>
            {branches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        )}
        {employees.length > 0 && (
          <select value={selLevel} onChange={e => setSelLevel(e.target.value)}
            className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-800 dark:text-gray-200">
            <option value="">Todos os níveis</option>
            <option value="diretoria">Diretoria</option>
            <option value="gerente">Gerente</option>
            <option value="coordenador_supervisor">Coordenador / Supervisor</option>
            <option value="administrativo">Administrativo</option>
            <option value="operacional">Operacional</option>
          </select>
        )}
        {employees.length > 0 && (
          <select value={selManager} onChange={e => setSelManager(e.target.value)}
            className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-800 dark:text-gray-200">
            <option value="">Todos os gestores</option>
            <option value="__no_manager__">Sem gestor</option>
            {managers.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        )}
        <div className="flex-1" />
        {selCompany && (
          <>
            <button onClick={openCreate} className="px-4 py-2 bg-[#00694E] hover:bg-[#004F3A] text-white text-sm font-semibold rounded-lg transition-all">+ Colaborador</button>
            <button onClick={handleDownloadTemplate} className="px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 text-sm font-semibold rounded-lg transition-all">⬇ Template Excel</button>
            <label className={`px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 text-sm font-semibold rounded-lg transition-all cursor-pointer ${importing ? "opacity-60 cursor-not-allowed" : ""}`}>
              {importing ? "Importando..." : "📤 Importar Planilha"}
              <input ref={fileRef} type="file" accept=".xlsx,.xls" onChange={handleImport} className="hidden" disabled={importing} />
            </label>
          </>
        )}
      </div>

      {importErrors.length > 0 && (() => {
        const isSuccess = importErrors.length === 1 && importErrors[0].startsWith("✅");
        return (
          <Card className={`p-4 mb-4 ${isSuccess ? "border-green-200 dark:border-green-800" : "border-red-200 dark:border-red-800"}`}>
            {!isSuccess && <p className="text-sm font-semibold text-red-700 dark:text-red-400 mb-2">Erros na importação:</p>}
            <ul className="space-y-1">
              {importErrors.map((err, i) => (
                <li key={i} className={`text-xs ${isSuccess ? "text-green-700 dark:text-green-400 font-semibold" : "text-red-600 dark:text-red-400"}`}>
                  {!isSuccess && "• "}{err}
                </li>
              ))}
            </ul>
          </Card>
        );
      })()}

      {!selCompany ? (
        <Card className="p-8 text-center text-gray-400">Selecione uma empresa para visualizar a hierarquia.</Card>
      ) : loading ? (
        <div className="flex justify-center py-12"><div className="w-7 h-7 border-4 border-[#00694E] border-t-transparent rounded-full animate-spin" /></div>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  {["Nome", "Matrícula", "Cargo", "Nível", "Gestor Direto", "E-mail", ""].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredEmployees.length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-400">{employees.length === 0 ? "Nenhum colaborador encontrado." : "Nenhum colaborador corresponde aos filtros."}</td></tr>}
                {filteredEmployees.map(emp => (
                  <tr key={emp.id} className="border-b border-gray-50 dark:border-gray-700/50 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{emp.name}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{emp.matricula}</td>
                    <td className="px-4 py-3 text-sm text-gray-500 max-w-[140px] truncate">{emp.cargo}</td>
                    <td className="px-4 py-3"><LevelBadge level={emp.level} /></td>
                    <td className="px-4 py-3 text-sm text-gray-500">{emp.manager_name || "—"}</td>
                    <td className="px-4 py-3 text-center">
                      {emp.email ? <span className="text-green-600 text-base" title={emp.email}>✓</span> : <span className="text-gray-300 text-base">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => openEdit(emp)} className="text-xs text-[#00694E] hover:underline dark:text-emerald-400">Editar</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <ModalWrapper open={modal.open} onClose={closeModal} title={modal.item?.id ? "Editar Colaborador" : "Novo Colaborador"}>
        <div className="space-y-4">
          {/* Empresa */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Empresa *</label>
            <select value={(modal.item as any)?.company_id ?? ""}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, company_id: e.target.value, branch_id: "", manager_id: undefined } }))}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100">
              <option value="">Selecione a empresa</option>
              {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          {/* Filial — filtrada pela empresa do form */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Filial *</label>
            <select value={(modal.item as any)?.branch_id ?? ""}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, branch_id: e.target.value } }))}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100">
              <option value="">Selecione a filial</option>
              {modalBranches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
          {[
            { label: "Nome Completo *", key: "name", type: "text", hint: "Como consta no sistema RH." },
            { label: "Cargo", key: "cargo", type: "text" },
            { label: "E-mail corporativo", key: "email", type: "email", hint: "Obrigatório para envio do link de ciência." },
            { label: "CPF *", key: "cpf", type: "text", hint: "Obrigatório para todos. 11 dígitos numéricos (validado)." },
          ].map(f => (
            <div key={f.key}>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">{f.label}</label>
              <input type={f.type} value={(modal.item as any)?.[f.key] ?? ""}
                onChange={e => {
                  const val = f.key === "name" ? e.target.value.toUpperCase() : e.target.value;
                  setModal(m => ({ ...m, item: { ...m.item!, [f.key]: val } }));
                }}
                className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100" />
              {f.hint && <p className="text-xs text-gray-400 mt-0.5">{f.hint}</p>}
            </div>
          ))}
          {/* WhatsApp: só aparece quando não há e-mail corporativo */}
          {!(modal.item as any)?.email?.trim() && (
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">
                WhatsApp <span className="text-xs font-normal text-gray-400">(apenas para quem não tem e-mail)</span>
              </label>
              <input
                type="text" inputMode="numeric"
                value={(modal.item as any)?.whatsapp_phone ?? ""}
                onChange={e => setModal(m => ({ ...m, item: { ...m.item!, whatsapp_phone: e.target.value.replace(/\D/g, "") } }))}
                placeholder="11999998888"
                className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100 font-mono"
              />
              <p className="text-xs text-gray-400 mt-0.5">Somente dígitos — o sistema adiciona o +55 automaticamente. Ex: 11999998888</p>
            </div>
          )}
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Nível *</label>
            <select value={modal.item?.level ?? "administrativo"}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, level: e.target.value } }))}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100">
              <option value="diretoria">Diretoria</option>
              <option value="gerente">Gerente</option>
              <option value="coordenador_supervisor">Coordenador / Supervisor</option>
              <option value="administrativo">Administrativo</option>
              <option value="operacional">Operacional</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Gestor Direto</label>
            <select value={(modal.item as any)?.manager_id ?? ""}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, manager_id: e.target.value || undefined } }))}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100">
              <option value="">Sem gestor direto</option>
              {modalManagers.filter((m: any) => m.id !== modal.item?.id).map((m: any) => (
                <option key={m.id} value={m.id}>{m.name} ({LEVEL_LABELS[m.level] ?? m.level})</option>
              ))}
            </select>
          </div>
          {formErr && <p className="text-sm text-red-600 dark:text-red-400">{formErr}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={handleSave} disabled={saving} className="flex-1 py-2.5 bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold rounded-lg text-sm transition-all disabled:opacity-60">
              {saving ? "Salvando..." : "Salvar"}
            </button>
            <button onClick={closeModal} className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm transition-all">Cancelar</button>
          </div>
          {modal.item?.id && (
            <div className="pt-1 border-t border-gray-100 dark:border-gray-700">
              <button onClick={handleDeactivate} disabled={saving}
                className="w-full py-2 text-xs font-semibold text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-all disabled:opacity-50">
                🗑 Desativar colaborador
              </button>
            </div>
          )}
        </div>
      </ModalWrapper>
    </div>
  );
}

// ─── Tab Gestão RH ────────────────────────────────────────────────────────────

function TabGestaoRH({ companies }: { companies: any[] }) {
  const { token, user } = useAuth();
  const [list, setList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ status: "", company_id: "", search: "" });
  const [, setCycleOpen] = useState(true);
  const [calibModal, setCalibModal] = useState<{ open: boolean; item: any | null }>({ open: false, item: null });
  const [calibDetail, setCalibDetail] = useState<any>(null);
  const [calibDetailLoading, setCalibDetailLoading] = useState(false);
  // Map: indicator_id → { new_score: string, justification: string }
  const [calibEdits, setCalibEdits] = useState<Record<string, { new_score: string; justification: string }>>({});
  const [calibNotes, setCalibNotes] = useState("");
  const [calibErr, setCalibErr] = useState("");
  const [calibSaving, setCalibSaving] = useState(false);
  const [resetModal, setResetModal] = useState(false);
  const [resetConfirm, setResetConfirm] = useState("");
  const [resetting, setResetting] = useState(false);

  // Nova Avaliação / Nova Auto-Avaliação — loading por colaborador
  const [novaAvalFor,     setNovaAvalFor]     = useState<string | null>(null);
  const [novaSelfAvalFor, setNovaSelfAvalFor] = useState<string | null>(null);

  // Link presencial (copy)
  const [copiedLink, setCopiedLink] = useState<string | null>(null);

  // Envio de e-mail de auto-avaliação individual

  // Ver Avaliação (leitura — gestor + auto-aval)
  const [viewModal, setViewModal] = useState<{ open: boolean; item: any | null }>({ open: false, item: null });
  const [viewDetail, setViewDetail] = useState<any>(null);
  const [viewDetailLoading, setViewDetailLoading] = useState(false);
  const [viewDetailNotFound, setViewDetailNotFound] = useState(false);

  // Filtros client-side de calibragem/ciência (não disparam reload da lista)
  const [calibFilter, setCalibFilter] = useState<"" | "yes" | "no">("");
  const [ackFilter, setAckFilter] = useState<"" | "yes" | "no">("");

  useEffect(() => {
    apiFetch<any>("/api/performance/admin/cycle/status", { token })
      .then(s => setCycleOpen(s?.is_open ?? true)).catch(() => {});
  }, [token]);

  function loadList() {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    if (filters.company_id) params.set("company_id", filters.company_id);
    if (filters.search) params.set("search", filters.search);
    apiFetch<any[]>(`/api/performance/admin/evaluations?${params}`, { token })
      .then(setList).catch(() => setList([]))
      .finally(() => setLoading(false));
  }
  useEffect(() => { loadList(); }, [token, filters]);

  const visibleList = list.filter(ev =>
    (calibFilter === "" || (calibFilter === "yes" ? ev.calibrated : !ev.calibrated)) &&
    (ackFilter === "" || (ackFilter === "yes" ? ev.acknowledged : !ev.acknowledged))
  );

  function openCalib(item: any) {
    if (!item?.id) return;
    setCalibModal({ open: true, item });
    setCalibEdits({});
    setCalibNotes("");
    setCalibErr("");
    setCalibDetail(null);
    setCalibDetailLoading(true);
    apiFetch<any>(`/api/performance/admin/evaluations/${item.id}/detail`, { token })
      .then(d => setCalibDetail(d))
      .catch(() => setCalibErr("Erro ao carregar detalhes da avaliação."))
      .finally(() => setCalibDetailLoading(false));
  }

  function openView(item: any) {
    setViewModal({ open: true, item });
    setViewDetail(null);
    setViewDetailNotFound(false);
    setViewDetailLoading(true);
    apiFetch<any>(`/api/performance/admin/evaluations/detail?employee_id=${item.employee_id}`, { token })
      .then(d => setViewDetail(d))
      .catch((e: any) => { if (e instanceof ApiError && e.status === 404) setViewDetailNotFound(true); })
      .finally(() => setViewDetailLoading(false));
  }

  function setCalibScore(indId: string, value: string) {
    setCalibEdits(prev => ({ ...prev, [indId]: { ...(prev[indId] || { justification: "" }), new_score: value } }));
  }

  function setCalibJust(indId: string, value: string) {
    setCalibEdits(prev => ({ ...prev, [indId]: { ...(prev[indId] || { new_score: "" }), justification: value } }));
  }

  function handleKeepAllScores() {
    if (!calibDetail?.indicators) return;
    const next: Record<string, { new_score: string; justification: string }> = {};
    for (const ind of calibDetail.indicators) {
      next[ind.id] = {
        new_score: String(ind.manager_score),
        justification: "Nota mantida pelo RH — aderência ≥ 80% entre avaliação e auto-avaliação.",
      };
    }
    setCalibEdits(next);
  }

  async function handleCalibrate() {
    // Coletar apenas indicadores com score preenchido (alterados)
    const items = Object.entries(calibEdits)
      .filter(([, v]) => v.new_score !== "")
      .map(([indicator_id, v]) => ({
        indicator_id,
        new_score: parseFloat(v.new_score),
        justification: v.justification,
      }));

    if (items.length === 0) { setCalibErr("Altere ao menos um indicador antes de salvar."); return; }
    for (const it of items) {
      if (isNaN(it.new_score) || it.new_score < 1 || it.new_score > 5) {
        setCalibErr(`Nota inválida — deve ser entre 1 e 5.`); return;
      }
      if (!it.justification.trim()) {
        const ind = calibDetail?.indicators?.find((i: any) => i.id === it.indicator_id);
        setCalibErr(`Justificativa obrigatória para: ${ind?.name || it.indicator_id}`); return;
      }
    }
    setCalibSaving(true); setCalibErr("");
    try {
      await apiFetch(`/api/performance/admin/evaluations/${calibModal.item?.id}/calibrate`, {
        token, method: "POST", json: { items, notes: calibNotes || null }
      });
      setCalibModal({ open: false, item: null }); loadList();
    } catch (e: any) { setCalibErr(e instanceof ApiError ? e.message : "Erro ao calibrar."); }
    finally { setCalibSaving(false); }
  }

  async function handleNewEvaluation(employeeId: string) {
    setNovaAvalFor(employeeId);
    try {
      await apiFetch(`/api/performance/admin/employees/${employeeId}/new-evaluation`, {
        token, method: "POST", json: { justification: "Solicitado pelo RH" }
      });
      loadList();
    } catch (e: any) { alert(e instanceof ApiError ? e.message : "Erro ao criar nova avaliação."); }
    finally { setNovaAvalFor(null); }
  }

  async function handleNewSelfEvaluation(employeeId: string) {
    setNovaSelfAvalFor(employeeId);
    try {
      await apiFetch(`/api/performance/admin/employees/${employeeId}/new-self-evaluation`, {
        token, method: "POST", json: { justification: "Solicitado pelo RH" }
      });
      loadList();
    } catch (e: any) { alert(e instanceof ApiError ? e.message : "Erro ao criar nova auto-avaliação."); }
    finally { setNovaSelfAvalFor(null); }
  }

  function handleCopyPresentialLink() {
    const url = `${window.location.origin}/auto-avaliacao-presencial`;
    navigator.clipboard.writeText(url).then(() => {
      setCopiedLink(url);
      setTimeout(() => setCopiedLink(null), 2500);
    }).catch(() => {});
  }

  async function handleExportCSV() {
    try {
      const params = new URLSearchParams();
      if (filters.status) params.set("status_filter", filters.status);
      if (filters.company_id) params.set("company_id", filters.company_id);
      const res = await fetch(`/api/performance/admin/evaluations/export?${params}`, { headers: { Authorization: `Bearer ${token}` } });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "avaliacoes.xlsx"; a.click();
      URL.revokeObjectURL(url);
    } catch {}
  }

  async function handleReset() {
    if (resetConfirm !== "CONFIRMAR") return;
    setResetting(true);
    try { await apiFetch("/api/performance/admin/reset", { token, method: "POST" }); setResetModal(false); setResetConfirm(""); loadList(); } catch {}
    setResetting(false);
  }

  return (
    <div className="space-y-4">

      {/* ── Links para páginas presenciais (para distribuir aos colaboradores) ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {[
          { icon: "📋", title: "Ciência Presencial", desc: "Colaboradores consultam e registram ciência da avaliação via CPF.", href: "/ciencia-presencial" },
          { icon: "✏️", title: "Auto-Avaliação Presencial", desc: "Colaboradores preenchem a auto-avaliação via CPF (sem precisar de e-mail).", href: "/auto-avaliacao-presencial" },
        ].map(link => (
          <div key={link.href} className="bg-[#E6F4F0] dark:bg-[#00694E]/10 border border-[#00694E]/30 dark:border-[#00694E]/30 rounded-xl p-4 flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-[#00694E]/10 dark:bg-[#00694E]/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-lg">{link.icon}</span>
              </div>
              <div>
                <p className="text-sm font-semibold text-[#00694E] dark:text-emerald-300">{link.title}</p>
                <p className="text-xs text-[#00694E]/70 dark:text-emerald-400/70 mt-0.5">{link.desc}</p>
                <p className="text-xs text-gray-400 mt-1 font-mono">jarvis.voetur.com.br{link.href}</p>
              </div>
            </div>
            <a href={link.href} target="_blank" rel="noopener noreferrer"
              className="flex-shrink-0 inline-flex items-center gap-1 px-3 py-1.5 bg-[#00694E] hover:bg-[#004F3A] text-white text-xs font-semibold rounded-lg transition-all">
              Abrir
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
              </svg>
            </a>
          </div>
        ))}
      </div>

      <Card className="p-4 flex flex-wrap gap-3 items-end">
        <input type="text" placeholder="Buscar colaborador..." value={filters.search}
          onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-800 dark:text-gray-200 w-56" />
        <select value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-800 dark:text-gray-200">
          <option value="">Todos os status</option>
          <option value="pending">Pendente</option>
          <option value="completed">Avaliado</option>
        </select>
        <select value={calibFilter} onChange={e => setCalibFilter(e.target.value as "" | "yes" | "no")}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-800 dark:text-gray-200">
          <option value="">Calibragem: Todas</option>
          <option value="yes">Calibradas</option>
          <option value="no">Não calibradas</option>
        </select>
        <select value={ackFilter} onChange={e => setAckFilter(e.target.value as "" | "yes" | "no")}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-800 dark:text-gray-200">
          <option value="">Ciência: Todas</option>
          <option value="yes">Ciência dada</option>
          <option value="no">Ciência pendente</option>
        </select>
        <select value={filters.company_id} onChange={e => setFilters(f => ({ ...f, company_id: e.target.value }))}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-800 dark:text-gray-200">
          <option value="">Todas as empresas</option>
          {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <div className="flex-1" />
        <button onClick={handleExportCSV} className="px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 text-sm font-semibold rounded-lg transition-all">⬇ Exportar XLSX</button>
      </Card>

      <Card>
        {loading ? (
          <div className="flex justify-center py-12"><div className="w-7 h-7 border-4 border-[#00694E] border-t-transparent rounded-full animate-spin" /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px]">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  {["Colaborador", "Gestor", "Nota Final", "Avaliação", "Auto-Aval.", "Calibragem", "Ciência", "Ações"].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleList.length === 0 && <tr><td colSpan={8} className="px-4 py-8 text-center text-sm text-gray-400">Nenhuma avaliação encontrada.</td></tr>}
                {visibleList.map(ev => (
                  <tr key={ev.employee_id} className="border-b border-gray-50 dark:border-gray-700/50 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{ev.employee_name}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{ev.evaluator_name}</td>
                    <td className="px-4 py-3 text-sm font-bold text-blue-700 dark:text-blue-400">{ev.final_score != null ? ev.final_score.toFixed(2) : "—"}</td>
                    <td className="px-4 py-3">
                      <Badge color={ev.status === "completed" ? "blue" : "gray"}>
                        {ev.status === "completed" ? "Avaliado" : "Pendente"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      {ev.self_eval_status === "completed"
                        ? <Badge color="green">✅ Concluída</Badge>
                        : ev.self_eval_status === "pending"
                        ? <Badge color="amber">⏳ Pendente</Badge>
                        : <Badge color="red">Não enviada</Badge>}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {ev.calibrated
                        ? <Badge color="violet">🎯 Calibrado</Badge>
                        : <Badge color="gray">—</Badge>}
                      {ev.calibrated && ev.calibrated_at && (
                        <p className="text-[10px] text-gray-400 mt-0.5">{new Date(ev.calibrated_at).toLocaleDateString("pt-BR")}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {ev.acknowledged
                        ? <Badge color="green">✅ Ciente</Badge>
                        : <Badge color="gray">Pendente</Badge>}
                      {ev.acknowledged && ev.acknowledged_at && (
                        <p className="text-[10px] text-gray-400 mt-0.5">
                          {new Date(ev.acknowledged_at).toLocaleDateString("pt-BR")}
                          {ev.acknowledged_via === "presencial" ? " · presencial" : ev.acknowledged_via === "email" ? " · e-mail" : ""}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1.5 items-center">
                        {/* Ver Avaliação */}
                        <button onClick={() => openView(ev)}
                          title="Ver avaliação do gestor e auto-avaliação"
                          className="text-xs font-semibold px-2.5 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-800 transition-all">
                          👁️ Ver
                        </button>
                        {/* Calibrar */}
                        <button
                          onClick={() => ev.id ? openCalib(ev) : alert("Avaliação do gestor ainda não foi submetida.")}
                          title="Calibrar nota"
                          className="text-xs font-semibold px-2.5 py-1 rounded bg-violet-100 text-violet-700 hover:bg-violet-200 border border-violet-200 dark:bg-violet-900/30 dark:text-violet-400 dark:border-violet-800 transition-all">
                          Calibrar
                        </button>
                        {/* Ciência Presencial */}
                        <a href="/ciencia-presencial" target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-green-50 hover:bg-green-100 text-green-700 rounded border border-green-200 dark:bg-green-900/20 dark:text-green-400 dark:border-green-800 transition-all">
                          📋 Ciência
                        </a>
                        {/* Nova Avaliação — cria token + envia e-mail ao gestor */}
                        <button
                          onClick={() => handleNewEvaluation(ev.employee_id)}
                          disabled={novaAvalFor === ev.employee_id}
                          title="Criar nova avaliação e enviar e-mail ao gestor"
                          className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-800 transition-all disabled:opacity-60">
                          {novaAvalFor === ev.employee_id
                            ? <span className="w-3 h-3 border-2 border-amber-400/30 border-t-amber-600 rounded-full animate-spin inline-block" />
                            : "🔄"}
                          Nova Aval.
                        </button>
                        {/* Nova Auto-Avaliação — cria token + envia e-mail ao colaborador */}
                        <button
                          onClick={() => handleNewSelfEvaluation(ev.employee_id)}
                          disabled={novaSelfAvalFor === ev.employee_id}
                          title="Criar nova auto-avaliação e enviar e-mail ao colaborador"
                          className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded bg-violet-50 text-violet-700 hover:bg-violet-100 border border-violet-200 dark:bg-violet-900/20 dark:text-violet-400 dark:border-violet-800 transition-all disabled:opacity-60">
                          {novaSelfAvalFor === ev.employee_id
                            ? <span className="w-3 h-3 border-2 border-violet-400/30 border-t-violet-600 rounded-full animate-spin inline-block" />
                            : "✏️"}
                          Nova Auto-Aval.
                        </button>
                        {/* Link presencial */}
                        <button
                          onClick={handleCopyPresentialLink}
                          title="Copiar link presencial de auto-avaliação para enviar via WhatsApp"
                          className="text-xs font-semibold px-2.5 py-1 rounded bg-gray-50 text-gray-600 hover:bg-gray-100 border border-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-700 transition-all">
                          {copiedLink ? "✓ Copiado!" : "🔗 Link Presencial"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {user?.role === "admin" && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-5">
          <h3 className="text-sm font-bold text-red-700 dark:text-red-400 mb-1">Zona de Perigo — Reset</h3>
          <p className="text-xs text-red-600 dark:text-red-400 mb-3">Remove todas as avaliações, tokens e ciências do ciclo atual. Irreversível.</p>
          <button onClick={() => setResetModal(true)} className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-bold rounded-lg transition-all">Resetar Ciclo Atual</button>
        </div>
      )}

      {/* ── Modal Ver Avaliação (leitura — gestor + auto-aval) ── */}
      <ModalWrapper open={viewModal.open} onClose={() => setViewModal({ open: false, item: null })} title={`Avaliação — ${viewModal.item?.employee_name ?? ""}`}>
        {viewDetailLoading ? (
          <div className="flex justify-center py-10"><div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" /></div>
        ) : viewDetail ? (
          <div className="space-y-5">
            {/* Cabeçalho resumo */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2.5">
                <p className="text-xs text-gray-400 mb-0.5">Colaborador</p>
                <p className="font-semibold text-gray-800 dark:text-gray-100 text-xs leading-tight">{viewDetail.employee?.name ?? "—"}</p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2.5">
                <p className="text-xs text-gray-400 mb-0.5">Avaliador (Gestor)</p>
                <p className="font-semibold text-gray-800 dark:text-gray-100 text-xs leading-tight">{viewDetail.evaluator?.name ?? "—"}</p>
              </div>
              <div className="bg-[#E6F4F0] dark:bg-emerald-900/20 rounded-lg p-2.5">
                <p className="text-xs text-[#00694E] dark:text-emerald-400 mb-0.5">Nota Gestor</p>
                <p className="font-bold text-[#00694E] dark:text-emerald-300 text-lg">{viewDetail.review?.final_score != null ? Number(viewDetail.review.final_score).toFixed(2) : "—"}</p>
              </div>
              <div className="bg-violet-50 dark:bg-violet-900/20 rounded-lg p-2.5">
                <p className="text-xs text-violet-500 dark:text-violet-400 mb-0.5">Nota Auto-Aval.</p>
                <p className="font-bold text-violet-700 dark:text-violet-300 text-lg">{viewDetail.self_eval?.final_score != null ? Number(viewDetail.self_eval.final_score).toFixed(2) : "—"}</p>
              </div>
            </div>

            {/* Card de Aderência Geral */}
            {viewDetail.overall_adherence_index != null && (() => {
              const adh = viewDetail.overall_adherence_index as number;
              const label = viewDetail.overall_adherence_label as string;
              const cfg = label === "alinhado"
                ? { bg: "bg-emerald-50 dark:bg-emerald-900/20", border: "border-emerald-200 dark:border-emerald-800", text: "text-emerald-700 dark:text-emerald-300", badge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300", icon: "✅", labelText: "Alinhado" }
                : label === "atencao"
                ? { bg: "bg-amber-50 dark:bg-amber-900/20", border: "border-amber-200 dark:border-amber-800", text: "text-amber-700 dark:text-amber-300", badge: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300", icon: "⚠️", labelText: "Ponto de atenção" }
                : { bg: "bg-red-50 dark:bg-red-900/20", border: "border-red-200 dark:border-red-800", text: "text-red-700 dark:text-red-300", badge: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300", icon: "🔴", labelText: "Desalinhamento relevante" };
              return (
                <div className={`rounded-lg border p-3 flex items-center gap-4 ${cfg.bg} ${cfg.border}`}>
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-0.5">Aderência Geral</p>
                    <p className={`text-2xl font-bold ${cfg.text}`}>{adh}%</p>
                  </div>
                  <div>
                    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${cfg.badge}`}>{cfg.icon} {cfg.labelText}</span>
                    <p className="text-xs text-gray-400 mt-1">Fórmula: (menor nota ÷ maior nota) × 100</p>
                  </div>
                </div>
              );
            })()}

            {/* Observações lado a lado */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {viewDetail.observations ? (
                <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg border border-gray-200 dark:border-gray-600 p-3">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">📝 Obs. do Gestor</p>
                  <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">{viewDetail.observations}</p>
                </div>
              ) : (
                <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg border border-dashed border-gray-200 dark:border-gray-600 p-3 flex items-center justify-center">
                  <p className="text-xs text-gray-400 italic">Gestor não preencheu observações</p>
                </div>
              )}
              {viewDetail.self_observations ? (
                <div className="bg-violet-50 dark:bg-violet-900/20 rounded-lg border border-violet-200 dark:border-violet-800 p-3">
                  <p className="text-xs font-semibold text-violet-600 uppercase tracking-wide mb-1.5">🔄 Obs. do Colaborador</p>
                  <p className="text-xs text-violet-700 dark:text-violet-300 leading-relaxed whitespace-pre-wrap">{viewDetail.self_observations}</p>
                </div>
              ) : (
                <div className={`rounded-lg border border-dashed p-3 flex items-center justify-center ${viewDetail.self_eval ? "bg-violet-50 dark:bg-violet-900/20 border-violet-200 dark:border-violet-800" : "bg-gray-50 dark:bg-gray-700/40 border-gray-200 dark:border-gray-600"}`}>
                  <p className="text-xs text-gray-400 italic">{viewDetail.self_eval ? "Colaborador não preencheu observações" : "Auto-avaliação não realizada"}</p>
                </div>
              )}
            </div>

            {/* Tabela comparativa por indicador */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Indicadores</p>
              <div className="grid grid-cols-12 gap-1 px-2 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wide border-b border-gray-100 dark:border-gray-700">
                <span className="col-span-5">Indicador</span>
                <span className="col-span-2 text-center">Gestor</span>
                <span className="col-span-2 text-center">Auto-Aval.</span>
                <span className="col-span-3 text-center">% Aderência</span>
              </div>
              <div className="space-y-1 mt-2">
                {viewDetail.indicators?.map((ind: any) => {
                  const adh = ind.adherence_index as number | null;
                  const adhLabel = ind.adherence_label as string | null;
                  const adhCfg = adhLabel === "alinhado"
                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                    : adhLabel === "atencao"
                    ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                    : adhLabel === "desalinhamento"
                    ? "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400"
                    : "bg-gray-100 text-gray-500 dark:bg-gray-700";
                  return (
                    <div key={ind.id} className="grid grid-cols-12 gap-2 items-start rounded-lg px-2 py-2 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors">
                      <div className="col-span-5">
                        <p className="text-xs font-semibold text-gray-800 dark:text-gray-100 leading-tight">{ind.name}</p>
                        {ind.manager_justification && (
                          <p className="text-xs text-gray-400 mt-0.5 italic leading-tight line-clamp-2" title={ind.manager_justification}>"{ind.manager_justification}"</p>
                        )}
                      </div>
                      <div className="col-span-2 text-center">
                        <span className={`text-sm font-bold ${ind.current_score >= 4 ? "text-emerald-600" : ind.current_score <= 2 ? "text-red-500" : "text-gray-700 dark:text-gray-300"}`}>
                          {ind.current_score ?? ind.manager_score}
                        </span>
                        {ind.current_score !== ind.manager_score && (
                          <span className="block text-xs text-gray-400 line-through">{ind.manager_score}</span>
                        )}
                      </div>
                      <div className="col-span-2 text-center">
                        {ind.self_score != null
                          ? <span className={`text-sm font-bold ${ind.self_score >= 4 ? "text-violet-600" : ind.self_score <= 2 ? "text-orange-500" : "text-violet-500"}`}>{ind.self_score}</span>
                          : <span className="text-xs text-gray-300">—</span>}
                      </div>
                      <div className="col-span-3 text-center">
                        {adh != null ? (
                          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${adhCfg}`}>
                            {adh}%
                          </span>
                        ) : <span className="text-xs text-gray-300">—</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Histórico de calibrações */}
            {viewDetail.calibration_history?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Histórico de Calibrações</p>
                {viewDetail.calibration_history.map((c: any, i: number) => (
                  <div key={i} className="border border-gray-100 dark:border-gray-700 rounded-lg p-3 mb-2 text-xs bg-violet-50/30 dark:bg-violet-900/10">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="font-semibold text-gray-700 dark:text-gray-300">🎯 {c.calibrated_by}</span>
                      <span className="text-gray-400">{new Date(c.calibrated_at).toLocaleString("pt-BR")}</span>
                    </div>
                    {c.items?.map((it: any, j: number) => (
                      <div key={j} className="flex items-center gap-2 text-gray-600 dark:text-gray-400 mb-0.5">
                        <span className="font-medium">{it.indicator_name}</span>
                        <span className="text-red-400 line-through">{it.old_score}</span>
                        <span>→</span>
                        <span className="text-emerald-600 font-bold">{it.new_score}</span>
                        {it.justification && <span className="italic text-gray-400">"{it.justification}"</span>}
                      </div>
                    ))}
                    {c.notes && <p className="text-gray-400 mt-1 italic">{c.notes}</p>}
                  </div>
                ))}
              </div>
            )}

            <div className="flex gap-3 pt-1">
              {viewDetail.review?.status !== "pending" && viewModal.item?.id && (
                <button
                  onClick={() => { setViewModal({ open: false, item: null }); openCalib(viewModal.item); }}
                  className="flex-1 py-2.5 bg-violet-100 hover:bg-violet-200 dark:bg-violet-900/30 text-violet-700 dark:text-violet-400 font-semibold rounded-lg text-sm transition-all">
                  Ir para Calibração
                </button>
              )}
              <button onClick={() => setViewModal({ open: false, item: null })}
                className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm">
                Fechar
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-gray-500 text-center py-4">
              {viewDetailNotFound ? "Não há avaliações realizadas para este colaborador." : "Erro ao carregar detalhes."}
            </p>
            <button onClick={() => setViewModal({ open: false, item: null })} className="w-full py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm">Fechar</button>
          </div>
        )}
      </ModalWrapper>

      {/* ── Modal Calibração por indicador ── */}
      <ModalWrapper open={calibModal.open} onClose={() => setCalibModal({ open: false, item: null })} title={`Calibração — ${calibModal.item?.employee_name ?? ""}`}>
        {calibDetailLoading ? (
          <div className="flex justify-center py-10"><div className="w-7 h-7 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" /></div>
        ) : calibDetail ? (
          <div className="space-y-5">
            {/* ── Cabeçalho: mini-cards de métricas ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-gray-50 dark:bg-gray-700/40 rounded-xl p-3 text-center">
                <p className="text-xs text-gray-400 mb-0.5">Avaliador</p>
                <p className="text-xs font-semibold text-gray-700 dark:text-gray-200 leading-tight">{calibDetail.evaluator?.name ?? "—"}</p>
              </div>
              <div className="bg-[#E6F4F0] dark:bg-emerald-900/20 rounded-xl p-3 text-center">
                <p className="text-xs text-[#00694E] dark:text-emerald-400 mb-0.5">Nota Gestor</p>
                <p className="text-xl font-black text-[#00694E] dark:text-emerald-300">{calibModal.item?.final_score != null ? Number(calibModal.item.final_score).toFixed(2) : "—"}</p>
              </div>
              <div className="bg-violet-50 dark:bg-violet-900/20 rounded-xl p-3 text-center">
                <p className="text-xs text-violet-500 dark:text-violet-400 mb-0.5">Auto-Aval.</p>
                <p className="text-xl font-black text-violet-700 dark:text-violet-300">{calibDetail.self_eval?.final_score != null ? Number(calibDetail.self_eval.final_score).toFixed(2) : "—"}</p>
              </div>
              {(() => {
                const adh = calibDetail.overall_adherence_index as number | null;
                const label = calibDetail.overall_adherence_label as string;
                const cfg = adh == null ? null
                  : label === "alinhado" ? { bg: "bg-emerald-50 dark:bg-emerald-900/20", text: "text-emerald-700 dark:text-emerald-300", tag: "Alinhado" }
                  : label === "atencao" ? { bg: "bg-amber-50 dark:bg-amber-900/20", text: "text-amber-700 dark:text-amber-300", tag: "Atenção" }
                  : { bg: "bg-red-50 dark:bg-red-900/20", text: "text-red-700 dark:text-red-300", tag: "Desalinhado" };
                return cfg ? (
                  <div className={`${cfg.bg} rounded-xl p-3 text-center`}>
                    <p className={`text-xs ${cfg.text} mb-0.5`}>Aderência</p>
                    <p className={`text-xl font-black ${cfg.text}`}>{adh}%</p>
                    <p className={`text-[10px] font-semibold ${cfg.text}`}>{cfg.tag}</p>
                  </div>
                ) : <div className="bg-gray-50 dark:bg-gray-700/40 rounded-xl p-3 text-center"><p className="text-xs text-gray-400">Aderência</p><p className="text-xl font-black text-gray-300">—</p></div>;
              })()}
            </div>

            {/* ── Observações ── */}
            {(calibDetail.observations || calibDetail.self_observations) && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {calibDetail.observations && (
                  <div className="bg-gray-50 dark:bg-gray-700/40 rounded-xl border border-gray-200 dark:border-gray-600 p-3">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">📝 Obs. Gestor</p>
                    <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed">{calibDetail.observations}</p>
                  </div>
                )}
                {calibDetail.self_observations && (
                  <div className="bg-violet-50 dark:bg-violet-900/20 rounded-xl border border-violet-200 dark:border-violet-800 p-3">
                    <p className="text-xs font-semibold text-violet-600 uppercase tracking-wide mb-1">🔄 Obs. Colaborador</p>
                    <p className="text-xs text-violet-700 dark:text-violet-300 leading-relaxed">{calibDetail.self_observations}</p>
                  </div>
                )}
              </div>
            )}

            {/* ── Manter todas as notas (alta aderência) ── */}
            {calibDetail.overall_adherence_index != null && calibDetail.overall_adherence_index >= 80 && (
              <button
                type="button"
                onClick={handleKeepAllScores}
                className="w-full py-2.5 rounded-xl border-2 border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 font-semibold text-sm hover:bg-emerald-100 dark:hover:bg-emerald-900/30 transition-all">
                ✅ Manter todas as notas (aderência de {calibDetail.overall_adherence_index}% entre avaliação e auto-avaliação)
              </button>
            )}

            {/* ── Cards de competências ── */}
            <div className="space-y-4">
              {calibDetail.indicators?.map((ind: any) => {
                const edit = calibEdits[ind.id];
                const isChanged = edit?.new_score !== "" && edit?.new_score !== undefined;
                const CALIB_SCORES = [
                  { v: 1, lbl: "1", sub: "NAE", cls: "border-red-400 bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300" },
                  { v: 2, lbl: "2", sub: "APE", cls: "border-amber-400 bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300" },
                  { v: 3, lbl: "3", sub: "AE",  cls: "border-blue-400 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" },
                  { v: 4, lbl: "4", sub: "SE",  cls: "border-emerald-400 bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" },
                  { v: 5, lbl: "5", sub: "EE",  cls: "border-purple-400 bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300" },
                ];
                return (
                  <div key={ind.id} className={`rounded-2xl border-2 transition-all ${isChanged ? "border-violet-300 dark:border-violet-700 bg-violet-50/30 dark:bg-violet-900/10" : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"}`}>
                    {/* Nome + descrição */}
                    <div className="px-4 pt-4 pb-3 border-b border-gray-100 dark:border-gray-700">
                      <p className="text-sm font-bold text-gray-900 dark:text-gray-100">{ind.name}</p>
                      {ind.description && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 leading-relaxed">{ind.description}</p>}
                    </div>
                    {/* Scores atuais */}
                    <div className="px-4 py-3 flex flex-wrap gap-4 text-sm border-b border-gray-100 dark:border-gray-700">
                      <div>
                        <span className="text-xs text-gray-400 block mb-0.5">Gestor</span>
                        <span className="text-base font-bold text-[#00694E] dark:text-emerald-400">{ind.manager_score ?? "—"}</span>
                        {ind.manager_justification && <p className="text-xs text-gray-400 italic mt-0.5">"{ind.manager_justification}"</p>}
                      </div>
                      <div>
                        <span className="text-xs text-gray-400 block mb-0.5">Auto-Aval.</span>
                        <span className="text-base font-bold text-violet-600 dark:text-violet-400">{ind.self_score ?? "—"}</span>
                      </div>
                      {ind.current_score !== ind.manager_score && (
                        <div>
                          <span className="text-xs text-gray-400 block mb-0.5">Calibrado</span>
                          <span className="text-base font-bold text-violet-700">{ind.current_score}</span>
                        </div>
                      )}
                      {ind.adherence_index != null && (
                        <div>
                          <span className="text-xs text-gray-400 block mb-0.5">Aderência</span>
                          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${ind.adherence_label === "alinhado" ? "bg-emerald-100 text-emerald-700" : ind.adherence_label === "atencao" ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-600"}`}>{ind.adherence_index}%</span>
                        </div>
                      )}
                    </div>
                    {/* Seletor de nova nota */}
                    <div className="px-4 py-3">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Nova nota RH <span className="text-gray-400 font-normal normal-case">(atual: {ind.current_score} — clique para alterar)</span></p>
                      <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                        {/* Opção "Manter" */}
                        <button
                          type="button"
                          onClick={() => setCalibScore(ind.id, "")}
                          className={`col-span-3 sm:col-span-5 py-1.5 rounded-lg border-2 text-xs font-semibold transition-all ${!isChanged ? "border-gray-400 bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200" : "border-gray-200 text-gray-400 hover:border-gray-300 bg-white dark:bg-gray-800"}`}>
                          ✓ Manter nota {ind.current_score}
                        </button>
                        {CALIB_SCORES.map(cs => {
                          const sel = edit?.new_score !== undefined && edit?.new_score !== "" && Number(edit?.new_score) === cs.v;
                          return (
                            <button key={cs.v} type="button"
                              onClick={() => setCalibScore(ind.id, String(cs.v))}
                              className={`flex flex-col items-center py-2 px-1 rounded-xl border-2 transition-all text-xs font-semibold ${sel ? cs.cls + " shadow-sm scale-[1.03]" : "border-gray-200 dark:border-gray-600 text-gray-500 hover:border-gray-300 bg-white dark:bg-gray-800"}`}>
                              <span className="text-sm font-bold">{cs.sub} <span className="text-[10px] font-normal opacity-60">({cs.lbl})</span></span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                    {/* Justificativa quando há mudança */}
                    {isChanged && (
                      <div className="px-4 pb-4">
                        <textarea
                          value={edit?.justification ?? ""}
                          onChange={e => setCalibJust(ind.id, e.target.value)}
                          rows={2}
                          placeholder="Justificativa obrigatória para esta alteração *"
                          className="w-full rounded-xl border border-violet-300 dark:border-violet-700 bg-white dark:bg-gray-800 px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-violet-500 text-gray-900 dark:text-gray-100 placeholder-gray-400"
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Notas gerais */}
            <div>
              <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">Observações gerais da calibração (opcional)</label>
              <textarea value={calibNotes} onChange={e => setCalibNotes(e.target.value)} rows={2}
                className="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 text-gray-900 dark:text-gray-100" />
            </div>

            {/* Histórico */}
            {calibDetail.calibration_history?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Histórico de Calibrações</p>
                {calibDetail.calibration_history.map((c: any, i: number) => (
                  <div key={i} className="border border-gray-100 dark:border-gray-700 rounded-xl p-3 mb-2 text-xs bg-gray-50/50 dark:bg-gray-700/20">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="font-semibold text-gray-700 dark:text-gray-300">🎯 {c.calibrated_by}</span>
                      <span className="text-gray-400">{new Date(c.calibrated_at).toLocaleString("pt-BR")}</span>
                    </div>
                    {c.items?.map((it: any, j: number) => (
                      <div key={j} className="flex items-center gap-2 text-gray-600 dark:text-gray-400 mb-0.5 flex-wrap">
                        <span className="font-medium">{it.indicator_name}</span>
                        <span className="text-red-400 line-through">{it.old_score}</span>
                        <span>→</span>
                        <span className="text-emerald-600 font-bold">{it.new_score}</span>
                        {it.justification && <span className="italic text-gray-400">"{it.justification}"</span>}
                      </div>
                    ))}
                    {c.notes && <p className="text-gray-400 mt-1 italic">{c.notes}</p>}
                  </div>
                ))}
              </div>
            )}

            {calibErr && <p className="text-sm text-red-600 dark:text-red-400">{calibErr}</p>}
            <div className="flex gap-3 pt-1">
              <button onClick={handleCalibrate} disabled={calibSaving || Object.keys(calibEdits).filter(k => calibEdits[k].new_score !== "").length === 0}
                className="flex-1 py-2.5 bg-violet-700 hover:bg-violet-800 text-white font-semibold rounded-lg text-sm disabled:opacity-60 transition-all">
                {calibSaving ? "Salvando..." : `Salvar Calibração (${Object.keys(calibEdits).filter(k => calibEdits[k].new_score !== "").length} indicador${Object.keys(calibEdits).filter(k => calibEdits[k].new_score !== "").length !== 1 ? "es" : ""})`}
              </button>
              <button onClick={() => setCalibModal({ open: false, item: null })} className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm">Cancelar</button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {calibErr && <p className="text-sm text-red-600 dark:text-red-400">{calibErr}</p>}
            <button onClick={() => setCalibModal({ open: false, item: null })} className="w-full py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm">Fechar</button>
          </div>
        )}
      </ModalWrapper>


      <ModalWrapper open={resetModal} onClose={() => setResetModal(false)} title="Confirmar Reset">
        <div className="space-y-4">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
            <p className="text-sm text-red-700 dark:text-red-400 font-semibold">Esta ação é irreversível. Todas as avaliações, tokens e ciências do ciclo atual serão removidos.</p>
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">
              Digite <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">CONFIRMAR</code> para prosseguir:
            </label>
            <input type="text" value={resetConfirm} onChange={e => setResetConfirm(e.target.value)}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500 text-gray-900 dark:text-gray-100" />
          </div>
          <div className="flex gap-3">
            <button onClick={handleReset} disabled={resetConfirm !== "CONFIRMAR" || resetting}
              className="flex-1 py-2.5 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg text-sm disabled:opacity-60">
              {resetting ? "Resetando..." : "Confirmar Reset"}
            </button>
            <button onClick={() => setResetModal(false)} className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm">Cancelar</button>
          </div>
        </div>
      </ModalWrapper>
    </div>
  );
}

// ─── Tab Ciclo ─────────────────────────────────────────────────────────────────

function TabCiclo({ companies }: { companies: any[] }) {
  const { token } = useAuth();
  const [cycleStatus, setCycleStatus] = useState<any>(null);
  const [tokens,      setTokens]      = useState<any[]>([]);
  const [history,     setHistory]     = useState<any[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [createModal, setCreateModal] = useState(false);
  const [reopenModal, setReopenModal] = useState(false);
  const [newCycle,    setNewCycle]    = useState({ name: "", period_start: "", period_end: "", company_id: "" });
  const [reopenJust,  setReopenJust]  = useState("");
  const [saving,      setSaving]      = useState(false);
  const [saveErr,     setSaveErr]     = useState("");

  // ── Estado do modal de envio de formulários ──────────────────────────────────
  const [sendModal,  setSendModal]  = useState(false);
  const [sendTarget, setSendTarget] = useState<"all" | string>("all"); // "all" ou token_id
  const [sending,    setSending]    = useState(false);
  const [sendResult, setSendResult] = useState<{ sent: number; no_email: number; created: number } | null>(null);
  const [sendError,  setSendError]  = useState("");

  // ── Estado do modal de envio de auto-avaliações ──────────────────────────────
  const [selfEvalModal,  setSelfEvalModal]  = useState(false);
  const [selfEvalSending, setSelfEvalSending] = useState(false);
  const [selfEvalResult, setSelfEvalResult] = useState<{ sent: number; no_email: number; created: number } | null>(null);
  const [selfEvalError,  setSelfEvalError]  = useState("");
  // Tokens de auto-avaliação
  const [selfEvalTokens, setSelfEvalTokens] = useState<any[]>([]);
  const [resendingSelfEval, setResendingSelfEval] = useState<string | null>(null);
  const [copiedPresencial, setCopiedPresencial] = useState(false);

  // ── Consulta histórica: selecionar um ciclo (atual ou passado) e ver todos
  // os colaboradores avaliados nele, com avaliação/auto-avaliação/calibragem/ciência ──
  const [cycles, setCycles] = useState<any[]>([]);
  const [historyCycleId, setHistoryCycleId] = useState("");
  const [historyList, setHistoryList] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const isViewingHistory = historyCycleId !== "";

  useEffect(() => {
    apiFetch<any[]>("/api/performance/admin/cycles", { token }).then(setCycles).catch(() => {});
  }, [token]);

  useEffect(() => {
    if (!historyCycleId) { setHistoryList([]); return; }
    setHistoryLoading(true);
    apiFetch<any[]>(`/api/performance/admin/evaluations?cycle_id=${historyCycleId}`, { token })
      .then(setHistoryList)
      .catch(() => setHistoryList([]))
      .finally(() => setHistoryLoading(false));
  }, [token, historyCycleId]);

  function handleCopyPresencialLink() {
    const url = `${window.location.origin}/auto-avaliacao-presencial`;
    navigator.clipboard.writeText(url).then(() => {
      setCopiedPresencial(true);
      setTimeout(() => setCopiedPresencial(false), 2500);
    }).catch(() => {});
  }

  function openSendAll() { setSendTarget("all"); setSendResult(null); setSendError(""); setSendModal(true); }
  function openSendOne(tokenId: string) { setSendTarget(tokenId); setSendResult(null); setSendError(""); setSendModal(true); }

  async function loadSelfEvalTokens() {
    try {
      const data = await apiFetch<any[]>("/api/performance/admin/cycle/self-evaluation-tokens", { token });
      setSelfEvalTokens(data || []);
    } catch { /* ignore */ }
  }

  async function handleSendSelfEval() {
    setSelfEvalSending(true); setSelfEvalError("");
    try {
      const r = await apiFetch<any>("/api/performance/admin/cycle/send-self-evaluation-tokens", { token, method: "POST" });
      setSelfEvalResult({ sent: r.sent_emails, no_email: r.no_email_count, created: r.tokens_created });
      await loadSelfEvalTokens();
    } catch (e: any) {
      setSelfEvalError(e?.message || "Erro ao enviar auto-avaliações.");
    } finally {
      setSelfEvalSending(false);
    }
  }

  async function handleResendSelfEval(tokenId: string) {
    setResendingSelfEval(tokenId);
    try {
      await apiFetch(`/api/performance/admin/cycle/self-evaluation-tokens/${tokenId}/resend`, { token, method: "POST" });
      await loadSelfEvalTokens();
    } catch (e: any) {
      alert(e?.message || "Erro ao reenviar auto-avaliação.");
    } finally {
      setResendingSelfEval(null);
    }
  }

  async function handleSendSelfEvalForEmployee(employeeId: string) {
    setResendingSelfEval(employeeId);
    try {
      await apiFetch("/api/performance/admin/cycle/self-evaluation-tokens/send-for-employee", {
        token, method: "POST", json: { employee_id: employeeId },
      });
      await loadSelfEvalTokens();
    } catch (e: any) {
      alert(e?.message || "Erro ao enviar auto-avaliação.");
    } finally {
      setResendingSelfEval(null);
    }
  }

  function load() {
    setLoading(true);
    // Cada promise tem seu próprio fallback — uma falha não cancela as outras
    Promise.all([
      apiFetch<any>("/api/performance/admin/cycle/status", { token }).catch(() => null),
      apiFetch<any[]>("/api/performance/admin/cycle/tokens", { token }).catch(() => []),
      apiFetch<any[]>("/api/performance/admin/cycle/reopen-history", { token }).catch(() => []),
      apiFetch<any[]>("/api/performance/admin/cycle/self-evaluation-tokens", { token }).catch(() => []),
    ]).then(([s, t, h, se]) => {
      setCycleStatus(s);
      setTokens(t || []);
      setHistory(h || []);
      setSelfEvalTokens(se || []);
    }).finally(() => setLoading(false));
  }
  useEffect(() => { load(); }, [token]);

  async function handleCreate() {
    if (!newCycle.name.trim()) { setSaveErr("Nome é obrigatório."); return; }
    if (!newCycle.period_start || !newCycle.period_end) { setSaveErr("Período de início e fim são obrigatórios."); return; }
    if (newCycle.period_end < newCycle.period_start) { setSaveErr("Data de término deve ser após o início."); return; }
    setSaving(true); setSaveErr("");
    try {
      await apiFetch("/api/performance/admin/cycle", {
        token, method: "POST",
        json: { name: newCycle.name, period_start: newCycle.period_start, period_end: newCycle.period_end, company_id: newCycle.company_id || null }
      });
      setCreateModal(false);
      setNewCycle({ name: "", period_start: "", period_end: "", company_id: "" });
      load();
    }
    catch (e: any) { setSaveErr(e instanceof ApiError ? e.message : "Erro inesperado. Tente novamente."); }
    finally { setSaving(false); }
  }

  async function handleOpen() {
    if (!confirm("Abrir o ciclo? Após aberto será possível enviar os formulários de avaliação.")) return;
    try { await apiFetch("/api/performance/admin/cycle/open", { token, method: "POST" }); load(); } catch {}
  }

  async function handleDoSend() {
    setSending(true); setSendError("");
    try {
      if (sendTarget === "all") {
        const r = await apiFetch<any>("/api/performance/admin/cycle/send-tokens", { token, method: "POST" });
        setSendResult({ sent: r.sent_emails, no_email: r.no_email_count, created: r.tokens_created });
      } else {
        await apiFetch(`/api/performance/admin/cycle/tokens/${sendTarget}/resend`, { token, method: "POST" });
        setSendResult({ sent: 1, no_email: 0, created: 0 });
      }
      load();
    } catch (e: any) {
      setSendError(e instanceof ApiError ? e.message : "Erro ao enviar. Tente novamente.");
    } finally {
      setSending(false);
    }
  }

  async function handleClose() {
    if (!confirm("Fechar o ciclo atual? Nenhuma nova avaliação poderá ser enviada.")) return;
    try { await apiFetch("/api/performance/admin/cycle/close", { token, method: "POST" }); load(); } catch {}
  }

  async function handleReopen() {
    if (!reopenJust.trim()) { setSaveErr("Justificativa é obrigatória."); return; }
    setSaving(true); setSaveErr("");
    try {
      await apiFetch("/api/performance/admin/cycle/reopen", { token, method: "POST", json: { justification: reopenJust } });
      setReopenModal(false); setReopenJust(""); load();
    }
    catch (e: any) { setSaveErr(e instanceof ApiError ? e.message : "Erro inesperado. Tente novamente."); }
    finally { setSaving(false); }
  }

  function formatDate(iso: string) {
    try { return new Date(iso).toLocaleString("pt-BR"); } catch { return iso; }
  }

  if (loading) return <div className="flex justify-center py-16"><div className="w-8 h-8 border-4 border-[#00694E] border-t-transparent rounded-full animate-spin" /></div>;

  return (
    <div className="space-y-6">
      <Card className="p-4 flex flex-wrap items-center gap-3">
        <label className="text-xs font-semibold uppercase tracking-widest text-gray-400">Consultar ciclo</label>
        <select value={historyCycleId} onChange={e => setHistoryCycleId(e.target.value)}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-800 dark:text-gray-200">
          <option value="">Ciclo atual (gestão)</option>
          {cycles.map(c => (
            <option key={c.id} value={c.id}>{c.name} — {c.status === "open" ? "aberto" : c.status === "draft" ? "rascunho" : "fechado"}</option>
          ))}
        </select>
        {isViewingHistory && (
          <span className="text-xs text-gray-400">Consulta histórica — somente leitura, sem ações de envio.</span>
        )}
      </Card>

      {isViewingHistory ? (
        <Card>
          {historyLoading ? (
            <div className="flex justify-center py-12"><div className="w-7 h-7 border-4 border-[#00694E] border-t-transparent rounded-full animate-spin" /></div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px]">
                <thead>
                  <tr className="border-b border-gray-100 dark:border-gray-700">
                    {["Colaborador", "Gestor", "Nota Final", "Avaliação", "Auto-Aval.", "Calibragem", "Ciência"].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {historyList.length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-400">Nenhum colaborador avaliado neste ciclo.</td></tr>}
                  {historyList.map(ev => (
                    <tr key={ev.employee_id} className="border-b border-gray-50 dark:border-gray-700/50 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{ev.employee_name}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">{ev.evaluator_name}</td>
                      <td className="px-4 py-3 text-sm font-bold text-blue-700 dark:text-blue-400">{ev.final_score != null ? ev.final_score.toFixed(2) : "—"}</td>
                      <td className="px-4 py-3">
                        <Badge color={ev.status === "completed" ? "blue" : "gray"}>{ev.status === "completed" ? "Avaliado" : "Pendente"}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        {ev.self_eval_status === "completed"
                          ? <Badge color="green">✅ Concluída</Badge>
                          : ev.self_eval_status === "pending"
                          ? <Badge color="amber">⏳ Pendente</Badge>
                          : <Badge color="red">Não enviada</Badge>}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {ev.calibrated ? <Badge color="violet">🎯 Calibrado</Badge> : <Badge color="gray">—</Badge>}
                        {ev.calibrated && ev.calibrated_at && (
                          <p className="text-[10px] text-gray-400 mt-0.5">{new Date(ev.calibrated_at).toLocaleDateString("pt-BR")}</p>
                        )}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {ev.acknowledged ? <Badge color="green">✅ Ciente</Badge> : <Badge color="gray">Pendente</Badge>}
                        {ev.acknowledged && ev.acknowledged_at && (
                          <p className="text-[10px] text-gray-400 mt-0.5">
                            {new Date(ev.acknowledged_at).toLocaleString("pt-BR")}
                            {ev.acknowledged_via === "presencial" ? " · presencial" : ev.acknowledged_via === "email" ? " · e-mail" : ""}
                          </p>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : (
      <>
      <Card className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex-1">
            <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-1">Ciclo Atual</p>
            {cycleStatus ? (
              <>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">{cycleStatus.name}</h2>
                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-sm text-gray-500">
                  {cycleStatus.period_start && cycleStatus.period_end && (
                    <span>
                      Período: <strong className="text-gray-700 dark:text-gray-300">
                        {new Date(cycleStatus.period_start + "T12:00:00").toLocaleDateString("pt-BR")}
                        {" até "}
                        {new Date(cycleStatus.period_end + "T12:00:00").toLocaleDateString("pt-BR")}
                      </strong>
                    </span>
                  )}
                  <span>
                    Escopo: <strong className="text-gray-700 dark:text-gray-300">
                      {cycleStatus.company_name ? cycleStatus.company_name : "Todas as empresas"}
                    </strong>
                  </span>
                </div>
              </>
            ) : (
              <h2 className="text-xl font-bold text-gray-500 dark:text-gray-400">Nenhum ciclo ativo</h2>
            )}
          </div>
          {cycleStatus && (
            cycleStatus.status === "open"
              ? <Badge color="green">Aberto</Badge>
              : cycleStatus.status === "draft"
                ? <Badge color="amber">Rascunho</Badge>
                : <Badge color="gray">Fechado</Badge>
          )}
        </div>

        {/* Aviso: ciclo aberto com período encerrado */}
        {cycleStatus?.status === "open" && cycleStatus?.period_end && new Date(cycleStatus.period_end) < new Date() && (
          <div className="mt-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl px-4 py-3 flex items-center gap-3">
            <span className="text-amber-600 text-lg">⚠️</span>
            <p className="text-sm text-amber-800 dark:text-amber-300">
              O período deste ciclo encerrou em <strong>{new Date(cycleStatus.period_end + "T12:00:00").toLocaleDateString("pt-BR")}</strong>.
              Considere fechar o ciclo para impedir novas avaliações.
            </p>
          </div>
        )}

        <div className="flex flex-wrap gap-3 mt-5">
          {!cycleStatus && (
            <button onClick={() => { setCreateModal(true); setSaveErr(""); }}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#00694E] hover:bg-[#004F3A] text-white text-sm font-semibold rounded-xl transition-all shadow-sm">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4"/></svg>
              Criar Ciclo
            </button>
          )}
          {cycleStatus?.status === "draft" && (
            <button onClick={handleOpen}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#00694E] hover:bg-[#004F3A] text-white text-sm font-semibold rounded-xl transition-all shadow-sm">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5 3l14 9-14 9V3z"/></svg>
              Abrir Ciclo
            </button>
          )}
          {cycleStatus?.status === "open" && (
            <button onClick={openSendAll}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#00694E] hover:bg-[#004F3A] text-white text-sm font-bold rounded-xl transition-all shadow-sm">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
              Enviar Avaliações
            </button>
          )}
          {cycleStatus?.status === "open" && (
            <button onClick={() => { setSelfEvalResult(null); setSelfEvalError(""); setSelfEvalModal(true); }}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-violet-600 hover:bg-violet-700 text-white text-sm font-bold rounded-xl transition-all shadow-sm">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
              Enviar Auto-Avaliações
            </button>
          )}
          {cycleStatus?.status === "open" && (
            <button onClick={handleClose}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold rounded-xl transition-all shadow-sm">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
              Fechar Ciclo
            </button>
          )}
          {cycleStatus && (
            <button
              onClick={() => cycleStatus.status === "closed" ? (setReopenModal(true), setSaveErr("")) : undefined}
              disabled={cycleStatus.status !== "closed"}
              title={cycleStatus.status !== "closed" ? "Feche o ciclo primeiro para poder reabri-lo" : "Reabrir ciclo fechado"}
              className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-xl transition-all shadow-sm ${
                cycleStatus.status === "closed"
                  ? "bg-green-700 hover:bg-green-800 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed"
              }`}>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582M20 20v-5h-.581M4.582 9A8 8 0 0120 15m-15.418 0A8 8 0 014 9"/></svg>
              Reabrir Ciclo
            </button>
          )}
        </div>
      </Card>

      {/* ── Lista unificada: Avaliações + Auto-Avaliações ────────────────────── */}
      {(tokens.length > 0 || selfEvalTokens.length > 0) && (() => {
        // Monta lista única: union de employee_ids de ambas as listas
        // API retorna ordenado do mais novo pro mais antigo (created_at desc) — mantém
        // só a primeira ocorrência de cada colaborador (a mais recente), evitando que um
        // token antigo/invalidado sobrescreva o token atual válido.
        const evalByEmp: Record<string, any> = {};
        tokens.forEach(t => { if (!evalByEmp[t.employee_id]) evalByEmp[t.employee_id] = t; });
        const selfByEmp: Record<string, any> = {};
        selfEvalTokens.forEach(st => { if (!selfByEmp[st.employee_id]) selfByEmp[st.employee_id] = st; });
        const allEmpIds = Array.from(new Set([
          ...Object.keys(evalByEmp),
          ...Object.keys(selfByEmp),
        ]));
        const rows = allEmpIds.map(empId => ({
          empId,
          evalTok: evalByEmp[empId] ?? null,
          selfTok: selfByEmp[empId] ?? null,
          name: (evalByEmp[empId]?.employee_name || selfByEmp[empId]?.employee_name || ""),
        })).sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));

        return (
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Formulários do Ciclo</h3>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400">{rows.length} colaborador{rows.length !== 1 ? "es" : ""}</span>
                <span className="text-xs text-[#00694E] font-semibold">
                  {Object.values(evalByEmp).filter((t: any) => t.status === "completed").length}/{Object.keys(evalByEmp).length} aval.
                </span>
                <span className="text-xs text-violet-600 font-semibold">
                  {Object.values(selfByEmp).filter((st: any) => st.status === "completed").length}/{Object.keys(selfByEmp).length} auto-aval.
                </span>
              </div>
            </div>
            <Card>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px]">
                  <thead>
                    <tr className="border-b border-gray-100 dark:border-gray-700">
                      {["Colaborador", "Avaliador (Gestor)", "Status Aval.", "Status Auto-Aval.", "Enviado em", "Ações"].map(h => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(({ empId, evalTok, selfTok, name }) => (
                      <tr key={empId} className="border-b border-gray-50 dark:border-gray-700/50 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{name || "—"}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">{evalTok?.evaluator_name ?? <span className="text-gray-300">—</span>}</td>
                        <td className="px-4 py-3">
                          {evalTok ? (
                            <Badge color={evalTok.status === "completed" ? "green" : evalTok.status === "invalidated" ? "red" : "gray"}>
                              {evalTok.status === "completed" ? "Concluído" : evalTok.status === "invalidated" ? "Inválido" : "Pendente"}
                            </Badge>
                          ) : <span className="text-xs text-gray-300">—</span>}
                        </td>
                        <td className="px-4 py-3">
                          {selfTok ? (
                            <Badge color={selfTok.status === "completed" ? "green" : selfTok.status === "invalidated" ? "red" : "violet"}>
                              {selfTok.status === "completed" ? "Concluída" : selfTok.status === "invalidated" ? "Inválida" : "Pendente"}
                            </Badge>
                          ) : <span className="text-xs text-gray-400 italic">não enviada</span>}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {evalTok?.sent_at ? formatDate(evalTok.sent_at) : selfTok?.sent_at ? formatDate(selfTok.sent_at) : "—"}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2 flex-wrap">
                            {/* Botão reenviar avaliação do gestor */}
                            {evalTok && evalTok.status !== "completed" && evalTok.status !== "invalidated" && cycleStatus?.status === "open" && (
                              evalTok.has_email ? (
                                <button onClick={() => openSendOne(evalTok.id)}
                                  title={evalTok.resend_count > 0 ? `Reenviar avaliação (${evalTok.resend_count}x)` : "Enviar formulário de avaliação"}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-[#E6F4F0] hover:bg-[#CCE8E0] text-[#00694E] dark:bg-[#00694E]/20 dark:hover:bg-[#00694E]/30 dark:text-emerald-300 rounded-lg transition-all border border-[#00694E]/30">
                                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                                  </svg>
                                  {evalTok.resend_count > 0 ? `Aval. (${evalTok.resend_count}×)` : "Aval."}
                                </button>
                              ) : <span className="text-xs text-gray-400 italic">sem e-mail</span>
                            )}
                            {/* Botão enviar/reenviar auto-avaliação */}
                            {cycleStatus?.status === "open" && selfTok?.status !== "completed" && selfTok?.status !== "invalidated" && (
                              selfTok ? (
                                <button onClick={() => handleResendSelfEval(selfTok.id)}
                                  disabled={resendingSelfEval === selfTok.id}
                                  title={selfTok.resend_count > 0 ? `Reenviar auto-avaliação (${selfTok.resend_count}x)` : "Reenviar link de auto-avaliação"}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-violet-50 hover:bg-violet-100 text-violet-700 dark:bg-violet-900/20 dark:hover:bg-violet-900/30 dark:text-violet-300 rounded-lg transition-all border border-violet-200 dark:border-violet-800 disabled:opacity-60">
                                  {resendingSelfEval === selfTok.id
                                    ? <span className="w-3.5 h-3.5 border-2 border-violet-400/30 border-t-violet-600 rounded-full animate-spin" />
                                    : <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>}
                                  {selfTok.resend_count > 0 ? `Auto (${selfTok.resend_count}×)` : "Auto-Aval."}
                                </button>
                              ) : cycleStatus?.status === "open" ? (
                                <button onClick={() => handleSendSelfEvalForEmployee(empId)}
                                  disabled={resendingSelfEval === empId}
                                  title="Criar e enviar link de auto-avaliação"
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-violet-50 hover:bg-violet-100 text-violet-700 dark:bg-violet-900/20 dark:hover:bg-violet-900/30 dark:text-violet-300 rounded-lg transition-all border border-violet-200 dark:border-violet-800 disabled:opacity-60">
                                  {resendingSelfEval === empId
                                    ? <span className="w-3.5 h-3.5 border-2 border-violet-400/30 border-t-violet-600 rounded-full animate-spin" />
                                    : <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>}
                                  Auto-Aval.
                                </button>
                              ) : null
                            )}
                            {/* Link presencial — para colaboradores sem e-mail */}
                            {!(evalTok?.has_email || selfTok?.has_email) && (
                              <button onClick={handleCopyPresencialLink}
                                title="Copiar link de auto-avaliação presencial para enviar via WhatsApp"
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold bg-gray-50 hover:bg-gray-100 text-gray-600 dark:bg-gray-800 dark:hover:bg-gray-700 dark:text-gray-400 rounded-lg transition-all border border-gray-200 dark:border-gray-700">
                                {copiedPresencial ? "✓ Copiado!" : "🔗 Link Presencial"}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        );
      })()}

      {/* ── Histórico de reaberturas ─────────────────────────────────────────── */}
      {history.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Histórico de Reaberturas</h3>
          <Card>
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  {["Data", "Usuário", "Justificativa"].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.map((h: any, i: number) => (
                  <tr key={i} className="border-b border-gray-50 dark:border-gray-700/50 last:border-0">
                    <td className="px-4 py-3 text-sm text-gray-500">{formatDate(h.created_at)}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{h.user_name}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{h.justification}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}
      </>
      )}

      {/* ── Modal: Enviar Formulários ─────────────────────────────────────────── */}
      <ModalWrapper
        open={sendModal}
        onClose={() => { if (!sending) setSendModal(false); }}
        title={sendTarget === "all" ? "Enviar Formulários de Avaliação" : "Reenviar Formulário"}
      >
        {!sendResult ? (
          <div className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
              {sendTarget === "all"
                ? "Será criado e enviado um formulário individual por e-mail para cada gestor/coordenador com avaliações pendentes neste ciclo."
                : "Um novo e-mail com o formulário de avaliação será reenviado para o avaliador responsável."}
            </p>
            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-3">
              <p className="text-xs text-amber-700 dark:text-amber-400 leading-relaxed">
                ⚠️ Avaliadores que já concluíram a avaliação não receberão novo e-mail.
                {sendTarget === "all" && " Gestores sem e-mail corporativo cadastrado também serão ignorados."}
              </p>
            </div>
            {sendError && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3">
                <p className="text-sm text-red-700 dark:text-red-300">{sendError}</p>
              </div>
            )}
            <div className="flex gap-3 pt-1">
              <button onClick={() => setSendModal(false)} disabled={sending}
                className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-xl text-sm hover:bg-gray-200 dark:hover:bg-gray-600 transition-all">
                Cancelar
              </button>
              <button onClick={handleDoSend} disabled={sending}
                className="flex-[2] py-2.5 bg-[#00694E] hover:bg-[#004F3A] disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white disabled:text-gray-400 font-bold rounded-xl text-sm transition-all">
                {sending ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"/>
                    Enviando…
                  </span>
                ) : "Confirmar Envio"}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Resultado */}
            <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-2xl p-6 text-center">
              <div className="w-14 h-14 bg-green-100 dark:bg-green-800/50 rounded-full flex items-center justify-center mx-auto mb-3">
                <svg className="w-7 h-7 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                </svg>
              </div>
              <p className="text-3xl font-black text-green-700 dark:text-green-400">{sendResult.sent}</p>
              <p className="text-sm text-green-600 dark:text-green-400 font-medium">
                e-mail{sendResult.sent !== 1 ? "s" : ""} enviado{sendResult.sent !== 1 ? "s" : ""} com sucesso
              </p>
            </div>
            {sendResult.no_email > 0 && (
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-3">
                <p className="text-xs text-amber-700 dark:text-amber-400">
                  {sendResult.no_email} gestor{sendResult.no_email !== 1 ? "es" : ""} sem e-mail corporativo — não notificado{sendResult.no_email !== 1 ? "s" : ""}.
                </p>
              </div>
            )}
            {sendResult.created > 0 && (
              <p className="text-xs text-gray-400 text-center">{sendResult.created} novo{sendResult.created !== 1 ? "s" : ""} formulário{sendResult.created !== 1 ? "s" : ""} criado{sendResult.created !== 1 ? "s" : ""}.</p>
            )}
            <button onClick={() => setSendModal(false)}
              className="w-full py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-xl text-sm hover:bg-gray-200 dark:hover:bg-gray-600 transition-all">
              Fechar
            </button>
          </div>
        )}
      </ModalWrapper>

      {/* ── Modal: Criar Ciclo ────────────────────────────────────────────────── */}
      <ModalWrapper open={createModal} onClose={() => setCreateModal(false)} title="Criar Novo Ciclo de Avaliação">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Nome do Ciclo *</label>
            <input type="text" value={newCycle.name} onChange={e => setNewCycle(c => ({ ...c, name: e.target.value }))}
              placeholder="Ex: Avaliação 1º Semestre 2026"
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Início do Período *</label>
              <input type="date" value={newCycle.period_start} onChange={e => setNewCycle(c => ({ ...c, period_start: e.target.value }))}
                className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100" />
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Fim do Período *</label>
              <input type="date" value={newCycle.period_end} onChange={e => setNewCycle(c => ({ ...c, period_end: e.target.value }))}
                className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Escopo da Empresa</label>
            <select value={newCycle.company_id} onChange={e => setNewCycle(c => ({ ...c, company_id: e.target.value }))}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100">
              <option value="">Todas as empresas do grupo</option>
              {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <p className="text-xs text-gray-400 mt-0.5">Deixe em branco para aplicar o ciclo a todas as empresas.</p>
          </div>
          {saveErr && <p className="text-sm text-red-600 dark:text-red-400">{saveErr}</p>}
          <div className="flex gap-3">
            <button onClick={handleCreate} disabled={saving}
              className="flex-1 py-2.5 bg-[#00694E] hover:bg-[#004F3A] text-white font-semibold rounded-lg text-sm disabled:opacity-60">
              {saving ? "Criando..." : "Criar Ciclo"}
            </button>
            <button onClick={() => setCreateModal(false)}
              className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm">
              Cancelar
            </button>
          </div>
        </div>
      </ModalWrapper>

      {/* ── Modal: Reabrir ────────────────────────────────────────────────────── */}
      <ModalWrapper open={reopenModal} onClose={() => setReopenModal(false)} title="Reabrir Ciclo">
        <div className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">Informe a justificativa para reabrir o ciclo. Este registro ficará no histórico.</p>
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Justificativa *</label>
            <textarea value={reopenJust} onChange={e => setReopenJust(e.target.value)} rows={3}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00694E] text-gray-900 dark:text-gray-100" />
          </div>
          {saveErr && <p className="text-sm text-red-600 dark:text-red-400">{saveErr}</p>}
          <div className="flex gap-3">
            <button onClick={handleReopen} disabled={saving}
              className="flex-1 py-2.5 bg-green-700 hover:bg-green-800 text-white font-semibold rounded-lg text-sm disabled:opacity-60">
              {saving ? "Reabrindo..." : "Reabrir"}
            </button>
            <button onClick={() => setReopenModal(false)}
              className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm">
              Cancelar
            </button>
          </div>
        </div>
      </ModalWrapper>

      {/* ── Modal: Enviar Auto-Avaliações ────────────────────────────────────── */}
      <ModalWrapper
        open={selfEvalModal}
        onClose={() => { if (!selfEvalSending) setSelfEvalModal(false); }}
        title="Enviar Auto-Avaliações"
      >
        {!selfEvalResult ? (
          <div className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
              Será criado e enviado um link de auto-avaliação por e-mail para cada colaborador ativo com e-mail corporativo cadastrado.
            </p>
            <div className="bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800 rounded-xl p-3">
              <p className="text-xs text-violet-700 dark:text-violet-400 leading-relaxed">
                🔄 Todos os colaboradores ativos (Gerentes, Coordenadores/Supervisores e Administrativo/Operacional) receberão o convite.
                Colaboradores sem e-mail corporativo cadastrado não receberão e-mail, mas o token será criado para controle.
              </p>
            </div>
            {selfEvalError && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3">
                <p className="text-sm text-red-700 dark:text-red-300">{selfEvalError}</p>
              </div>
            )}
            <div className="flex gap-3 pt-1">
              <button onClick={() => setSelfEvalModal(false)} disabled={selfEvalSending}
                className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-xl text-sm hover:bg-gray-200 dark:hover:bg-gray-600 transition-all">
                Cancelar
              </button>
              <button onClick={handleSendSelfEval} disabled={selfEvalSending}
                className="flex-[2] py-2.5 bg-violet-600 hover:bg-violet-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white disabled:text-gray-400 font-bold rounded-xl text-sm transition-all">
                {selfEvalSending ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Enviando…
                  </span>
                ) : "✓ Confirmar Envio"}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800 rounded-2xl p-6 text-center">
              <div className="w-14 h-14 bg-violet-100 dark:bg-violet-800/50 rounded-full flex items-center justify-center mx-auto mb-3">
                <svg className="w-7 h-7 text-violet-600 dark:text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <p className="text-3xl font-black text-violet-700 dark:text-violet-400">{selfEvalResult.sent}</p>
              <p className="text-sm text-violet-600 dark:text-violet-400 font-medium">
                e-mail{selfEvalResult.sent !== 1 ? "s" : ""} enviado{selfEvalResult.sent !== 1 ? "s" : ""} com sucesso
              </p>
            </div>
            {selfEvalResult.no_email > 0 && (
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-3">
                <p className="text-xs text-amber-700 dark:text-amber-400">
                  {selfEvalResult.no_email} colaborador{selfEvalResult.no_email !== 1 ? "es" : ""} sem e-mail corporativo — não notificado{selfEvalResult.no_email !== 1 ? "s" : ""}.
                </p>
              </div>
            )}
            {selfEvalResult.created > 0 && (
              <p className="text-xs text-gray-400 text-center">
                {selfEvalResult.created} novo{selfEvalResult.created !== 1 ? "s" : ""} token{selfEvalResult.created !== 1 ? "s" : ""} criado{selfEvalResult.created !== 1 ? "s" : ""}.
              </p>
            )}
            <button onClick={() => setSelfEvalModal(false)}
              className="w-full py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-xl text-sm hover:bg-gray-200 dark:hover:bg-gray-600 transition-all">
              Fechar
            </button>
          </div>
        )}
      </ModalWrapper>
    </div>
  );
}

// ─── Tab Avaliações (Gerente / Coord-Sup) ─────────────────────────────────────

function TabAvaliacoes() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [subordinates, setSubordinates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [resending, setResending] = useState<string | null>(null);

  function load() {
    setLoading(true);
    apiFetch<any[]>("/api/performance/my/subordinates", { token })
      .then(setSubordinates).catch(() => setSubordinates([]))
      .finally(() => setLoading(false));
  }
  useEffect(() => { load(); }, [token]);

  async function handleResend(employeeId: string) {
    setResending(employeeId);
    try { await apiFetch(`/api/performance/my/subordinates/${employeeId}/resend-ciencia`, { token, method: "POST" }); }
    catch {}
    finally { setResending(null); }
  }

  return (
    <div className="space-y-4">
      <div className="bg-[#E6F4F0] dark:bg-[#00694E]/10 border border-[#00694E]/30 dark:border-[#00694E]/30 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-blue-800 dark:text-blue-200">Colaboradores sem e-mail?</p>
          <p className="text-xs text-[#00694E]/80 dark:text-emerald-400/80 mt-0.5">Use a página de ciência presencial para registrar a ciência no tablet/computador.</p>
        </div>
        <button onClick={() => navigate("/ciencia-presencial")}
          className="px-4 py-2 bg-[#00694E] hover:bg-[#004F3A] text-white text-sm font-semibold rounded-lg transition-all">
          Ciência Presencial →
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><div className="w-7 h-7 border-4 border-[#00694E] border-t-transparent rounded-full animate-spin" /></div>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px]">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  {["Colaborador", "Cargo", "Status Ciclo", "Avaliar", "Ações"].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {subordinates.length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">Nenhum subordinado encontrado.</td></tr>}
                {subordinates.map((sub: any) => (
                  <tr key={sub.employee_id} className="border-b border-gray-50 dark:border-gray-700/50 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{sub.name}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{sub.cargo}</td>
                    <td className="px-4 py-3">
                      <Badge color={sub.cycle_status === "acknowledged" ? "green" : sub.cycle_status === "completed" ? "blue" : sub.cycle_status === "pending" ? "amber" : "gray"}>
                        {sub.cycle_status === "pending" ? "Pendente" : sub.cycle_status === "completed" ? "Avaliado" : sub.cycle_status === "acknowledged" ? "Ciência Dada" : sub.cycle_status ?? "—"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      {sub.evaluation_token && (sub.cycle_status === "pending" || sub.cycle_status === "calibrated") ? (
                        <a href={`/avaliar/${sub.evaluation_token}`} target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs font-semibold px-3 py-1.5 bg-[#00694E] hover:bg-[#004F3A] text-white rounded-lg transition-all">
                          Avaliar →
                        </a>
                      ) : (
                        <span className="text-xs text-gray-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {sub.email && (
                        <button onClick={() => handleResend(sub.employee_id)} disabled={resending === sub.employee_id}
                          className="text-xs text-[#00694E] hover:underline dark:text-emerald-400 disabled:opacity-60">
                          {resending === sub.employee_id ? "Enviando..." : "Reenviar Ciência"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

// ─── Página Principal ─────────────────────────────────────────────────────────

export default function PerformancePage() {
  const { user, token } = useAuth();
  const role = user?.role as AppRole | undefined;

  // ── Empresas carregadas UMA VEZ aqui e compartilhadas por todos os tabs ──────
  const [companies, setCompanies] = useState<any[]>([]);
  useEffect(() => {
    if (!token) return;
    apiFetch<any[]>("/api/performance/admin/companies", { token })
      .then(c => setCompanies(c || []))
      .catch(() => {});
  }, [token]);

  const visibleTabs = TABS.filter(t => role && t.roles.includes(role));
  const [activeTab, setActiveTab] = useState(() => visibleTabs[0]?.id ?? "dashboard");

  useEffect(() => {
    if (!visibleTabs.find(t => t.id === activeTab) && visibleTabs.length > 0) {
      setActiveTab(visibleTabs[0].id);
    }
  }, [role]);

  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Gestão de Desempenho</h1>
        <p className="text-sm text-gray-500 mt-1">Avaliações, indicadores, hierarquia e ciclos de desempenho.</p>
      </div>

      <div className="flex gap-1 flex-wrap mb-6 bg-gray-100 dark:bg-gray-800 p-1 rounded-xl">
        {visibleTabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              activeTab === tab.id
                ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm"
                : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            }`}>
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "dashboard"          && <TabDashboard companies={companies} />}
      {activeTab === "indicadores"        && <TabIndicadores />}
      {activeTab === "hierarquia"         && <TabHierarquia companies={companies} />}
      {activeTab === "gestao-rh"          && <TabGestaoRH   companies={companies} />}
      {activeTab === "ciclo"              && <TabCiclo       companies={companies} />}
      {activeTab === "avaliacoes"         && <TabAvaliacoes />}
    </div>
  );
}
