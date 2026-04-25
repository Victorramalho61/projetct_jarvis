import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";

type Account = {
  connected: boolean;
  email?: string;
  updated_at?: string;
};

type DeliveryChannel = "email" | "teams" | "whatsapp";

type Prefs = {
  send_hour_utc: number;
  active: boolean;
  delivery_channel: DeliveryChannel;
  teams_webhook_url: string;
  whatsapp_phone: string;
};

export default function MoneypennyPage() {
  const { token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [account, setAccount] = useState<Account | null>(null);
  const [prefs, setPrefs] = useState<Prefs>({
    send_hour_utc: 10,
    active: true,
    delivery_channel: "email",
    teams_webhook_url: "",
    whatsapp_phone: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [testing, setTesting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (msg: string) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast(msg);
    toastTimer.current = setTimeout(() => setToast(null), 4000);
  };

  useEffect(() => () => { if (toastTimer.current) clearTimeout(toastTimer.current); }, []);

  const savePrefs = useCallback(async (updated: Prefs) => {
    try {
      await apiFetch("/api/moneypenny/prefs", { method: "PUT", token, json: updated });
    } catch {
      showToast("Erro ao salvar preferências.");
    }
  }, [token]);

  const fetchData = useCallback(async () => {
    try {
      const [acc, pref] = await Promise.all([
        apiFetch<Account>("/api/moneypenny/account", { token }),
        apiFetch<Prefs>("/api/moneypenny/prefs", { token }),
      ]);
      setAccount(acc);
      setPrefs(pref);
    } catch (e) {
      if (e instanceof ApiError && e.status === 0) showToast("Sem conexão com o servidor.");
      setAccount({ connected: false });
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (searchParams.get("connected") === "1") {
      showToast("Conta Microsoft conectada com sucesso!");
      setSearchParams({}, { replace: true });
    }
  }, []);

  async function handleConnect() {
    try {
      const data = await apiFetch<{ url: string }>("/api/moneypenny/auth/microsoft/url", { token });
      window.location.href = data.url;
    } catch (e) {
      showToast(e instanceof ApiError ? `Erro: ${e.message}` : "Falha de conexão.");
    }
  }

  async function handleDisconnect() {
    try {
      await apiFetch("/api/moneypenny/account", { method: "DELETE", token });
      setAccount({ connected: false });
      showToast("Conta desconectada.");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Erro ao desconectar.");
    }
  }

  async function handleSavePrefs() {
    setSaving(true);
    try {
      await apiFetch("/api/moneypenny/prefs", { method: "PUT", token, json: prefs });
      showToast("Preferências salvas.");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive() {
    const newActive = !prefs.active;
    setToggling(true);
    try {
      await apiFetch("/api/moneypenny/prefs", { method: "PUT", token, json: { ...prefs, active: newActive } });
      setPrefs((p) => ({ ...p, active: newActive }));
      showToast(newActive ? "Agendamento ativado." : "Agendamento desativado.");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Erro ao alterar agendamento.");
    } finally {
      setToggling(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    try {
      await apiFetch("/api/moneypenny/prefs", { method: "PUT", token, json: prefs });
      await apiFetch("/api/moneypenny/test", { method: "POST", token });
      const label = prefs.delivery_channel === "teams"
        ? "Mensagem enviada no Teams!"
        : prefs.delivery_channel === "whatsapp"
        ? "Mensagem enviada no WhatsApp!"
        : "E-mail de teste enviado! Verifique sua caixa de entrada.";
      showToast(label);
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Falha ao enviar.");
    } finally {
      setTesting(false);
    }
  }

  const channels: { value: DeliveryChannel; label: string; icon: string }[] = [
    { value: "email", label: "E-mail", icon: "📧" },
    { value: "teams", label: "Teams", icon: "💬" },
    { value: "whatsapp", label: "WhatsApp", icon: "📱" },
  ];

  if (loading) {
    return (
      <div className="flex min-h-full items-center justify-center p-8">
        <p className="text-sm text-gray-400">Carregando...</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-2xl">
      {toast && (
        <div className="fixed top-4 right-4 z-50 rounded-lg bg-gray-900 px-4 py-3 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}

      <h2 className="text-xl font-bold text-gray-900">Moneypenny</h2>
      <p className="mt-1 text-sm text-gray-500">
        Receba um resumo diário dos seus e-mails e agenda do Microsoft 365.
      </p>

      {/* Conta Microsoft */}
      <section className="mt-6 rounded-xl border bg-white p-6 shadow-sm">
        <h3 className="font-semibold text-gray-900">Conta Microsoft 365</h3>
        {account?.connected ? (
          <div className="mt-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">{account.email}</p>
              <p className="text-xs text-gray-400">
                Conectado em{" "}
                {account.updated_at ? new Date(account.updated_at).toLocaleDateString("pt-BR") : "—"}
              </p>
            </div>
            <button
              onClick={handleDisconnect}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
            >
              Desconectar
            </button>
          </div>
        ) : (
          <div className="mt-4">
            <p className="text-sm text-gray-500 mb-3">Conecte sua conta para buscar e-mails e agenda.</p>
            <button
              onClick={handleConnect}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              <svg className="h-4 w-4" viewBox="0 0 23 23" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M1 1h10v10H1V1zm11 0h10v10H12V1zM1 12h10v10H1V12zm11 0h10v10H12V12z" fill="currentColor"/>
              </svg>
              Conectar com Microsoft 365
            </button>
          </div>
        )}
      </section>

      {/* Canal de entrega */}
      <section className="mt-4 rounded-xl border bg-white p-6 shadow-sm">
        <h3 className="font-semibold text-gray-900">Canal de entrega</h3>
        <p className="mt-0.5 text-xs text-gray-500">Onde você quer receber o resumo diário</p>

        <div className="mt-4 grid grid-cols-3 gap-2">
          {channels.map((ch) => (
            <button
              key={ch.value}
              onClick={() => {
                const updated = { ...prefs, delivery_channel: ch.value };
                setPrefs(updated);
                savePrefs(updated);
              }}
              className={`flex flex-col items-center gap-1 rounded-xl border-2 py-4 text-sm font-medium transition-colors ${
                prefs.delivery_channel === ch.value
                  ? "border-blue-500 bg-blue-50 text-blue-700"
                  : "border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50"
              }`}
            >
              <span className="text-2xl">{ch.icon}</span>
              {ch.label}
            </button>
          ))}
        </div>

        {prefs.delivery_channel === "teams" && (
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700">URL do Webhook do Teams</label>
            <p className="mt-0.5 text-xs text-gray-400">
              Configure um Incoming Webhook no Teams e cole a URL abaixo.
            </p>
            <input
              type="url"
              value={prefs.teams_webhook_url}
              onChange={(e) => setPrefs((p) => ({ ...p, teams_webhook_url: e.target.value }))}
              className="mt-2 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="https://..."
            />
          </div>
        )}

        {prefs.delivery_channel === "whatsapp" && (
          <div className="mt-4 rounded-lg border border-gray-100 bg-gray-50 px-4 py-3">
            {prefs.whatsapp_phone ? (
              <p className="text-sm text-gray-700">
                Resumo será enviado para{" "}
                <span className="font-medium text-gray-900">+{prefs.whatsapp_phone}</span>
              </p>
            ) : (
              <p className="text-sm text-red-500">
                Nenhum número cadastrado.{" "}
                <a href="/admin/acesso" className="underline">Atualize seu perfil</a>.
              </p>
            )}
          </div>
        )}
      </section>

      {/* Agendamento */}
      <section className="mt-4 rounded-xl border bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900">Resumo diário</h3>
            <p className="mt-0.5 text-xs text-gray-500">
              {prefs.active
                ? `Agendado para ${((prefs.send_hour_utc - 3 + 24) % 24).toString().padStart(2, "0")}:00 (BRT) todos os dias`
                : "Agendamento desativado"}
            </p>
          </div>
          <button
            onClick={handleToggleActive}
            disabled={toggling}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none disabled:opacity-50 ${
              prefs.active ? "bg-blue-600" : "bg-gray-300"
            }`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
              prefs.active ? "translate-x-6" : "translate-x-1"
            }`} />
          </button>
        </div>

        {prefs.active && (
          <div className="mt-5 border-t pt-5">
            <label className="text-sm font-medium text-gray-700">Horário de envio (BRT)</label>
            <div className="mt-2 flex items-center gap-3">
              <select
                value={prefs.send_hour_utc}
                onChange={(e) => setPrefs((p) => ({ ...p, send_hour_utc: Number(e.target.value) }))}
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {Array.from({ length: 24 }, (_, i) => i).map((utcH) => {
                  const brt = ((utcH - 3 + 24) % 24).toString().padStart(2, "0");
                  return <option key={utcH} value={utcH}>{brt}:00</option>;
                })}
              </select>
              <button
                onClick={handleSavePrefs}
                disabled={saving}
                className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {saving ? "Salvando..." : "Salvar"}
              </button>
              {account?.connected && (
                <button
                  onClick={handleTest}
                  disabled={testing}
                  className="rounded-lg border border-gray-300 px-4 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
                >
                  {testing ? "Enviando..." : "Enviar agora"}
                </button>
              )}
            </div>
          </div>
        )}

        {!prefs.active && account?.connected && (
          <div className="mt-4">
            <button
              onClick={handleTest}
              disabled={testing}
              className="rounded-lg border border-gray-300 px-4 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              {testing ? "Enviando..." : "Enviar resumo agora"}
            </button>
          </div>
        )}
      </section>

      <p className="mt-4 text-xs text-gray-400">
        O resumo inclui e-mails não lidos do dia anterior e compromissos do dia atual.
        A conta Microsoft é necessária independente do canal escolhido.
      </p>
    </div>
  );
}
