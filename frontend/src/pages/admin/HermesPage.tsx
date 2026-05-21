import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../lib/api";
import Icon from "../../components/Icon";

// ─── Types ────────────────────────────────────────────────────────────────────

interface PlatformConfig {
  enabled: boolean;
  token: string;
  chat_id?: string;
  address?: string;
  password?: string;
}

interface HermesConfig {
  model: string;
  provider: string;
  max_iterations: number;
  enabled_toolsets: string[];
  platforms: Record<string, PlatformConfig>;
  session_reset_mode: string;
  session_reset_hour: number;
  streaming_mode: string;
}

interface SchemaData {
  providers: Record<string, string[]>;
  toolsets: string[];
  streaming_modes: string[];
  session_modes: string[];
}

interface GatewayStatus {
  platform: string;
  enabled: boolean;
  configured: boolean;
  running: boolean;
  pid: number | null;
}

interface Skill {
  name: string;
  description: string;
  tags: string[];
  uses: number;
  modified_at: number;
  file: string;
}

type Tab = "config" | "gateways" | "sessions" | "skills";

const PLATFORM_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  telegram:  { label: "Telegram",  icon: "send",      color: "bg-sky-500"    },
  discord:   { label: "Discord",   icon: "message",   color: "bg-indigo-500" },
  slack:     { label: "Slack",     icon: "hash",      color: "bg-green-600"  },
  whatsapp:  { label: "WhatsApp",  icon: "phone",     color: "bg-emerald-500"},
  signal:    { label: "Signal",    icon: "shield",    color: "bg-blue-600"   },
  email:     { label: "E-mail",    icon: "mail",      color: "bg-orange-500" },
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function HermesPage() {
  const { token } = useAuth();

  const [tab, setTab] = useState<Tab>("config");
  const [config, setConfig] = useState<HermesConfig | null>(null);
  const [schema, setSchema] = useState<SchemaData | null>(null);
  const [gateways, setGateways] = useState<GatewayStatus[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfg, sch, gws] = await Promise.all([
        apiFetch<HermesConfig>("/api/hermes/config", { token }),
        apiFetch<SchemaData>("/api/hermes/config/schema", { token }),
        apiFetch<GatewayStatus[]>("/api/hermes/gateways", { token }),
      ]);
      setConfig(cfg);
      setSchema(sch);
      setGateways(gws);
    } catch (e: any) {
      setError(e.message ?? "Erro ao carregar configurações");
    } finally {
      setLoading(false);
    }
  }, [token]);

  const loadSkills = useCallback(async () => {
    try {
      const data = await apiFetch<Skill[]>("/api/hermes/skills", { token });
      setSkills(data);
    } catch {
      setSkills([]);
    }
  }, [token]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (tab === "skills") loadSkills();
  }, [tab, loadSkills]);

  async function saveConfig() {
    if (!config) return;
    setSaving(true);
    try {
      await apiFetch("/api/hermes/config", { method: "PUT", json: config, token });
      showToast("Configuração salva");
    } catch (e: any) {
      showToast("Erro: " + (e.message ?? "falha ao salvar"));
    } finally {
      setSaving(false);
    }
  }

  async function toggleGateway(platform: string, running: boolean) {
    const action = running ? "stop" : "start";
    try {
      await apiFetch(`/api/hermes/gateways/${platform}/${action}`, {
        method: "POST",
        token,
      });
      showToast(`Gateway ${platform} ${action === "start" ? "iniciado" : "parado"}`);
      await loadAll();
    } catch (e: any) {
      showToast("Erro: " + (e.message ?? "falha na operação"));
    }
  }

  async function deleteSkill(file: string) {
    if (!confirm("Deletar esta skill?")) return;
    try {
      await apiFetch(`/api/hermes/skills/${encodeURIComponent(file)}`, {
        method: "DELETE",
        token,
      });
      showToast("Skill deletada");
      loadSkills();
    } catch (e: any) {
      showToast("Erro: " + (e.message ?? "falha ao deletar"));
    }
  }

  function setPlatformField(platform: string, field: string, value: unknown) {
    setConfig((c) => {
      if (!c) return c;
      return {
        ...c,
        platforms: {
          ...c.platforms,
          [platform]: { ...c.platforms[platform], [field]: value },
        },
      };
    });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-brand-green border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !config) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4 text-red-700 dark:text-red-400">
          {error ?? "Hermes service indisponível"}
        </div>
      </div>
    );
  }

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: "config",   label: "Configuração", icon: "settings"  },
    { id: "gateways", label: "Gateways",     icon: "zap"       },
    { id: "sessions", label: "Sessões",      icon: "clock"     },
    { id: "skills",   label: "Skills",       icon: "cpu"       },
  ];

  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="h-8 w-8 rounded-lg bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
              <Icon name="cpu" size={18} className="text-violet-600 dark:text-violet-400" />
            </div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Hermes Agent</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Assistente IA autônomo com learning loop — configure modelo, gateways e comportamento
          </p>
        </div>
        {tab !== "skills" && (
          <button
            onClick={saveConfig}
            disabled={saving}
            className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-green text-white text-sm font-medium hover:bg-brand-green/90 disabled:opacity-60 transition-colors"
          >
            {saving ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <Icon name="save" size={15} />
            )}
            Salvar
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="flex gap-1 -mb-px">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === t.id
                  ? "border-brand-green text-brand-deep dark:text-brand-mid"
                  : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              <Icon name={t.icon} size={15} />
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {/* ── Tab: Configuração ─────────────────────────────────────────────── */}
      {tab === "config" && (
        <div className="space-y-6">
          <Section title="Modelo de IA">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Provider">
                <select
                  value={config.provider}
                  onChange={(e) =>
                    setConfig((c) => c ? { ...c, provider: e.target.value, model: schema?.providers[e.target.value]?.[0] ?? c.model } : c)
                  }
                  className={selectCls}
                >
                  {Object.keys(schema?.providers ?? {}).map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </Field>
              <Field label="Modelo">
                <select
                  value={config.model}
                  onChange={(e) => setConfig((c) => c ? { ...c, model: e.target.value } : c)}
                  className={selectCls}
                >
                  {(schema?.providers[config.provider] ?? []).map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Máximo de iterações por turn">
              <input
                type="number"
                min={1}
                max={50}
                value={config.max_iterations}
                onChange={(e) =>
                  setConfig((c) => c ? { ...c, max_iterations: Number(e.target.value) } : c)
                }
                className={inputCls}
              />
            </Field>
          </Section>

          <Section title="Toolsets habilitados">
            <div className="flex flex-wrap gap-2">
              {(schema?.toolsets ?? []).map((tool) => {
                const active = config.enabled_toolsets.includes(tool);
                return (
                  <button
                    key={tool}
                    onClick={() =>
                      setConfig((c) => {
                        if (!c) return c;
                        const next = active
                          ? c.enabled_toolsets.filter((t) => t !== tool)
                          : [...c.enabled_toolsets, tool];
                        return { ...c, enabled_toolsets: next };
                      })
                    }
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      active
                        ? "bg-brand-green/15 border-brand-green text-brand-deep dark:text-brand-mid"
                        : "bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-brand-green/50"
                    }`}
                  >
                    {tool}
                  </button>
                );
              })}
            </div>
          </Section>
        </div>
      )}

      {/* ── Tab: Gateways ─────────────────────────────────────────────────── */}
      {tab === "gateways" && (
        <div className="space-y-4">
          {Object.entries(PLATFORM_LABELS).map(([platform, meta]) => {
            const pcfg = config.platforms[platform] ?? { enabled: false, token: "", chat_id: "" };
            const status = gateways.find((g) => g.platform === platform);
            const isEmail = platform === "email";
            return (
              <div
                key={platform}
                className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-hidden"
              >
                <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 dark:border-gray-800">
                  <div className={`h-8 w-8 rounded-lg ${meta.color} flex items-center justify-center`}>
                    <Icon name={meta.icon} size={16} className="text-white" />
                  </div>
                  <span className="font-medium text-gray-900 dark:text-gray-100 flex-1">{meta.label}</span>
                  {status && (
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                      status.running
                        ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
                        : status.enabled
                        ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400"
                        : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
                    }`}>
                      {status.running ? "Rodando" : status.enabled ? "Parado" : "Desabilitado"}
                    </span>
                  )}
                  {/* Enable toggle */}
                  <button
                    onClick={() => setPlatformField(platform, "enabled", !pcfg.enabled)}
                    className={`relative w-10 h-5 rounded-full transition-colors ${pcfg.enabled ? "bg-brand-green" : "bg-gray-200 dark:bg-gray-700"}`}
                  >
                    <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${pcfg.enabled ? "translate-x-5" : ""}`} />
                  </button>
                </div>

                {pcfg.enabled && (
                  <div className="px-4 py-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {isEmail ? (
                      <>
                        <Field label="E-mail">
                          <input
                            value={pcfg.address ?? ""}
                            onChange={(e) => setPlatformField(platform, "address", e.target.value)}
                            placeholder="bot@example.com"
                            className={inputCls}
                          />
                        </Field>
                        <Field label="Senha / App Password">
                          <input
                            type="password"
                            value={pcfg.password ?? ""}
                            onChange={(e) => setPlatformField(platform, "password", e.target.value)}
                            placeholder="senha ou app password"
                            className={inputCls}
                          />
                        </Field>
                      </>
                    ) : (
                      <>
                        <Field label="Token do bot">
                          <input
                            value={pcfg.token}
                            onChange={(e) => setPlatformField(platform, "token", e.target.value)}
                            placeholder="token do bot"
                            className={inputCls}
                          />
                        </Field>
                        <Field label="Chat / Channel ID (home)">
                          <input
                            value={pcfg.chat_id ?? ""}
                            onChange={(e) => setPlatformField(platform, "chat_id", e.target.value)}
                            placeholder="ID do chat padrão"
                            className={inputCls}
                          />
                        </Field>
                      </>
                    )}
                    {status && (
                      <div className="sm:col-span-2 flex justify-end">
                        <button
                          onClick={() => toggleGateway(platform, status.running)}
                          className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                            status.running
                              ? "bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 hover:bg-red-100"
                              : "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 hover:bg-green-100"
                          }`}
                        >
                          <Icon name={status.running ? "square" : "play"} size={13} />
                          {status.running ? "Parar daemon" : "Iniciar daemon"}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
          <p className="text-xs text-gray-400 dark:text-gray-500">
            Salve a configuração antes de iniciar um daemon. O daemon roda dentro do container hermes-service.
          </p>
        </div>
      )}

      {/* ── Tab: Sessões ──────────────────────────────────────────────────── */}
      {tab === "sessions" && (
        <div className="space-y-6">
          <Section title="Política de reset de sessão">
            <Field label="Modo">
              <select
                value={config.session_reset_mode}
                onChange={(e) =>
                  setConfig((c) => c ? { ...c, session_reset_mode: e.target.value } : c)
                }
                className={selectCls}
              >
                {(schema?.session_modes ?? []).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                daily = limpa contexto todo dia · idle = limpa após inatividade · both = ambos · none = nunca limpa
              </p>
            </Field>
            {(config.session_reset_mode === "daily" || config.session_reset_mode === "both") && (
              <Field label="Hora do reset diário (0–23)">
                <input
                  type="number"
                  min={0}
                  max={23}
                  value={config.session_reset_hour}
                  onChange={(e) =>
                    setConfig((c) => c ? { ...c, session_reset_hour: Number(e.target.value) } : c)
                  }
                  className={inputCls}
                />
              </Field>
            )}
          </Section>

          <Section title="Streaming de respostas">
            <Field label="Modo">
              <select
                value={config.streaming_mode}
                onChange={(e) =>
                  setConfig((c) => c ? { ...c, streaming_mode: e.target.value } : c)
                }
                className={selectCls}
              >
                {(schema?.streaming_modes ?? []).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                auto = decide por canal · draft = mostra rascunho editável · edit = edição inline · off = sem streaming
              </p>
            </Field>
          </Section>
        </div>
      )}

      {/* ── Tab: Skills ───────────────────────────────────────────────────── */}
      {tab === "skills" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Skills aprendidas automaticamente pelo Hermes durante o uso
            </p>
            <button
              onClick={loadSkills}
              className="inline-flex items-center gap-1 text-xs text-brand-green hover:underline"
            >
              <Icon name="refresh-cw" size={12} />
              Atualizar
            </button>
          </div>

          {skills.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-200 dark:border-gray-700 p-10 text-center">
              <div className="mx-auto mb-3 h-12 w-12 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                <Icon name="cpu" size={22} className="text-gray-400 dark:text-gray-500" />
              </div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Nenhuma skill aprendida ainda</p>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                O Hermes cria skills automaticamente após completar tarefas complexas
              </p>
            </div>
          ) : (
            <div className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
                    <th className="px-4 py-2.5 text-left font-medium text-gray-600 dark:text-gray-400">Nome</th>
                    <th className="hidden sm:table-cell px-4 py-2.5 text-left font-medium text-gray-600 dark:text-gray-400">Descrição</th>
                    <th className="px-4 py-2.5 text-center font-medium text-gray-600 dark:text-gray-400">Usos</th>
                    <th className="px-4 py-2.5" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                  {skills.map((skill) => (
                    <tr key={skill.file} className="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                      <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{skill.name}</td>
                      <td className="hidden sm:table-cell px-4 py-3 text-gray-500 dark:text-gray-400 max-w-xs truncate">
                        {skill.description || "—"}
                      </td>
                      <td className="px-4 py-3 text-center text-gray-500 dark:text-gray-400">{skill.uses}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => deleteSkill(skill.file)}
                          className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-500 transition-colors"
                          title="Deletar skill"
                        >
                          <Icon name="trash-2" size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-lg bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 text-sm font-medium shadow-lg animate-fade-in">
          {toast}
        </div>
      )}
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4 space-y-4">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="block text-xs font-medium text-gray-600 dark:text-gray-400">{label}</label>
      {children}
    </div>
  );
}

const inputCls =
  "w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-green/40 focus:border-brand-green transition-colors";

const selectCls =
  "w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-green/40 focus:border-brand-green transition-colors";
