import { useState } from "react";
import type { MonitoredSystem, SystemType } from "../../types/monitoring";
import { apiFetch, ApiError } from "../../lib/api";

const TYPE_OPTIONS: { value: SystemType; label: string }[] = [
  { value: "http",      label: "HTTP — health check de URL" },
  { value: "tcp",       label: "TCP — verifica porta (banco de dados, etc.)" },
  { value: "evolution", label: "WhatsApp — Evolution API" },
  { value: "metrics",   label: "Servidor — CPU/RAM/disco" },
  { value: "custom",    label: "Custom — endpoint configurável" },
];

const INTERVAL_OPTIONS = [1, 5, 10, 15, 30, 60];

const FIELD_CLASS = "w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

type Props = {
  system?: MonitoredSystem;
  token: string | null;
  onClose: () => void;
  onSaved: () => void;
};

export default function SystemFormModal({ system, token, onClose, onSaved }: Props) {
  const isEdit = Boolean(system);
  const [name, setName] = useState(system?.name ?? "");
  const [description, setDescription] = useState(system?.description ?? "");
  const [url, setUrl] = useState(system?.url ?? "");
  const [type, setType] = useState<SystemType>(system?.system_type ?? "http");
  const [interval, setInterval] = useState(system?.check_interval_minutes ?? 5);
  const [enabled, setEnabled] = useState(system?.enabled ?? true);
  const [configJson, setConfigJson] = useState(
    system?.config && Object.keys(system.config).length > 0
      ? JSON.stringify(system.config, null, 2)
      : ""
  );
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!name.trim()) { setError("Nome obrigatório"); return; }
    let config = {};
    if (configJson.trim()) {
      try { config = JSON.parse(configJson); }
      catch { setError("Config JSON inválido"); return; }
    }
    setSaving(true);
    setError(null);
    try {
      const payload = { name, description, url, system_type: type, config, check_interval_minutes: interval, enabled };
      if (isEdit) {
        await apiFetch(`/api/monitoring/systems/${system!.id}`, { method: "PATCH", json: payload, token });
      } else {
        await apiFetch("/api/monitoring/systems", { method: "POST", json: payload, token });
      }
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await apiFetch(`/api/monitoring/systems/${system!.id}`, { method: "DELETE", token });
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao excluir.");
      setDeleting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4">
      <div className="flex w-full max-w-lg flex-col rounded-t-xl bg-white dark:bg-gray-900 shadow-xl sm:rounded-xl max-h-[92vh]">

        {/* Header — fixo */}
        <div className="flex shrink-0 items-center justify-between border-b border-gray-100 dark:border-gray-800 px-4 py-4 sm:px-6">
          <h2 className="font-semibold text-gray-900 dark:text-gray-100">
            {isEdit ? "Editar sistema" : "Adicionar sistema"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none">&times;</button>
        </div>

        {/* Body — rola */}
        <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Nome *</label>
              <input value={name} onChange={(e) => setName(e.target.value)}
                className={FIELD_CLASS} placeholder="Ex: Backend API" />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Descrição</label>
              <input value={description} onChange={(e) => setDescription(e.target.value)}
                className={FIELD_CLASS} placeholder="Opcional" />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Tipo</label>
              <select value={type} onChange={(e) => setType(e.target.value as SystemType)} className={FIELD_CLASS}>
                {TYPE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            {type !== "metrics" && (
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                  {type === "tcp" ? "Host:Porta" : "URL"}
                </label>
                <input value={url} onChange={(e) => setUrl(e.target.value)}
                  className={FIELD_CLASS}
                  placeholder={type === "tcp" ? "ex: 10.141.0.32:5432" : "http://..."} />
              </div>
            )}

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Intervalo de check</label>
              <select value={interval} onChange={(e) => setInterval(Number(e.target.value))} className={FIELD_CLASS}>
                {INTERVAL_OPTIONS.map((m) => (
                  <option key={m} value={m}>{m} {m === 1 ? "minuto" : "minutos"}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Config (JSON opcional)</label>
              <textarea value={configJson} onChange={(e) => setConfigJson(e.target.value)} rows={3}
                className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 font-mono text-xs text-gray-900 dark:text-gray-100 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder='{"timeout_seconds": 5, "expected_status": 200}' />
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Habilitado</span>
              <button onClick={() => setEnabled((v) => !v)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${enabled ? "bg-blue-600" : "bg-gray-300 dark:bg-gray-600"}`}>
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${enabled ? "translate-x-6" : "translate-x-1"}`} />
              </button>
            </div>

            {error && (
              <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-700 dark:text-red-300">{error}</div>
            )}
          </div>
        </div>

        {/* Footer — fixo */}
        <div className="flex shrink-0 items-center justify-between border-t border-gray-100 dark:border-gray-800 px-4 py-4 sm:px-6">
          <div>
            {isEdit && !confirmDelete && (
              <button onClick={() => setConfirmDelete(true)} className="text-sm text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300">
                Excluir sistema
              </button>
            )}
            {isEdit && confirmDelete && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-red-600 dark:text-red-400">Confirmar?</span>
                <button onClick={handleDelete} disabled={deleting}
                  className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">
                  {deleting ? "..." : "Excluir"}
                </button>
                <button onClick={() => setConfirmDelete(false)} className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200">Cancelar</button>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <button onClick={onClose}
              className="rounded-lg border border-gray-300 dark:border-gray-700 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
              Cancelar
            </button>
            <button onClick={handleSave} disabled={saving}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
              {saving ? "Salvando..." : isEdit ? "Salvar" : "Adicionar"}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
