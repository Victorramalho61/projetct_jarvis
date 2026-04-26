import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiFetch, ApiError } from "../lib/api";
import { useToast } from "../hooks/useToast";

type UserSummary = { id: string; username: string; display_name: string; email: string };
type ProfileData = { display_name: string; email: string; whatsapp_phone: string };

export default function ProfilePage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";

  const { toast, showToast } = useToast();
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [selectedUsername, setSelectedUsername] = useState<string>("");
  const [profile, setProfile] = useState<ProfileData>({ display_name: "", email: "", whatsapp_phone: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isAdmin) {
      apiFetch<ProfileData>("/api/auth/profile", { token })
        .then(setProfile)
        .catch(() => showToast("Erro ao carregar perfil."))
        .finally(() => setLoading(false));
      return;
    }
    apiFetch<UserSummary[]>("/api/users", { token })
      .then((data) => {
        setUsers(data);
        const self = data.find((u) => u.username === user?.username);
        const first = self ?? data[0];
        if (first) setSelectedUsername(first.username);
      })
      .catch(() => showToast("Erro ao carregar usuários."))
      .finally(() => setLoading(false));
  }, [token, isAdmin]);

  useEffect(() => {
    if (!isAdmin || !selectedUsername) return;
    setLoading(true);
    apiFetch<ProfileData>(`/api/users/${selectedUsername}/profile`, { token })
      .then(setProfile)
      .catch(() => showToast("Erro ao carregar perfil."))
      .finally(() => setLoading(false));
  }, [selectedUsername, isAdmin, token]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      if (isAdmin && selectedUsername !== user?.username) {
        await apiFetch(`/api/users/${selectedUsername}/profile`, {
          method: "PATCH",
          token,
          json: { display_name: profile.display_name, whatsapp_phone: profile.whatsapp_phone },
        });
      } else {
        await apiFetch("/api/auth/profile", {
          method: "PUT",
          token,
          json: { display_name: profile.display_name, whatsapp_phone: profile.whatsapp_phone },
        });
      }
      showToast("Perfil atualizado com sucesso.");
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="p-8 max-w-lg">
      {toast && (
        <div className="fixed top-4 right-4 z-50 rounded-lg bg-gray-900 px-4 py-3 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}

      <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Perfil</h2>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
        {isAdmin ? "Visualize e edite o perfil de qualquer usuário." : "Atualize suas informações pessoais."}
      </p>

      {isAdmin && users.length > 0 && (
        <div className="mt-4">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Usuário</label>
          <select
            value={selectedUsername}
            onChange={(e) => setSelectedUsername(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 shadow-sm focus:border-voetur-500 focus:outline-none focus:ring-1 focus:ring-voetur-500"
          >
            {users.map((u) => (
              <option key={u.id} value={u.username}>
                {u.display_name} ({u.email})
              </option>
            ))}
          </select>
        </div>
      )}

      {loading ? (
        <div className="mt-8 text-center text-sm text-gray-400 dark:text-gray-500">Carregando...</div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-4 space-y-5">
          <section className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">E-mail</label>
              <input
                type="text"
                value={profile.email}
                disabled
                className="mt-1 block w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm text-gray-500 dark:text-gray-400"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Nome de exibição</label>
              <input
                type="text"
                value={profile.display_name}
                onChange={(e) => setProfile((p) => ({ ...p, display_name: e.target.value }))}
                className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 shadow-sm focus:border-voetur-500 focus:outline-none focus:ring-1 focus:ring-voetur-500"
                placeholder="Nome completo"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">WhatsApp</label>
              <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">Com DDD e código do país, sem espaços (ex: 5561999999999)</p>
              <input
                type="tel"
                value={profile.whatsapp_phone}
                onChange={(e) => setProfile((p) => ({ ...p, whatsapp_phone: e.target.value.replace(/\D/g, "") }))}
                className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 shadow-sm focus:border-voetur-500 focus:outline-none focus:ring-1 focus:ring-voetur-500"
                placeholder="5561999999999"
              />
            </div>
          </section>

          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-voetur-600 px-5 py-2 text-sm font-semibold text-white hover:bg-voetur-700 disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-voetur-500 focus:ring-offset-2"
          >
            {saving ? "Salvando..." : "Salvar alterações"}
          </button>
        </form>
      )}
    </div>
  );
}
