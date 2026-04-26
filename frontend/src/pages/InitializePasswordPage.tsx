import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch, ApiError } from "../lib/api";

const FIELD_CLASS = "mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 shadow-sm focus:border-voetur-500 focus:outline-none focus:ring-1 focus:ring-voetur-500";

export default function InitializePasswordPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError("As senhas não coincidem.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await apiFetch("/api/auth/initialize", { method: "POST", json: { username, password } });
      navigate("/login", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao definir senha.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-950">
      <div className="w-full max-w-sm rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-8 shadow-md">
        <div className="mb-4 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-voetur-800">
            <svg className="h-4 w-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <span className="text-sm font-black text-voetur-900 dark:text-voetur-100 tracking-wide">JARVIS</span>
        </div>

        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Definir senha</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Primeiro acesso — defina sua senha para o Jarvis.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">E-mail corporativo</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={FIELD_CLASS}
              placeholder="nome@voetur.com.br"
              required
              autoFocus
              autoComplete="username"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Nova senha</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={FIELD_CLASS}
              placeholder="mínimo 6 caracteres"
              required
              minLength={6}
              autoComplete="new-password"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Confirmar senha</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className={FIELD_CLASS}
              placeholder="••••••••"
              required
              autoComplete="new-password"
            />
          </div>

          {error && <p className="text-sm text-red-500 dark:text-red-400">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-voetur-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-voetur-700 disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-voetur-500 focus:ring-offset-2"
          >
            {loading ? "Salvando..." : "Definir senha"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-gray-500 dark:text-gray-400">
          <Link to="/login" className="font-medium text-voetur-600 hover:text-voetur-700 hover:underline">
            Voltar ao login
          </Link>
        </p>
      </div>
    </main>
  );
}
