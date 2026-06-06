import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../../lib/api";
import type { CartoesCliente } from "../../types/cartoes";

interface Props { token: string | null; }

interface ClienteForm { nome: string; cnpj: string; }
const EMPTY: ClienteForm = { nome: "", cnpj: "" };

export default function CartoesClientesTab({ token }: Props) {
  const [clients, setClients] = useState<CartoesCliente[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<ClienteForm>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  function load() {
    setLoading(true);
    apiFetch<CartoesCliente[]>("/api/cards/clients", { token })
      .then(setClients)
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, [token]);

  function openNew() {
    setForm(EMPTY); setEditId(null); setFormError(""); setShowForm(true);
  }

  function openEdit(c: CartoesCliente) {
    setForm({ nome: c.nome, cnpj: c.cnpj ?? "" }); setEditId(c.id); setFormError(""); setShowForm(true);
  }

  async function handleSave() {
    if (!form.nome.trim()) { setFormError("Nome é obrigatório."); return; }
    setSaving(true); setFormError("");
    try {
      if (editId) {
        await apiFetch(`/api/cards/clients/${editId}`, { token, method: "PUT", json: form });
      } else {
        await apiFetch("/api/cards/clients", { token, method: "POST", json: form });
      }
      setShowForm(false); load();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="flex justify-center h-40 items-center"><div className="h-7 w-7 border-4 border-brand-green/30 border-t-brand-green rounded-full animate-spin" /></div>;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Clientes cadastrados</h2>
        <button onClick={openNew} className="flex items-center gap-2 rounded-lg bg-brand-green px-4 py-2 text-sm font-semibold text-white hover:bg-brand-deep">
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Novo Cliente
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
              <th className="px-4 py-3 text-left font-semibold text-gray-600 dark:text-gray-400">Nome</th>
              <th className="px-4 py-3 text-left font-semibold text-gray-600 dark:text-gray-400">CNPJ</th>
              <th className="px-4 py-3 text-left font-semibold text-gray-600 dark:text-gray-400">Status</th>
              <th className="px-4 py-3 text-right font-semibold text-gray-600 dark:text-gray-400">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {clients.length === 0 ? (
              <tr><td colSpan={4} className="px-4 py-10 text-center text-gray-400 dark:text-gray-600">Nenhum cliente cadastrado.</td></tr>
            ) : clients.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{c.nome}</td>
                <td className="px-4 py-3 font-mono text-gray-600 dark:text-gray-400 text-xs">{c.cnpj ?? "—"}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${c.ativo ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"}`}>
                    {c.ativo ? "Ativo" : "Inativo"}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => openEdit(c)} className="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-1 text-xs font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800">
                    Editar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm rounded-xl bg-white dark:bg-gray-900 shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 px-5 py-4">
              <h2 className="font-semibold text-gray-900 dark:text-gray-100">{editId ? "Editar Cliente" : "Novo Cliente"}</h2>
              <button onClick={() => setShowForm(false)} className="h-8 w-8 grid place-items-center rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="px-5 py-4 space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                  Nome <span className="text-red-500">*</span>
                </label>
                <input
                  value={form.nome}
                  onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
                  placeholder="Razão social ou nome fantasia"
                  className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">CNPJ</label>
                <input
                  value={form.cnpj}
                  onChange={(e) => setForm((f) => ({ ...f, cnpj: e.target.value }))}
                  placeholder="00.000.000/0000-00"
                  className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm font-mono text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                />
              </div>
              {formError && <p className="text-sm text-red-600 dark:text-red-400">{formError}</p>}
            </div>
            <div className="flex justify-end gap-3 border-t border-gray-100 dark:border-gray-800 px-5 py-4">
              <button onClick={() => setShowForm(false)} className="rounded-lg border border-gray-200 dark:border-gray-700 px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800">
                Cancelar
              </button>
              <button onClick={handleSave} disabled={saving} className="rounded-lg bg-brand-green px-5 py-2 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-40 flex items-center gap-2">
                {saving && <div className="h-4 w-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />}
                Salvar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
