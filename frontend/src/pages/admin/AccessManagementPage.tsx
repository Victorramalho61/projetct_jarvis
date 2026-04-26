import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch, ApiError } from "../../lib/api";
import { useToast } from "../../hooks/useToast";

type Profile = {
  id: string;
  username: string;
  display_name: string;
  email: string;
  role: "admin" | "user";
  active: boolean;
  created_at: string;
};

type ProfileData = { display_name: string; email: string; whatsapp_phone: string };

function UserProfileForm({
  token,
  username,
  isSelf,
}: {
  token: string | null;
  username: string;
  isSelf: boolean;
}) {
  const { toast, showToast } = useToast();
  const [profile, setProfile] = useState<ProfileData>({ display_name: "", email: "", whatsapp_phone: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    const url = isSelf ? "/api/auth/profile" : `/api/users/${username}/profile`;
    apiFetch<ProfileData>(url, { token })
      .then(setProfile)
      .catch(() => showToast("Erro ao carregar perfil."))
      .finally(() => setLoading(false));
  }, [username, isSelf, token]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const url = isSelf ? "/api/auth/profile" : `/api/users/${username}/profile`;
      const method = isSelf ? "PUT" : "PATCH";
      await apiFetch(url, { method, token, json: { display_name: profile.display_name, whatsapp_phone: profile.whatsapp_phone } });
      showToast("Perfil atualizado.");
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="mt-4 text-sm text-gray-400">Carregando perfil...</div>;

  return (
    <form onSubmit={handleSubmit} className="mt-4 space-y-4 rounded-xl border bg-white p-6 shadow-sm">
      {toast && (
        <div className="fixed top-4 right-4 z-50 rounded-lg bg-gray-900 px-4 py-3 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}
      <div>
        <label className="block text-sm font-medium text-gray-700">E-mail</label>
        <input
          type="text"
          value={profile.email}
          disabled
          className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700">Nome de exibição</label>
        <input
          type="text"
          value={profile.display_name}
          onChange={(e) => setProfile((p) => ({ ...p, display_name: e.target.value }))}
          className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-voetur-500 focus:outline-none focus:ring-1 focus:ring-voetur-500"
          placeholder="Nome completo"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700">WhatsApp</label>
        <p className="mt-0.5 text-xs text-gray-400">Com DDD e código do país, sem espaços (ex: 5561999999999)</p>
        <input
          type="tel"
          value={profile.whatsapp_phone}
          onChange={(e) => setProfile((p) => ({ ...p, whatsapp_phone: e.target.value.replace(/\D/g, "") }))}
          className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-voetur-500 focus:outline-none focus:ring-1 focus:ring-voetur-500"
          placeholder="5561999999999"
        />
      </div>
      <button
        type="submit"
        disabled={saving}
        className="rounded-lg bg-voetur-600 px-5 py-2 text-sm font-semibold text-white hover:bg-voetur-700 disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-voetur-500 focus:ring-offset-2"
      >
        {saving ? "Salvando..." : "Salvar alterações"}
      </button>
    </form>
  );
}

export default function AccessManagementPage() {
  const { token, user: currentUser } = useAuth();
  const isAdmin = currentUser?.role === "admin";

  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedUsername, setSelectedUsername] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const initialSelectionDone = useRef(false);

  const fetchProfiles = useCallback(async () => {
    try {
      const data = await apiFetch<Profile[]>("/api/users", { token });
      data.sort((a, b) => {
        if (a.active !== b.active) return a.active ? 1 : -1;
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      });
      setProfiles(data);
      if (!initialSelectionDone.current) {
        initialSelectionDone.current = true;
        const self = data.find((u) => u.username === currentUser?.username);
        setSelectedUsername(self?.username ?? data[0]?.username ?? "");
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar usuários.");
    } finally {
      setLoading(false);
    }
  }, [token, currentUser]);

  useEffect(() => { fetchProfiles(); }, [fetchProfiles]);

  async function handleRoleChange(username: string, role: string) {
    setBusy(username);
    setError(null);
    try {
      await apiFetch(`/api/users/${username}/role`, { method: "PATCH", token, json: { role } });
      await fetchProfiles();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao alterar perfil.");
    } finally {
      setBusy(null);
    }
  }

  async function handleDeleteUser(username: string) {
    if (!confirm(`Recusar e remover a solicitação de "${username}"?`)) return;
    setBusy(username);
    setError(null);
    try {
      await apiFetch(`/api/users/${username}`, { method: "DELETE", token });
      await fetchProfiles();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao recusar solicitação.");
    } finally {
      setBusy(null);
    }
  }

  async function handleToggleActive(username: string, active: boolean) {
    setBusy(username);
    setError(null);
    try {
      await apiFetch(`/api/users/${username}/active`, { method: "PATCH", token, json: { active } });
      await fetchProfiles();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao alterar status.");
    } finally {
      setBusy(null);
    }
  }

  if (!isAdmin) {
    return (
      <div className="p-8 max-w-lg">
        <h2 className="text-xl font-bold text-gray-900">Meu Perfil</h2>
        <p className="mt-1 text-sm text-gray-500">Atualize suas informações pessoais.</p>
        <UserProfileForm token={token} username={currentUser?.username ?? ""} isSelf={true} />
      </div>
    );
  }

  const pending = profiles.filter((p) => !p.active);
  const selectedProfile = profiles.find((p) => p.username === selectedUsername);

  return (
    <div className="p-8">
      <h2 className="text-xl font-bold text-gray-900">Gestão de Acesso</h2>
      <p className="mt-1 text-sm text-gray-500">Gerencie usuários e perfis de acesso</p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {pending.length > 0 && (
        <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-semibold text-amber-800">
            {pending.length} solicitação{pending.length > 1 ? "ões" : ""} pendente{pending.length > 1 ? "s" : ""}
          </p>
          <div className="mt-3 space-y-2">
            {pending.map((p) => (
              <div key={p.id} className="flex items-center justify-between rounded-lg bg-white px-4 py-3 shadow-sm">
                <div>
                  <p className="text-sm font-medium text-gray-900">{p.display_name}</p>
                  <p className="text-xs text-gray-500">{p.email}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    disabled={busy === p.username}
                    onClick={() => handleToggleActive(p.username, true)}
                    className="rounded-lg bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
                  >
                    {busy === p.username ? "..." : "Aprovar"}
                  </button>
                  <button
                    disabled={busy === p.username}
                    onClick={() => handleDeleteUser(p.username)}
                    className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
                  >
                    Recusar
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 overflow-hidden rounded-xl border bg-white shadow-sm">
        {loading ? (
          <div className="p-10 text-center text-sm text-gray-400">Carregando...</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-100">
            <thead className="bg-gray-50">
              <tr>
                {["Usuário", "Email", "Perfil", "Status", "Desde"].map((h) => (
                  <th key={h} className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 bg-white">
              {profiles.map((p) => {
                const isSelf = p.username === currentUser?.username;
                const isDisabled = busy === p.username;
                const isSelected = p.username === selectedUsername;
                return (
                  <tr
                    key={p.id}
                    onClick={() => setSelectedUsername(p.username)}
                    className={`cursor-pointer transition-colors ${isSelected ? "bg-voetur-50" : "hover:bg-gray-50"} ${isDisabled ? "opacity-50" : ""} ${!p.active ? "bg-amber-50/40" : ""}`}
                  >
                    <td className="px-6 py-4">
                      <p className="font-medium text-gray-900">{p.display_name}</p>
                      <p className="text-xs text-gray-400">@{p.username}</p>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">{p.email}</td>
                    <td className="px-6 py-4">
                      <select
                        value={p.role}
                        disabled={isSelf || isDisabled || !p.active}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => handleRoleChange(p.username, e.target.value)}
                        className="rounded-lg border border-gray-300 px-2 py-1 text-sm focus:border-voetur-500 focus:outline-none focus:ring-1 focus:ring-voetur-500 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option value="user">Usuário</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        disabled={isSelf || isDisabled}
                        onClick={(e) => { e.stopPropagation(); handleToggleActive(p.username, !p.active); }}
                        className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${p.active ? "bg-green-100 text-green-700 hover:bg-green-200" : "bg-amber-100 text-amber-700 hover:bg-amber-200"}`}
                      >
                        {p.active ? "Ativo" : "Pendente"}
                      </button>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-400">
                      {new Date(p.created_at).toLocaleDateString("pt-BR")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {selectedProfile && (
        <div className="mt-6">
          <h3 className="text-base font-semibold text-gray-900">
            Editar perfil — {selectedProfile.display_name}
          </h3>
          <UserProfileForm
            token={token}
            username={selectedUsername}
            isSelf={selectedUsername === currentUser?.username}
          />
        </div>
      )}
    </div>
  );
}
