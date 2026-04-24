import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

type Account = {
  connected: boolean;
  email?: string;
  updated_at?: string;
};

type Prefs = {
  send_hour_utc: number;
  active: boolean;
};

export default function MoneypennyPage() {
  const { token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [account, setAccount] = useState<Account | null>(null);
  const [prefs, setPrefs] = useState<Prefs>({ send_hour_utc: 10, active: true });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [testing, setTesting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const headers = { Authorization: `Bearer ${token}` };

  const showToast = (msg: string) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast(msg);
    toastTimer.current = setTimeout(() => setToast(null), 4000);
  };

  useEffect(() => () => { if (toastTimer.current) clearTimeout(toastTimer.current); }, []);

  const fetchData = useCallback(async () => {
    const [accRes, prefsRes] = await Promise.all([
      fetch("/api/moneypenny/account", { headers }),
      fetch("/api/moneypenny/prefs", { headers }),
    ]);
    if (accRes.ok) setAccount(await accRes.json());
    if (prefsRes.ok) setPrefs(await prefsRes.json());
    setLoading(false);
  }, [token]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (searchParams.get("connected") === "1") {
      showToast("Conta Microsoft conectada com sucesso!");
      setSearchParams({}, { replace: true });
    }
  }, []);

  async function handleConnect() {
    try {
      const r = await fetch("/api/moneypenny/auth/microsoft/url", { headers });
      const data = await r.json();
      if (!r.ok) { showToast(`Erro ao gerar link: ${data.detail ?? r.status}`); return; }
      if (!data.url) { showToast("Backend não retornou URL de autenticação."); return; }
      window.location.href = data.url;
    } catch (e) {
      showToast(`Falha de conexão: ${e}`);
    }
  }

  async function handleDisconnect() {
    const r = await fetch("/api/moneypenny/account", { method: "DELETE", headers });
    if (!r.ok) { showToast("Erro ao desconectar conta."); return; }
    setAccount({ connected: false });
    showToast("Conta desconectada.");
  }

  async function handleSavePrefs() {
    setSaving(true);
    const r = await fetch("/api/moneypenny/prefs", {
      method: "PUT",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify(prefs),
    });
    setSaving(false);
    if (!r.ok) { showToast("Erro ao salvar preferências."); return; }
    showToast("Preferências salvas.");
  }

  async function handleToggleActive() {
    const newActive = !prefs.active;
    setToggling(true);
    const r = await fetch("/api/moneypenny/prefs", {
      method: "PUT",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ ...prefs, active: newActive }),
    });
    setToggling(false);
    if (!r.ok) { showToast("Erro ao alterar agendamento."); return; }
    setPrefs((p) => ({ ...p, active: newActive }));
    showToast(newActive ? "Agendamento ativado." : "Agendamento desativado.");
  }

  async function handleTest() {
    setTesting(true);
    const r = await fetch("/api/moneypenny/test", { method: "POST", headers });
    setTesting(false);
    if (r.ok) {
      showToast("E-mail de teste enviado! Verifique sua caixa de entrada.");
    } else {
      const data = await r.json().catch(() => ({}));
      showToast(`Erro: ${(data as { detail?: string }).detail ?? "Falha ao enviar"}`);
    }
  }

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

      {/* Conexão */}
      <section className="mt-6 rounded-xl border bg-white p-6 shadow-sm">
        <h3 className="font-semibold text-gray-900">Conta Microsoft 365</h3>

        {account?.connected ? (
          <div className="mt-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">{account.email}</p>
              <p className="text-xs text-gray-400">
                Conectado em{" "}
                {account.updated_at
                  ? new Date(account.updated_at).toLocaleDateString("pt-BR")
                  : "—"}
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
            <p className="text-sm text-gray-500 mb-3">
              Conecte sua conta para receber resumos por e-mail.
            </p>
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
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                prefs.active ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
        </div>

        {prefs.active && (
          <div className="mt-5 border-t pt-5">
            <label className="text-sm font-medium text-gray-700">
              Horário de envio (BRT)
            </label>
            <div className="mt-2 flex items-center gap-3">
              <select
                value={prefs.send_hour_utc}
                onChange={(e) =>
                  setPrefs((p) => ({ ...p, send_hour_utc: Number(e.target.value) }))
                }
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {Array.from({ length: 24 }, (_, i) => i).map((utcH) => {
                  const brt = ((utcH - 3 + 24) % 24).toString().padStart(2, "0");
                  return (
                    <option key={utcH} value={utcH}>
                      {brt}:00
                    </option>
                  );
                })}
              </select>

              <button
                onClick={handleSavePrefs}
                disabled={saving}
                className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {saving ? "Salvando..." : "Salvar horário"}
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
        O resumo inclui e-mails não lidos do dia anterior e compromissos do dia atual,
        enviado para seu e-mail Microsoft 365.
      </p>
    </div>
  );
}
