import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch, ApiError } from "../lib/api";

const FIELD_CLASS = "mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 shadow-sm focus:border-voetur-500 focus:outline-none focus:ring-1 focus:ring-voetur-500";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [channel, setChannel] = useState("both");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await apiFetch("/api/auth/forgot-password", { method: "POST", json: { email, channel } });
      setSuccess(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao processar solicitação.");
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="w-full max-w-sm rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-8 shadow-md text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-voetur-100 dark:bg-voetur-900/30">
            <svg className="h-6 w-6 text-voetur-600 dark:text-voetur-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">Solicitação enviada!</h1>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Se o e-mail estiver cadastrado, você receberá o link em breve.
          </p>
          <Link to="/login" className="mt-6 inline-block text-sm font-medium text-voetur-600 hover:text-voetur-700 hover:underline">
            Voltar ao login
          </Link>
        </div>
      </main>
    );
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

        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Esqueci a senha</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Informe seu e-mail e escolha como receber o link de redefinição.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">E-mail corporativo</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={FIELD_CLASS}
              placeholder="nome@voetur.com.br"
              required
              autoFocus
              autoComplete="email"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Enviar por</label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              className={FIELD_CLASS}
            >
              <option value="email">E-mail</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="both">Ambos</option>
            </select>
          </div>

          {error && <p className="text-sm text-red-500 dark:text-red-400">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-voetur-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-voetur-700 disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-voetur-500 focus:ring-offset-2"
          >
            {loading ? "Enviando..." : "Enviar link"}
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
