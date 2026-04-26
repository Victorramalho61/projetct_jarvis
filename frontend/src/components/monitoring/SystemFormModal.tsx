import { useState } from "react";
import type { MonitoredSystem, SystemType } from "../../types/monitoring";
import { apiFetch, ApiError } from "../../lib/api";

const TYPE_OPTIONS: { value: SystemType; label: string }[] = [
  { value: "http",      label: "HTTP — health check de URL" },
  { value: "evolution", label: "WhatsApp — Evolution API" },
  { value: "metrics",   label: "Servidor — CPU/RAM/disco" },
  { value: "custom",    label: "Custom — endpoint configurável" },
];

const INTERVAL_OPTIONS = [1, 5, 10, 15, 30, 60];

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 className="font-semibold text-gray-900">
            {isEdit ? "Editar sistema" : "Adicionar sistema"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>

        <div className="space-y-4 px-6 py-5">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Nome *</label>
            <input value={name} onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              placeholder="Ex: Backend API" />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Descrição</label>
            <input value={description} onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              placeholder="Opcional" />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Tipo</label>
            <select value={type} onChange={(e) => setType(e.target.value as SystemType)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none">
              {TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {type !== "metrics" && (
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">URL</label>
              <input value={url} onChange={(e) => setUrl(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                placeholder="http://..." />
            </div>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Intervalo de check</label>
            <select value={interval} onChange={(e) => setInterval(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none">
              {INTERVAL_OPTIONS.map((m) => (
                <option key={m} value={m}>{m} {m === 1 ? "minuto" : "minutos"}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Config (JSON opcional)</label>
            <textarea value={configJson} onChange={(e) => setConfigJson(e.target.value)} rows={3}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-xs focus:border-blue-500 focus:outline-none"
              placeholder='{"timeout_seconds": 5, "expected_status": 200}' />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">Habilitado</span>
            <button onClick={() => setEnabled((v) => !v)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${enabled ? "bg-blue-600" : "bg-gray-300"}`}>
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${enabled ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
          )}
        </div>

        <div className="flex items-center justify-between border-t px-6 py-4">
          <div>
            {isEdit && !confirmDelete && (
              <button onClick={() => setConfirmDelete(true)}
                className="text-sm text-red-600 hover:text-red-800">
                Excluir sistema
              </button>
            )}
            {isEdit && confirmDelete && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-red-600">Confirmar exclusão?</span>
                <button onClick={handleDelete} disabled={deleting}
                  className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">
                  {deleting ? "..." : "Confirmar"}
                </button>
                <button onClick={() => setConfirmDelete(false)} className="text-sm text-gray-500 hover:text-gray-700">Cancelar</button>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <button onClick={onClose}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
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
