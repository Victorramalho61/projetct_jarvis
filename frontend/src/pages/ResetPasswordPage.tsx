import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { apiFetch, ApiError } from "../lib/api";
import Icon from "../components/Icon";

const FIELD_CLASS = "mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 shadow-sm focus:border-voetur-500 focus:outline-none focus:ring-1 focus:ring-voetur-500";

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="w-full max-w-sm rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-8 shadow-md text-center">
          <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">Link inválido</h1>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Este link de redefinição é inválido ou expirou.
          </p>
          <Link to="/esqueci-senha" className="mt-4 inline-block text-sm font-medium text-voetur-600 hover:text-voetur-700 hover:underline">
            Solicitar novo link
          </Link>
        </div>
      </main>
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError("As senhas não coincidem.");
      return;
    }
    if (password.length < 8) {
      setError("A senha deve ter no mínimo 8 caracteres.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await apiFetch("/api/auth/reset-password", { method: "POST", json: { token, new_password: password } });
      navigate("/login", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao redefinir senha.");
    } finally {
      setLoading(false);
    }
  }

  const showNewLinkSuggestion = error.includes("inválido") || error.includes("expirado");

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

        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Redefinir senha</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Defina sua nova senha para o JARVIS.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Nova senha</label>
            <div className="relative">
              <input
                type={showPw ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={FIELD_CLASS + " pr-10"}
                placeholder="mínimo 8 caracteres"
                required
                minLength={8}
                autoComplete="new-password"
                autoFocus
              />
              <button
                type="button"
                onClick={() => setShowPw((v) => !v)}
                aria-label={showPw ? "Ocultar senha" : "Mostrar senha"}
                className="absolute inset-y-0 right-2 h-full w-9 grid place-items-center text-gray-400 hover:text-gray-600"
              >
                <Icon name={showPw ? "eye-off" : "eye"} size={16} />
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Confirmar senha</label>
            <div className="relative">
              <input
                type={showConfirm ? "text" : "password"}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className={FIELD_CLASS + " pr-10"}
                placeholder="••••••••"
                required
                autoComplete="new-password"
              />
              <button
                type="button"
                onClick={() => setShowConfirm((v) => !v)}
                aria-label={showConfirm ? "Ocultar senha" : "Mostrar senha"}
                className="absolute inset-y-0 right-2 h-full w-9 grid place-items-center text-gray-400 hover:text-gray-600"
              >
                <Icon name={showConfirm ? "eye-off" : "eye"} size={16} />
              </button>
            </div>
          </div>

          {error && (
            <div className="space-y-1">
              <p className="text-sm text-red-500 dark:text-red-400">{error}</p>
              {showNewLinkSuggestion && (
                <Link to="/esqueci-senha" className="text-sm font-medium text-voetur-600 hover:text-voetur-700 hover:underline">
                  Solicitar novo link
                </Link>
              )}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-voetur-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-voetur-700 disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-voetur-500 focus:ring-offset-2"
          >
            {loading ? "Salvando..." : "Redefinir senha"}
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
