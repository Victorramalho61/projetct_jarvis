import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";
import { useToast } from "../hooks/useToast";

type ChannelConfig = {
  enabled: boolean;
  content: string[];
};

type Prefs = {
  send_hour_utc: number;
  active: boolean;
  channels: {
    email: ChannelConfig;
    teams: ChannelConfig;
    whatsapp: ChannelConfig;
  };
  teams_chat_id: string;
  teams_mode: "direct";
  whatsapp_phone: string;
};

const DEFAULT_PREFS: Prefs = {
  send_hour_utc: 10,
  active: true,
  channels: {
    email:    { enabled: false, content: ["emails", "calendar"] },
    teams:    { enabled: false, content: ["emails", "calendar"] },
    whatsapp: { enabled: false, content: ["calendar"] },
  },
  teams_chat_id: "",
  teams_mode: "direct",
  whatsapp_phone: "",
};

type Account = { connected: boolean; email?: string; updated_at?: string };

const CONTENT_LABELS: Record<string, { icon: string; label: string }> = {
  emails:   { icon: "📬", label: "E-mails não lidos" },
  calendar: { icon: "📅", label: "Agenda do dia" },
};

const CHANNEL_META: Record<string, { icon: string; label: string }> = {
  email:    { icon: "📧", label: "E-mail" },
  teams:    { icon: "💬", label: "Teams" },
  whatsapp: { icon: "📱", label: "WhatsApp" },
};

