import { useAuth } from "../context/AuthContext";

export default function HomePage() {
  const { user } = useAuth();

  return (
    <div className="p-8">
      <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Início</h2>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Bem-vindo, {user?.display_name}</p>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">Usuário</p>
          <p className="mt-1 font-semibold text-gray-900 dark:text-gray-100">{user?.username}</p>
        </div>
        <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">Email</p>
          <p className="mt-1 font-semibold text-gray-900 dark:text-gray-100">{user?.email}</p>
        </div>
        <div className="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">Perfil</p>
          <p className="mt-1 font-semibold text-gray-900 dark:text-gray-100 capitalize">{user?.role}</p>
        </div>
      </div>
    </div>
  );
}
