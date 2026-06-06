import { useEffect, useMemo, useState } from "react";
import { apiFetch, ApiError } from "../../lib/api";
import type { CartaoManagement, CartoesCliente } from "../../types/cartoes";

interface Props { token: string | null; }

interface CardForm {
  cliente_id: string;
  bandeira: string;
  numero: string;
  cvv: string;
  expiracao: string;
  titular: string;
}

const BANDEIRAS = ["VISA", "MASTER", "ELO", "AMEX", "HIPERCARD"];
const EMPTY_FORM: CardForm = { cliente_id: "", bandeira: "VISA", numero: "", cvv: "", expiracao: "", titular: "" };

type SortKey = "bandeira" | "numero_final" | "cliente";
type SortDir = "asc" | "desc";

export default function CartoesGestaoTab({ token }: Props) {
  const [cards, setCards] = useState<CartaoManagement[]>([]);
  const [clients, setClients] = useState<CartoesCliente[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("bandeira");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<CardForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  function load() {
    setLoading(true);
    Promise.all([
      apiFetch<CartaoManagement[]>("/api/cards/management", { token }),
      apiFetch<CartoesCliente[]>("/api/cards/clients", { token }),
    ])
      .then(([c, cl]) => { setCards(c); setClients(cl); })
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, [token]);

  function toggleSort(k: SortKey) {
    if (sortKey === k) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(k); setSortDir("asc"); }
  }

  function SortIcon({ k }: { k: SortKey }) {
    if (sortKey !== k) return <span className="opacity-30">↕</span>;
    return <span>{sortDir === "asc" ? "↑" : "↓"}</span>;
  }

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return cards
      .filter((c) =>
        !q ||
        c.bandeira.toLowerCase().includes(q) ||
        c.numero_final.includes(q) ||
        (c.cards_clientes?.nome ?? "").toLowerCase().includes(q)
      )
      .sort((a, b) => {
        let va = "", vb = "";
        if (sortKey === "bandeira") { va = a.bandeira; vb = b.bandeira; }
        else if (sortKey === "numero_final") { va = a.numero_final; vb = b.numero_final; }
        else { va = a.cards_clientes?.nome ?? ""; vb = b.cards_clientes?.nome ?? ""; }
        return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
      });
  }, [cards, search, sortKey, sortDir]);

  function openNew() {
    setForm(EMPTY_FORM);
    setEditId(null);
    setFormError("");
    setShowForm(true);
  }

  function openEdit(card: CartaoManagement) {
    setForm({ cliente_id: card.cliente_id, bandeira: card.bandeira, numero: "", cvv: "", expiracao: "", titular: "" });
    setEditId(card.id);
    setFormError("");
    setShowForm(true);
  }

  async function handleSave() {
    if (!form.cliente_id || !form.bandeira) { setFormError("Preencha cliente e bandeira."); return; }
    if (!editId && (!form.numero || !form.cvv || !form.expiracao || !form.titular)) {
      setFormError("Preencha todos os campos do cartão."); return;
    }
    setSaving(true); setFormError("");
    try {
      if (editId) {
        await apiFetch(`/api/cards/management/${editId}`, { token, method: "PUT", json: form });
      } else {
        await apiFetch("/api/cards/management", { token, method: "POST", json: form });
      }
      setShowForm(false);
      load();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Erro ao salvar cartão.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivate(id: string) {
    if (!confirm("Desativar este cartão?")) return;
    try {
      await apiFetch(`/api/cards/management/${id}`, { token, method: "DELETE" });
      load();
    } catch {}
  }

  if (loading) {
    return <div className="flex justify-center h-40 items-center"><div className="h-7 w-7 border-4 border-brand-green/30 border-t-brand-green rounded-full animate-spin" /></div>;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
          </svg>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por bandeira, 4 dígitos ou cliente…"
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
          />
        </div>
        <button
          onClick={openNew}
          className="ml-auto flex items-center gap-2 rounded-lg bg-brand-green px-4 py-2 text-sm font-semibold text-white hover:bg-brand-deep"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Novo Cartão
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
              <th onClick={() => toggleSort("bandeira")} className="px-4 py-3 text-left font-semibold text-gray-600 dark:text-gray-400 cursor-pointer select-none hover:text-gray-900 dark:hover:text-gray-100">
                Bandeira <SortIcon k="bandeira" />
              </th>
              <th onClick={() => toggleSort("numero_final")} className="px-4 py-3 text-left font-semibold text-gray-600 dark:text-gray-400 cursor-pointer select-none hover:text-gray-900 dark:hover:text-gray-100">
                Número <SortIcon k="numero_final" />
              </th>
              <th onClick={() => toggleSort("cliente")} className="px-4 py-3 text-left font-semibold text-gray-600 dark:text-gray-400 cursor-pointer select-none hover:text-gray-900 dark:hover:text-gray-100">
                Cliente <SortIcon k="cliente" />
              </th>
              <th className="px-4 py-3 text-left font-semibold text-gray-600 dark:text-gray-400">Status</th>
              <th className="px-4 py-3 text-right font-semibold text-gray-600 dark:text-gray-400">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {filtered.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-10 text-center text-gray-400 dark:text-gray-600">Nenhum cartão encontrado.</td></tr>
            ) : filtered.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                <td className="px-4 py-3">
                  <span className="inline-flex items-center rounded-full bg-gray-100 dark:bg-gray-700 px-2.5 py-0.5 text-xs font-semibold text-gray-700 dark:text-gray-300">
                    {c.bandeira}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-gray-700 dark:text-gray-300">•••• •••• •••• {c.numero_final}</td>
                <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{c.cards_clientes?.nome ?? "—"}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${c.ativo ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"}`}>
                    {c.ativo ? "Ativo" : "Inativo"}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex justify-end gap-2">
                    <button onClick={() => openEdit(c)} className="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-1 text-xs font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800">
                      Editar
                    </button>
                    {c.ativo && (
                      <button onClick={() => handleDeactivate(c.id)} className="rounded-lg border border-red-200 dark:border-red-800 px-3 py-1 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20">
                        Desativar
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal de cadastro/edição */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl bg-white dark:bg-gray-900 shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 px-5 py-4">
              <h2 className="font-semibold text-gray-900 dark:text-gray-100">
                {editId ? "Editar Cartão" : "Novo Cartão"}
              </h2>
              <button onClick={() => setShowForm(false)} className="h-8 w-8 grid place-items-center rounded-md text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="px-5 py-4 space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                  Cliente <span className="text-red-500">*</span>
                </label>
                <select
                  value={form.cliente_id}
                  onChange={(e) => setForm((f) => ({ ...f, cliente_id: e.target.value }))}
                  className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                >
                  <option value="">Selecione…</option>
                  {clients.filter((c) => c.ativo).map((c) => (
                    <option key={c.id} value={c.id}>{c.nome}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                  Bandeira <span className="text-red-500">*</span>
                </label>
                <select
                  value={form.bandeira}
                  onChange={(e) => setForm((f) => ({ ...f, bandeira: e.target.value }))}
                  className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                >
                  {BANDEIRAS.map((b) => <option key={b} value={b}>{b}</option>)}
                </select>
              </div>
              {!editId && (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                      Número do Cartão <span className="text-red-500">*</span>
                    </label>
                    <input
                      value={form.numero}
                      onChange={(e) => setForm((f) => ({ ...f, numero: e.target.value.replace(/\D/g, "") }))}
                      placeholder="Somente dígitos"
                      maxLength={19}
                      className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm font-mono text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                        CVV <span className="text-red-500">*</span>
                      </label>
                      <input
                        value={form.cvv}
                        onChange={(e) => setForm((f) => ({ ...f, cvv: e.target.value.replace(/\D/g, "") }))}
                        placeholder="123"
                        maxLength={4}
                        className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm font-mono text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                        Validade <span className="text-red-500">*</span>
                      </label>
                      <input
                        value={form.expiracao}
                        onChange={(e) => setForm((f) => ({ ...f, expiracao: e.target.value }))}
                        placeholder="MM/AA"
                        maxLength={5}
                        className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm font-mono text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                      Nome do Titular <span className="text-red-500">*</span>
                    </label>
                    <input
                      value={form.titular}
                      onChange={(e) => setForm((f) => ({ ...f, titular: e.target.value.toUpperCase() }))}
                      placeholder="NOME COMO NO CARTÃO"
                      className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm font-mono text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green"
                    />
                  </div>
                  <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 px-3 py-2">
                    <p className="text-xs text-amber-700 dark:text-amber-400">
                      Os dados do cartão serão criptografados imediatamente. Nunca são armazenados em texto simples.
                    </p>
                  </div>
                </>
              )}
              {formError && (
                <p className="text-sm text-red-600 dark:text-red-400">{formError}</p>
              )}
            </div>
            <div className="flex justify-end gap-3 border-t border-gray-100 dark:border-gray-800 px-5 py-4">
              <button onClick={() => setShowForm(false)} className="rounded-lg border border-gray-200 dark:border-gray-700 px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800">
                Cancelar
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="rounded-lg bg-brand-green px-5 py-2 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-40 flex items-center gap-2"
              >
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