export default function MoneypennyPage() {
  const { token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const { toast, showToast } = useToast(5000);
  const [account, setAccount] = useState<Account | null>(null);
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [testing, setTesting] = useState(false);
  const [initingChat, setInitingChat] = useState(false);

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
      await apiFetch("/api/moneypenny/prefs", {
        method: "PUT",
        token,
        json: { ...prefs, teams_mode: "direct", teams_webhook_url: "" },
      });
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
      await apiFetch("/api/moneypenny/prefs", { method: "PUT", token, json: { ...prefs, active: newActive, teams_mode: "direct", teams_webhook_url: "" } });
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
      const result = await apiFetch<{ ok: boolean; sent: string[]; background?: boolean }>(
        "/api/moneypenny/test", { method: "POST", token }
      );
      const channels = result.sent.map((ch) => CHANNEL_META[ch]?.label ?? ch).join(", ");
      const msg = result.background
        ? `Enviando via ${channels} em segundo plano. Verifique os Logs em instantes.`
        : `Resumo enviado via ${channels}!`;
      showToast(msg);
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Falha ao enviar.");
    } finally {
      setTesting(false);
    }
  }

  async function handleInitChat() {
    setInitingChat(true);
    try {
      const result = await apiFetch<{ ok: boolean; chat_id: string }>(
        "/api/moneypenny/teams/init-chat", { method: "POST", token }
      );
      setPrefs((p) => ({ ...p, teams_chat_id: result.chat_id, teams_mode: "direct" }));
      showToast("Chat Teams Moneypenny inicializado!");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Erro ao inicializar chat.");
    } finally {
      setInitingChat(false);
    }
  }

  async function handleAdminConsent() {
    try {
      const data = await apiFetch<{ url: string }>("/api/moneypenny/auth/microsoft/admin-consent-url", { token });
      window.open(data.url, "_blank");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Erro ao obter URL de consentimento.");
    }
  }

  function toggleChannel(ch: keyof Prefs["channels"]) {
    setPrefs((p) => ({
      ...p,
      channels: {
        ...p.channels,
        [ch]: { ...p.channels[ch], enabled: !p.channels[ch].enabled },
      },
    }));
  }

  const anyEnabled = Object.values(prefs.channels).some((c) => c.enabled);

  if (loading) {
    return (
      <div className="flex min-h-full items-center justify-center p-8">
        <p className="text-sm text-gray-400 dark:text-gray-500">Carregando...</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-2xl">
      {toast && (
        <div className="fixed top-4 right-4 z-50 rounded-lg bg-gray-900 px-4 py-3 text-sm text-white shadow-lg max-w-sm">
          {toast}
        </div>
      )}

      <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Moneypenny</h2>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Receba um resumo diário dos seus e-mails e agenda do Microsoft 365.
      </p>

      {/* Conta Microsoft */}
      <section className="mt-6 rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Conta Microsoft 365</h3>
        {account?.connected ? (
          <div className="mt-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{account.email}</p>
              <p className="text-xs text-gray-400 dark:text-gray-500">
                Conectado em{" "}
                {account.updated_at ? new Date(account.updated_at).toLocaleDateString("pt-BR") : "—"}
              </p>
            </div>
            <button
              onClick={handleDisconnect}
              className="rounded-lg border border-red-200 dark:border-red-700 px-3 py-1.5 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            >
              Desconectar
            </button>
          </div>
        ) : (
          <div className="mt-4">
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">Conecte sua conta para buscar e-mails e agenda.</p>
            <button
              onClick={handleConnect}
              className="inline-flex items-center gap-2 rounded-lg bg-voetur-600 px-4 py-2 text-sm font-medium text-white hover:bg-voetur-700 transition-colors"
            >
              <svg className="h-4 w-4" viewBox="0 0 23 23" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M1 1h10v10H1V1zm11 0h10v10H12V1zM1 12h10v10H1V12zm11 0h10v10H12V12z" fill="currentColor"/>
              </svg>
              Conectar com Microsoft 365
            </button>
          </div>
        )}
      </section>

      {/* Canais de entrega */}
      <section className="mt-4">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Canais de entrega</h3>
        <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">Ative um ou mais canais para receber o resumo</p>

        <div className="mt-3 space-y-3">
          <ChannelCard
            id="email"
            meta={CHANNEL_META.email}
            enabled={prefs.channels.email?.enabled ?? false}
            content={prefs.channels.email?.content ?? []}
            onToggle={() => toggleChannel("email")}
          />

          <ChannelCard
            id="teams"
            meta={CHANNEL_META.teams}
            enabled={prefs.channels.teams?.enabled ?? false}
            content={prefs.channels.teams?.content ?? []}
            onToggle={() => toggleChannel("teams")}
          >
            {prefs.channels.teams?.enabled && (
              <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700 space-y-2">
                <div className="flex items-center justify-between">
                  <p className={`text-xs ${prefs.teams_chat_id ? "text-green-600 dark:text-green-400" : "text-gray-500 dark:text-gray-400"}`}>
                    {prefs.teams_chat_id ? "✓ Chat inicializado" : "Chat ainda não inicializado"}
                  </p>
                  <button
                    type="button"
                    onClick={handleInitChat}
                    disabled={initingChat || !account?.connected}
                    className="rounded-lg bg-voetur-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-voetur-700 disabled:opacity-50 transition-colors"
                  >
                    {initingChat ? "Inicializando..." : prefs.teams_chat_id ? "Reinicializar" : "Inicializar chat"}
                  </button>
                </div>
              </div>
            )}
          </ChannelCard>

          <ChannelCard
            id="whatsapp"
            meta={CHANNEL_META.whatsapp}
            enabled={prefs.channels.whatsapp?.enabled ?? false}
            content={prefs.channels.whatsapp?.content ?? []}
            onToggle={() => toggleChannel("whatsapp")}
          >
            {prefs.channels.whatsapp?.enabled && (
              <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
                {prefs.whatsapp_phone ? (
                  <p className="text-xs text-gray-600 dark:text-gray-400">
                    Envio para{" "}
                    <span className="font-medium text-gray-900 dark:text-gray-100">+{prefs.whatsapp_phone}</span>
                  </p>
                ) : (
                  <p className="text-xs text-red-500 dark:text-red-400">
                    Nenhum número cadastrado.{" "}
                    <a href="/admin/acesso" className="underline">Atualize seu perfil</a>.
                  </p>
                )}
              </div>
            )}
          </ChannelCard>
        </div>
      </section>

      {/* Agendamento */}
      <section className="mt-4 rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Resumo diário</h3>
            <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
              {prefs.active
                ? `Agendado para ${((prefs.send_hour_utc - 3 + 24) % 24).toString().padStart(2, "0")}:00 (BRT) todos os dias`
                : "Agendamento desativado"}
            </p>
          </div>
          <button
            onClick={handleToggleActive}
            disabled={toggling}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none disabled:opacity-50 ${
              prefs.active ? "bg-voetur-600" : "bg-gray-300 dark:bg-gray-600"
            }`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
              prefs.active ? "translate-x-6" : "translate-x-1"
            }`} />
          </button>
        </div>

        {prefs.active && (
          <div className="mt-5 border-t border-gray-100 dark:border-gray-800 pt-5">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Horário de envio (BRT)</label>
            <div className="mt-2">
              <select
                value={prefs.send_hour_utc}
                onChange={(e) => setPrefs((p) => ({ ...p, send_hour_utc: Number(e.target.value) }))}
                className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:border-voetur-500 focus:outline-none focus:ring-1 focus:ring-voetur-500"
              >
                {Array.from({ length: 24 }, (_, i) => i).map((utcH) => {
                  const brt = ((utcH - 3 + 24) % 24).toString().padStart(2, "0");
                  return <option key={utcH} value={utcH}>{brt}:00</option>;
                })}
              </select>
            </div>
          </div>
        )}
      </section>

      {/* Ações */}
      <div className="mt-4 flex gap-3">
        <button
          onClick={handleSavePrefs}
          disabled={saving}
          className="rounded-lg bg-voetur-600 px-5 py-2 text-sm font-semibold text-white hover:bg-voetur-700 disabled:opacity-50 transition-colors"
        >
          {saving ? "Salvando..." : "Salvar"}
        </button>
        {account?.connected && anyEnabled && (
          <button
            onClick={handleTest}
            disabled={testing}
            className="rounded-lg border border-gray-300 dark:border-gray-700 px-5 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
          >
            {testing ? "Enviando..." : "Enviar agora"}
          </button>
        )}
      </div>

      <p className="mt-4 text-xs text-gray-400 dark:text-gray-500">
        A conta Microsoft é necessária para buscar e-mails e agenda, independente do canal escolhido.
      </p>
    </div>
  );
}

function ChannelCard({
  id: _id,
  meta,
  enabled,
  content,
  onToggle,
  children,
}: {
  id: string;
  meta: { icon: string; label: string };
  enabled: boolean;
  content: string[];
  onToggle: () => void;
  children?: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-xl border-2 bg-white dark:bg-gray-900 p-4 transition-colors ${
        enabled ? "border-voetur-500" : "border-gray-200 dark:border-gray-700"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{meta.icon}</span>
          <div>
            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{meta.label}</p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {content.map((c) => (
                <span
                  key={c}
                  className="inline-flex items-center gap-1 rounded-full bg-gray-100 dark:bg-gray-700 px-2 py-0.5 text-xs text-gray-600 dark:text-gray-300"
                >
                  {CONTENT_LABELS[c]?.icon} {CONTENT_LABELS[c]?.label ?? c}
                </span>
              ))}
            </div>
          </div>
        </div>
        <button
          onClick={onToggle}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none ${
            enabled ? "bg-voetur-600" : "bg-gray-300 dark:bg-gray-600"
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
              enabled ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </div>
      {children}
    </div>
  );
}
