import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiFetch, ApiError } from "../../lib/api";

type Profile = {
  id: string;
  username: string;
  display_name: string;
  email: string;
  role: "admin" | "user";
  active: boolean;
  created_at: string;
};

export default function AccessManagementPage() {
  const { token, user: currentUser } = useAuth();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchProfiles = useCallback(async () => {
    try {
      const data = await apiFetch<Profile[]>("/api/users", { token });
      // Pendentes primeiro, depois por data de criação
      data.sort((a, b) => {
        if (a.active !== b.active) return a.active ? 1 : -1;
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      });
      setProfiles(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar usuários.");
    } finally {
      setLoading(false);
    }
  }, [token]);

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

  const pending = profiles.filter((p) => !p.active);

  return (
    <div className="p-8">
      <h2 className="text-xl font-bold text-gray-900">Gestão de Acesso</h2>
      <p className="mt-1 text-sm text-gray-500">Gerencie usuários e perfis de acesso</p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {pending.length > 0 && (
        <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-semibold text-amber-800">
            {pending.length} solicitação{pending.length > 1 ? "ões" : ""} de acesso pendente{pending.length > 1 ? "s" : ""}
          </p>
          <div className="mt-3 space-y-2">
            {pending.map((p) => (
              <div key={p.id} className="flex items-center justify-between rounded-lg bg-white px-4 py-3 shadow-sm">
                <div>
                  <p className="text-sm font-medium text-gray-900">{p.display_name}</p>
                  <p className="text-xs text-gray-500">{p.email}</p>
                </div>
                <button
                  disabled={busy === p.username}
                  onClick={() => handleToggleActive(p.username, true)}
                  className="rounded-lg bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
                >
                  {busy === p.username ? "..." : "Aprovar"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 overflow-hidden rounded-xl border bg-white shadow-sm">
        {loading ? (
          <div className="p-10 text-center text-sm text-gray-400">Carregando...</div>
        ) : profiles.length === 0 ? (
          <div className="p-10 text-center text-sm text-gray-400">Nenhum usuário encontrado.</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-100">
            <thead className="bg-gray-50">
              <tr>
                {["Usuário", "Email", "Perfil", "Status", "Desde"].map((h) => (
                  <th key={h} className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 bg-white">
              {profiles.map((p) => {
                const isSelf = p.username === currentUser?.username;
                const isDisabled = busy === p.username;
                return (
                  <tr key={p.id} className={`${isDisabled ? "opacity-50" : ""} ${!p.active ? "bg-amber-50/40" : ""}`}>
                    <td className="px-6 py-4">
                      <p className="font-medium text-gray-900">{p.display_name}</p>
                      <p className="text-xs text-gray-400">@{p.username}</p>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">{p.email}</td>
                    <td className="px-6 py-4">
                      <select
                        value={p.role}
                        disabled={isSelf || isDisabled || !p.active}
                        onChange={(e) => handleRoleChange(p.username, e.target.value)}
                        className="rounded-lg border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option value="user">Usuário</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        disabled={isSelf || isDisabled}
                        onClick={() => handleToggleActive(p.username, !p.active)}
                        className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                          p.active
                            ? "bg-green-100 text-green-700 hover:bg-green-200"
                            : "bg-amber-100 text-amber-700 hover:bg-amber-200"
                        }`}
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
    </div>
  );
}
