import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from "recharts";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";

// ─── Tipos ───────────────────────────────────────────────────────────────────

type AppRole = "admin" | "user" | "rh" | "gerente" | "coordenador_supervisor" | "administrativo_operacional";

type TabDef = { id: string; label: string; icon: string; roles: AppRole[] };

const TABS: TabDef[] = [
  { id: "dashboard",   label: "Dashboard",   icon: "📊", roles: ["admin", "rh", "gerente"] },
  { id: "indicadores", label: "Indicadores", icon: "📋", roles: ["admin", "rh"] },
  { id: "hierarquia",  label: "Hierarquia",  icon: "🏢", roles: ["admin", "rh"] },
  { id: "gestao-rh",   label: "Gestão RH",  icon: "⚙️", roles: ["admin", "rh"] },
  { id: "ciclo",       label: "Ciclo",       icon: "🔄", roles: ["admin", "rh"] },
  { id: "avaliacoes",  label: "Avaliações",  icon: "✅", roles: ["gerente", "coordenador_supervisor"] },
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

function StatCard({ label, value, color = "blue" }: { label: string; value: string | number; color?: string }) {
  const colorMap: Record<string, string> = {
    blue: "text-blue-700 dark:text-blue-400",
    green: "text-green-700 dark:text-green-400",
    amber: "text-amber-700 dark:text-amber-400",
    red: "text-red-700 dark:text-red-400",
    violet: "text-violet-700 dark:text-violet-400",
  };
  return (
    <Card className="p-5">
      <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-1">{label}</p>
      <p className={`text-3xl font-bold ${colorMap[color] ?? colorMap.blue}`}>{value}</p>
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

function TabDashboard() {
  const { token } = useAuth();
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ empresa: "", ciclo: "" });
  const [companies, setCompanies] = useState<any[]>([]);
  const [cycles, setCycles] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      apiFetch<any[]>("/api/performance/admin/companies", { token }),
      apiFetch<any[]>("/api/performance/admin/cycles", { token }),
    ]).then(([c, cy]) => {
      setCompanies(c || []);
      setCycles(cy || []);
    }).catch(() => {});
  }, [token]);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.empresa) params.set("company_id", filters.empresa);
    if (filters.ciclo) params.set("cycle_id", filters.ciclo);
    apiFetch<any>(`/api/performance/admin/dashboard?${params}`, { token })
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, [token, filters]);

  return (
    <div className="space-y-6">
      <Card className="p-4 flex flex-wrap gap-3">
        <select
          value={filters.empresa}
          onChange={e => setFilters(f => ({ ...f, empresa: e.target.value }))}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Todas as empresas</option>
          {companies.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select
          value={filters.ciclo}
          onChange={e => setFilters(f => ({ ...f, ciclo: e.target.value }))}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Ciclo atual</option>
          {cycles.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </Card>

      {loading ? (
        <div className="flex justify-center py-16"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : !stats ? (
        <Card className="p-8 text-center text-gray-500">Nenhum dado disponível.</Card>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Total Avaliados" value={stats.total_evaluated ?? "—"} color="blue" />
            <StatCard label="Completude" value={`${stats.completion_pct ?? 0}%`} color="green" />
            <StatCard label="Pendentes Ciência" value={stats.pending_acknowledgment ?? "—"} color="amber" />
            <StatCard label="Sem Avaliação" value={stats.without_evaluation ?? "—"} color="red" />
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
                  <Bar dataKey="avg" fill="#2563eb" radius={[4, 4, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

// ─── Tab Indicadores ──────────────────────────────────────────────────────────

type Indicator = { id: string; name: string; description?: string; active: boolean };

function TabIndicadores() {
  const { token } = useAuth();
  const [list, setList] = useState<Indicator[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<{ open: boolean; item: Partial<Indicator> | null }>({ open: false, item: null });
  const [saving, setSaving] = useState(false);
  const [formErr, setFormErr] = useState("");

  function load() {
    setLoading(true);
    apiFetch<Indicator[]>("/api/performance/indicators", { token })
      .then(setList).catch(() => setList([]))
      .finally(() => setLoading(false));
  }
  useEffect(() => { load(); }, [token]);

  function openCreate() { setModal({ open: true, item: { name: "", description: "", active: true } }); setFormErr(""); }
  function openEdit(it: Indicator) { setModal({ open: true, item: { ...it } }); setFormErr(""); }
  function closeModal() { setModal({ open: false, item: null }); setFormErr(""); }

  async function handleSave() {
    const it = modal.item!;
    if (!it.name?.trim()) { setFormErr("Nome é obrigatório."); return; }
    setSaving(true);
    try {
      if (it.id) {
        await apiFetch(`/api/performance/indicators/${it.id}`, { token, method: "PUT", json: it });
      } else {
        await apiFetch("/api/performance/indicators", { token, method: "POST", json: it });
      }
      closeModal(); load();
    } catch (e: any) { setFormErr(e.message || "Erro ao salvar."); }
    finally { setSaving(false); }
  }

  async function toggleActive(it: Indicator) {
    try {
      await apiFetch(`/api/performance/indicators/${it.id}`, { token, method: "PUT", json: { ...it, active: !it.active } });
      load();
    } catch {}
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-base font-semibold text-gray-700 dark:text-gray-300">Indicadores de Avaliação</h2>
        <button onClick={openCreate} className="px-4 py-2 bg-blue-700 hover:bg-blue-800 text-white text-sm font-semibold rounded-lg transition-all">+ Novo Indicador</button>
      </div>
      <Card>
        {loading ? (
          <div className="flex justify-center py-12"><div className="w-7 h-7 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-700">
                {["Nome", "Descrição", "Status", "Ações"].map(h => (
                  <th key={h} className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 ${h === "Descrição" ? "hidden md:table-cell" : ""}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {list.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-gray-400">Nenhum indicador cadastrado.</td></tr>}
              {list.map(it => (
                <tr key={it.id} className="border-b border-gray-50 dark:border-gray-700/50 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{it.name}</td>
                  <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 hidden md:table-cell max-w-xs truncate">{it.description || "—"}</td>
                  <td className="px-4 py-3"><Badge color={it.active ? "green" : "gray"}>{it.active ? "Ativo" : "Inativo"}</Badge></td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => openEdit(it)} className="text-xs text-blue-600 hover:underline dark:text-blue-400">Editar</button>
                      <button onClick={() => toggleActive(it)} className="text-xs text-gray-500 hover:underline dark:text-gray-400">{it.active ? "Desativar" : "Ativar"}</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <ModalWrapper open={modal.open} onClose={closeModal} title={modal.item?.id ? "Editar Indicador" : "Novo Indicador"}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Nome *</label>
            <input type="text" value={modal.item?.name ?? ""}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, name: e.target.value } }))}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100" />
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Descrição</label>
            <textarea value={modal.item?.description ?? ""}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, description: e.target.value } }))}
              rows={3}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100" />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="active-check" checked={modal.item?.active ?? true}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, active: e.target.checked } }))}
              className="rounded" />
            <label htmlFor="active-check" className="text-sm text-gray-700 dark:text-gray-300">Ativo</label>
          </div>
          {formErr && <p className="text-sm text-red-600 dark:text-red-400">{formErr}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={handleSave} disabled={saving} className="flex-1 py-2.5 bg-blue-700 hover:bg-blue-800 text-white font-semibold rounded-lg text-sm transition-all disabled:opacity-60">
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
  gerente: "Gerente",
  coordenador_supervisor: "Coord./Supervisor",
  administrativo_operacional: "Adm./Operacional",
};

function LevelBadge({ level }: { level: string }) {
  const colors: Record<string, string> = { gerente: "violet", coordenador_supervisor: "blue", administrativo_operacional: "gray" };
  return <Badge color={colors[level] ?? "gray"}>{LEVEL_LABELS[level] ?? level}</Badge>;
}

function TabHierarquia() {
  const { token } = useAuth();
  const [companies, setCompanies] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(false);
  const [selCompany, setSelCompany] = useState("");
  const [selBranch, setSelBranch] = useState("");
  const [modal, setModal] = useState<{ open: boolean; item: Partial<Employee & { active?: boolean }> | null }>({ open: false, item: null });
  const [saving, setSaving] = useState(false);
  const [formErr, setFormErr] = useState("");
  const [importErrors, setImportErrors] = useState<string[]>([]);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    apiFetch<any[]>("/api/performance/admin/companies", { token }).then(setCompanies).catch(() => {});
  }, [token]);

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

  useEffect(() => { loadEmployees(); }, [token, selCompany, selBranch]);

  function openCreate() {
    setModal({ open: true, item: { company_id: selCompany, branch_id: selBranch, level: "administrativo_operacional", active: true } });
    setFormErr("");
  }
  function openEdit(e: Employee) { setModal({ open: true, item: { ...e } }); setFormErr(""); }
  function closeModal() { setModal({ open: false, item: null }); setFormErr(""); }

  async function handleSave() {
    const it = modal.item!;
    if (!it.name?.trim()) { setFormErr("Nome é obrigatório."); return; }
    if (!it.matricula?.trim()) { setFormErr("Matrícula é obrigatória."); return; }
    if (!it.company_id) { setFormErr("Empresa é obrigatória."); return; }
    if (!it.branch_id) { setFormErr("Filial é obrigatória."); return; }
    setSaving(true);
    try {
      if (it.id) {
        await apiFetch(`/api/performance/admin/employees/${it.id}`, { token, method: "PUT", json: it });
      } else {
        await apiFetch("/api/performance/admin/employees", { token, method: "POST", json: it });
      }
      closeModal(); loadEmployees();
    } catch (e: any) { setFormErr(e.message || "Erro ao salvar."); }
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
      } else {
        loadEmployees();
      }
    } catch { setImportErrors(["Erro de conexão."]); }
    finally { setImporting(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  const managersForModal = employees.filter(e => e.level === "gerente" || e.level === "coordenador_supervisor");

  return (
    <div>
      <div className="flex flex-wrap gap-3 items-center mb-4">
        <select value={selCompany} onChange={e => setSelCompany(e.target.value)}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-800 dark:text-gray-200">
          <option value="">Selecione a empresa</option>
          {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {branches.length > 0 && (
          <select value={selBranch} onChange={e => setSelBranch(e.target.value)}
            className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-800 dark:text-gray-200">
            <option value="">Todas as filiais</option>
            {branches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        )}
        <div className="flex-1" />
        {selCompany && (
          <>
            <button onClick={openCreate} className="px-4 py-2 bg-blue-700 hover:bg-blue-800 text-white text-sm font-semibold rounded-lg transition-all">+ Colaborador</button>
            <button onClick={handleDownloadTemplate} className="px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 text-sm font-semibold rounded-lg transition-all">⬇ Template Excel</button>
            <label className={`px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 text-sm font-semibold rounded-lg transition-all cursor-pointer ${importing ? "opacity-60 cursor-not-allowed" : ""}`}>
              {importing ? "Importando..." : "📤 Importar Planilha"}
              <input ref={fileRef} type="file" accept=".xlsx,.xls" onChange={handleImport} className="hidden" disabled={importing} />
            </label>
          </>
        )}
      </div>

      {importErrors.length > 0 && (
        <Card className="p-4 mb-4 border-red-200 dark:border-red-800">
          <p className="text-sm font-semibold text-red-700 dark:text-red-400 mb-2">Erros na importação:</p>
          <ul className="space-y-1">
            {importErrors.map((err, i) => <li key={i} className="text-xs text-red-600 dark:text-red-400">• {err}</li>)}
          </ul>
        </Card>
      )}

      {!selCompany ? (
        <Card className="p-8 text-center text-gray-400">Selecione uma empresa para visualizar a hierarquia.</Card>
      ) : loading ? (
        <div className="flex justify-center py-12"><div className="w-7 h-7 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
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
                {employees.length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-400">Nenhum colaborador encontrado.</td></tr>}
                {employees.map(emp => (
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
                      <button onClick={() => openEdit(emp)} className="text-xs text-blue-600 hover:underline dark:text-blue-400">Editar</button>
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
          {[
            { label: "Nome Completo *", key: "name", type: "text", hint: "Como consta no sistema RH." },
            { label: "Matrícula *", key: "matricula", type: "text", hint: "Apenas números." },
            { label: "Cargo", key: "cargo", type: "text" },
            { label: "E-mail corporativo", key: "email", type: "email", hint: "Opcional — usado para envio do link de ciência." },
          ].map(f => (
            <div key={f.key}>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">{f.label}</label>
              <input type={f.type} value={(modal.item as any)?.[f.key] ?? ""}
                onChange={e => setModal(m => ({ ...m, item: { ...m.item!, [f.key]: e.target.value } }))}
                className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100" />
              {f.hint && <p className="text-xs text-gray-400 mt-0.5">{f.hint}</p>}
            </div>
          ))}
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Nível *</label>
            <select value={modal.item?.level ?? "administrativo_operacional"}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, level: e.target.value } }))}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100">
              <option value="gerente">Gerente</option>
              <option value="coordenador_supervisor">Coordenador / Supervisor</option>
              <option value="administrativo_operacional">Administrativo / Operacional</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Gestor Direto</label>
            <select value={(modal.item as any)?.manager_id ?? ""}
              onChange={e => setModal(m => ({ ...m, item: { ...m.item!, manager_id: e.target.value || undefined } }))}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100">
              <option value="">Sem gestor direto</option>
              {managersForModal.filter(m => m.id !== modal.item?.id).map(m => (
                <option key={m.id} value={m.id}>{m.name} ({LEVEL_LABELS[m.level] ?? m.level})</option>
              ))}
            </select>
          </div>
          {formErr && <p className="text-sm text-red-600 dark:text-red-400">{formErr}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={handleSave} disabled={saving} className="flex-1 py-2.5 bg-blue-700 hover:bg-blue-800 text-white font-semibold rounded-lg text-sm transition-all disabled:opacity-60">
              {saving ? "Salvando..." : "Salvar"}
            </button>
            <button onClick={closeModal} className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm transition-all">Cancelar</button>
          </div>
        </div>
      </ModalWrapper>
    </div>
  );
}

// ─── Tab Gestão RH ────────────────────────────────────────────────────────────

function TabGestaoRH() {
  const { token, user } = useAuth();
  const [list, setList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ status: "", company_id: "", search: "" });
  const [companies, setCompanies] = useState<any[]>([]);
  const [cycleOpen, setCycleOpen] = useState(true);
  const [calibModal, setCalibModal] = useState<{ open: boolean; item: any | null }>({ open: false, item: null });
  const [calibNota, setCalibNota] = useState("");
  const [calibJust, setCalibJust] = useState("");
  const [calibErr, setCalibErr] = useState("");
  const [calibSaving, setCalibSaving] = useState(false);
  const [resetModal, setResetModal] = useState(false);
  const [resetConfirm, setResetConfirm] = useState("");
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    apiFetch<any>("/api/performance/admin/cycle/status", { token }).then(s => setCycleOpen(s.is_open ?? true)).catch(() => {});
    apiFetch<any[]>("/api/performance/admin/companies", { token }).then(setCompanies).catch(() => {});
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

  function openCalib(item: any) {
    setCalibModal({ open: true, item });
    setCalibNota(item.final_score?.toString() ?? "");
    setCalibJust(""); setCalibErr("");
  }

  async function handleCalibrate() {
    const nota = parseFloat(calibNota);
    if (isNaN(nota) || nota < 0 || nota > 5) { setCalibErr("Nota deve ser entre 0 e 5."); return; }
    if (!calibJust.trim()) { setCalibErr("Justificativa é obrigatória."); return; }
    setCalibSaving(true);
    try {
      await apiFetch(`/api/performance/admin/evaluations/${calibModal.item?.id}/calibrate`, {
        token, method: "POST", json: { new_score: nota, justification: calibJust }
      });
      setCalibModal({ open: false, item: null }); loadList();
    } catch (e: any) { setCalibErr(e.message || "Erro ao calibrar."); }
    finally { setCalibSaving(false); }
  }

  async function handleExportCSV() {
    try {
      const params = new URLSearchParams();
      if (filters.status) params.set("status", filters.status);
      if (filters.company_id) params.set("company_id", filters.company_id);
      const res = await fetch(`/api/performance/admin/evaluations/export?${params}`, { headers: { Authorization: `Bearer ${token}` } });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "avaliacoes.csv"; a.click();
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
      <Card className="p-4 flex flex-wrap gap-3 items-end">
        <input type="text" placeholder="Buscar colaborador..." value={filters.search}
          onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-800 dark:text-gray-200 w-56" />
        <select value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-800 dark:text-gray-200">
          <option value="">Todos os status</option>
          <option value="pending">Pendente</option>
          <option value="completed">Avaliado</option>
          <option value="acknowledged">Ciência dada</option>
          <option value="calibrated">Calibrado</option>
        </select>
        <select value={filters.company_id} onChange={e => setFilters(f => ({ ...f, company_id: e.target.value }))}
          className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-800 dark:text-gray-200">
          <option value="">Todas as empresas</option>
          {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <div className="flex-1" />
        <button onClick={handleExportCSV} className="px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 text-sm font-semibold rounded-lg transition-all">⬇ Exportar CSV</button>
      </Card>

      <Card>
        {loading ? (
          <div className="flex justify-center py-12"><div className="w-7 h-7 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px]">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  {["Colaborador", "Gestor", "Nota Final", "Status", "Ações"].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {list.length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">Nenhuma avaliação encontrada.</td></tr>}
                {list.map(ev => (
                  <tr key={ev.id} className="border-b border-gray-50 dark:border-gray-700/50 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{ev.employee_name}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{ev.evaluator_name}</td>
                    <td className="px-4 py-3 text-sm font-bold text-blue-700 dark:text-blue-400">{ev.final_score != null ? ev.final_score.toFixed(2) : "—"}</td>
                    <td className="px-4 py-3">
                      <Badge color={ev.status === "acknowledged" ? "green" : ev.status === "calibrated" ? "violet" : ev.status === "completed" ? "blue" : "gray"}>
                        {ev.status === "pending" ? "Pendente" : ev.status === "completed" ? "Avaliado" : ev.status === "acknowledged" ? "Ciência Dada" : ev.status === "calibrated" ? "Calibrado" : ev.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => openCalib(ev)} disabled={!cycleOpen}
                        title={!cycleOpen ? "Ciclo fechado — reabra o ciclo para calibrar" : "Calibrar nota"}
                        className={`text-xs font-semibold px-2.5 py-1 rounded transition-all ${cycleOpen ? "bg-violet-100 text-violet-700 hover:bg-violet-200 dark:bg-violet-900/30 dark:text-violet-400" : "bg-gray-100 text-gray-400 cursor-not-allowed dark:bg-gray-800"}`}>
                        Calibrar
                      </button>
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

      <ModalWrapper open={calibModal.open} onClose={() => setCalibModal({ open: false, item: null })} title="Calibração de Nota">
        <div className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Colaborador: <strong>{calibModal.item?.employee_name}</strong><br />
            Nota atual: <strong>{calibModal.item?.final_score?.toFixed(2) ?? "—"}</strong>
          </p>
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Nova Nota (0–5)</label>
            <input type="number" min="0" max="5" step="0.01" value={calibNota} onChange={e => setCalibNota(e.target.value)}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100" />
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Justificativa *</label>
            <textarea value={calibJust} onChange={e => setCalibJust(e.target.value)} rows={3}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100" />
          </div>
          {calibErr && <p className="text-sm text-red-600 dark:text-red-400">{calibErr}</p>}
          <div className="flex gap-3">
            <button onClick={handleCalibrate} disabled={calibSaving} className="flex-1 py-2.5 bg-violet-700 hover:bg-violet-800 text-white font-semibold rounded-lg text-sm disabled:opacity-60">{calibSaving ? "Salvando..." : "Calibrar"}</button>
            <button onClick={() => setCalibModal({ open: false, item: null })} className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm">Cancelar</button>
          </div>
        </div>
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

function TabCiclo() {
  const { token } = useAuth();
  const [cycleStatus, setCycleStatus] = useState<any>(null);
  const [tokens, setTokens] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [createModal, setCreateModal] = useState(false);
  const [reopenModal, setReopenModal] = useState(false);
  const [newCycleName, setNewCycleName] = useState("");
  const [reopenJust, setReopenJust] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState("");

  function load() {
    setLoading(true);
    Promise.all([
      apiFetch<any>("/api/performance/admin/cycle/status", { token }),
      apiFetch<any[]>("/api/performance/admin/cycle/tokens", { token }),
      apiFetch<any[]>("/api/performance/admin/cycle/reopen-history", { token }),
    ]).then(([s, t, h]) => { setCycleStatus(s); setTokens(t || []); setHistory(h || []); })
      .catch(() => {}).finally(() => setLoading(false));
  }
  useEffect(() => { load(); }, [token]);

  async function handleCreate() {
    if (!newCycleName.trim()) { setSaveErr("Nome é obrigatório."); return; }
    setSaving(true); setSaveErr("");
    try { await apiFetch("/api/performance/admin/cycle", { token, method: "POST", json: { name: newCycleName } }); setCreateModal(false); setNewCycleName(""); load(); }
    catch (e: any) { setSaveErr(e.message || "Erro."); }
    finally { setSaving(false); }
  }

  async function handleClose() {
    if (!confirm("Fechar o ciclo atual? Nenhuma nova avaliação poderá ser enviada.")) return;
    try { await apiFetch("/api/performance/admin/cycle/close", { token, method: "POST" }); load(); } catch {}
  }

  async function handleReopen() {
    if (!reopenJust.trim()) { setSaveErr("Justificativa é obrigatória."); return; }
    setSaving(true); setSaveErr("");
    try { await apiFetch("/api/performance/admin/cycle/reopen", { token, method: "POST", json: { justification: reopenJust } }); setReopenModal(false); setReopenJust(""); load(); }
    catch (e: any) { setSaveErr(e.message || "Erro."); }
    finally { setSaving(false); }
  }

  async function handleResendToken(tokenId: string) {
    try { await apiFetch(`/api/performance/admin/cycle/tokens/${tokenId}/resend`, { token, method: "POST" }); load(); } catch {}
  }

  function formatDate(iso: string) {
    try { return new Date(iso).toLocaleString("pt-BR"); } catch { return iso; }
  }

  if (loading) return <div className="flex justify-center py-16"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>;

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-1">Ciclo Atual</p>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">{cycleStatus?.name ?? "Nenhum ciclo ativo"}</h2>
            {cycleStatus?.started_at && <p className="text-sm text-gray-500 mt-0.5">Iniciado em: {formatDate(cycleStatus.started_at)}</p>}
          </div>
          {cycleStatus && (
            cycleStatus.is_open ? <Badge color="green">Aberto</Badge> : <Badge color="gray">Fechado</Badge>
          )}
        </div>
        <div className="flex flex-wrap gap-3 mt-5">
          {!cycleStatus && (
            <button onClick={() => { setCreateModal(true); setSaveErr(""); }} className="px-4 py-2 bg-blue-700 hover:bg-blue-800 text-white text-sm font-semibold rounded-lg transition-all">+ Criar Ciclo</button>
          )}
          {cycleStatus?.is_open && (
            <button onClick={handleClose} className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold rounded-lg transition-all">Fechar Ciclo</button>
          )}
          {cycleStatus && !cycleStatus.is_open && (
            <button onClick={() => { setReopenModal(true); setSaveErr(""); }} className="px-4 py-2 bg-green-700 hover:bg-green-800 text-white text-sm font-semibold rounded-lg transition-all">Reabrir Ciclo</button>
          )}
        </div>
      </Card>

      {tokens.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Tokens de Avaliação</h3>
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[500px]">
                <thead>
                  <tr className="border-b border-gray-100 dark:border-gray-700">
                    {["Avaliador", "Status", "Enviado em", "Ações"].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tokens.map((t: any) => (
                    <tr key={t.id} className="border-b border-gray-50 dark:border-gray-700/50 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{t.evaluator_name}</td>
                      <td className="px-4 py-3"><Badge color={t.status === "completed" ? "green" : t.status === "sent" ? "blue" : "gray"}>{t.status === "completed" ? "Concluído" : t.status === "sent" ? "Enviado" : t.status}</Badge></td>
                      <td className="px-4 py-3 text-sm text-gray-500">{t.sent_at ? formatDate(t.sent_at) : "—"}</td>
                      <td className="px-4 py-3">
                        <button onClick={() => handleResendToken(t.id)} className="text-xs text-blue-600 hover:underline dark:text-blue-400">Reenviar</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

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

      <ModalWrapper open={createModal} onClose={() => setCreateModal(false)} title="Criar Novo Ciclo">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Nome do Ciclo *</label>
            <input type="text" value={newCycleName} onChange={e => setNewCycleName(e.target.value)}
              placeholder="Ex: Avaliação 1º Semestre 2026"
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100" />
          </div>
          {saveErr && <p className="text-sm text-red-600 dark:text-red-400">{saveErr}</p>}
          <div className="flex gap-3">
            <button onClick={handleCreate} disabled={saving} className="flex-1 py-2.5 bg-blue-700 hover:bg-blue-800 text-white font-semibold rounded-lg text-sm disabled:opacity-60">{saving ? "Criando..." : "Criar Ciclo"}</button>
            <button onClick={() => setCreateModal(false)} className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm">Cancelar</button>
          </div>
        </div>
      </ModalWrapper>

      <ModalWrapper open={reopenModal} onClose={() => setReopenModal(false)} title="Reabrir Ciclo">
        <div className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">Informe a justificativa para reabrir o ciclo. Este registro ficará no histórico.</p>
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Justificativa *</label>
            <textarea value={reopenJust} onChange={e => setReopenJust(e.target.value)} rows={3}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100" />
          </div>
          {saveErr && <p className="text-sm text-red-600 dark:text-red-400">{saveErr}</p>}
          <div className="flex gap-3">
            <button onClick={handleReopen} disabled={saving} className="flex-1 py-2.5 bg-green-700 hover:bg-green-800 text-white font-semibold rounded-lg text-sm disabled:opacity-60">{saving ? "Reabrindo..." : "Reabrir"}</button>
            <button onClick={() => setReopenModal(false)} className="flex-1 py-2.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold rounded-lg text-sm">Cancelar</button>
          </div>
        </div>
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
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-blue-800 dark:text-blue-200">Colaboradores sem e-mail?</p>
          <p className="text-xs text-blue-600 dark:text-blue-400 mt-0.5">Use a página de ciência presencial para registrar a ciência no tablet/computador.</p>
        </div>
        <button onClick={() => navigate("/ciencia-presencial")}
          className="px-4 py-2 bg-blue-700 hover:bg-blue-800 text-white text-sm font-semibold rounded-lg transition-all">
          Ciência Presencial →
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><div className="w-7 h-7 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px]">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  {["Colaborador", "Cargo", "Status Ciclo", "E-mail", "Ações"].map(h => (
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
                    <td className="px-4 py-3 text-center">
                      {sub.email ? <span className="text-green-600 text-base" title={sub.email}>✓</span> : <span className="text-gray-300 text-base">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      {sub.email && (
                        <button onClick={() => handleResend(sub.employee_id)} disabled={resending === sub.employee_id}
                          className="text-xs text-blue-600 hover:underline dark:text-blue-400 disabled:opacity-60">
                          {resending === sub.employee_id ? "Enviando..." : "Reenviar Link"}
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
  const { user } = useAuth();
  const role = user?.role as AppRole | undefined;

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

      {activeTab === "dashboard"   && <TabDashboard />}
      {activeTab === "indicadores" && <TabIndicadores />}
      {activeTab === "hierarquia"  && <TabHierarquia />}
      {activeTab === "gestao-rh"   && <TabGestaoRH />}
      {activeTab === "ciclo"       && <TabCiclo />}
      {activeTab === "avaliacoes"  && <TabAvaliacoes />}
    </div>
  );
}
