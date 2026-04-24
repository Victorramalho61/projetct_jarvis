import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";

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

  const headers = { Authorization: `Bearer ${token}` };

  const fetchProfiles = useCallback(async () => {
    const r = await fetch("/api/users", { headers });
    if (r.ok) setProfiles(await r.json());
    setLoading(false);
  }, [token]);

  useEffect(() => { fetchProfiles(); }, [fetchProfiles]);

  async function handleRoleChange(username: string, role: string) {
    setBusy(username);
    await fetch(`/api/users/${username}/role`, {
      method: "PATCH",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    await fetchProfiles();
    setBusy(null);
  }

  async function handleToggleActive(username: string, active: boolean) {
    setBusy(username);
    await fetch(`/api/users/${username}/active`, {
      method: "PATCH",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ active }),
    });
    await fetchProfiles();
    setBusy(null);
  }

  return (
    <div className="p-8">
      <h2 className="text-xl font-bold text-gray-900">Gestão de Acesso</h2>
      <p className="mt-1 text-sm text-gray-500">
        Gerencie usuários e perfis de acesso
      </p>

      <div className="mt-6 overflow-hidden rounded-xl border bg-white shadow-sm">
        {loading ? (
          <div className="p-10 text-center text-sm text-gray-400">Carregando...</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-100">
            <thead className="bg-gray-50">
              <tr>
                {["Usuário", "Email", "Perfil", "Status", "Desde"].map((h) => (
                  <th
                    key={h}
                    className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                  >
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
                  <tr key={p.id} className={isDisabled ? "opacity-50" : ""}>
                    <td className="px-6 py-4">
                      <p className="font-medium text-gray-900">{p.display_name}</p>
                      <p className="text-xs text-gray-400">@{p.username}</p>
                    </td>

                    <td className="px-6 py-4 text-sm text-gray-600">{p.email}</td>

                    <td className="px-6 py-4">
                      <select
                        value={p.role}
                        disabled={isSelf || isDisabled}
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
                            : "bg-red-100 text-red-700 hover:bg-red-200"
                        }`}
                      >
                        {p.active ? "Ativo" : "Inativo"}
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
