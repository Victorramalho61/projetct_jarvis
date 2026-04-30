import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/api";
import Icon from "../components/Icon";

export default function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Credenciais inválidas. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen">
      {/* Painel esquerdo — identidade visual Voetur */}
      <aside className="relative hidden md:flex md:w-[42%] flex-col bg-brand-ink overflow-hidden voetur-pattern">
        <div className="voetur-grid absolute inset-0 opacity-70" />
        <div className="noise absolute inset-0" />

        {/* Círculos decorativos */}
        <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full border border-white/8 spin-slow" />
        <div className="absolute -bottom-32 -left-20 w-[28rem] h-[28rem] rounded-full border border-emerald-500/10" />
        <div className="absolute top-1/3 right-12 w-2 h-2 rounded-full bg-brand-mid pulse-soft" />
        <div className="absolute top-1/2 right-24 w-1 h-1 rounded-full bg-emerald-200/60" />

        <div className="relative flex h-full flex-col justify-between p-10 lg:p-14">
          {/* Logo + versão */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <img src="/grupo-voetur-branco.svg" alt="Grupo Voetur" className="block select-none" style={{ height: 26, width: "auto" }} />
              <span className="w-px h-6 bg-white/15" />
              <div className="leading-none">
                <div className="text-[17px] font-extrabold tracking-[0.22em] text-white inline-flex items-baseline">
                  JARVIS
                  <sup className="ml-1 text-[9px] font-medium tracking-normal opacity-70">®</sup>
                </div>
                <div className="text-[10px] text-emerald-300/90 mt-1">Sistema interno</div>
              </div>
            </div>
            <span className="font-mono text-[11px] tracking-widest text-emerald-300/60 uppercase">2026</span>
          </div>

          {/* Headline */}
          <div className="space-y-6 max-w-sm">
            <p className="font-mono text-[11px] tracking-[0.28em] text-emerald-300/70 uppercase">
              Mordomo digital · Centralizador de IAs
            </p>
            <h1 className="text-[38px] lg:text-[48px] leading-[1.05] font-extrabold tracking-tight text-white">
              Cada colaborador,<br />
              com seu próprio<br />
              <span className="text-brand-mid">mordomo digital.</span>
            </h1>
            <div className="flex items-center gap-3 text-[12px] text-emerald-50/60">
              <a href="https://grupovoetur.com.br/" target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 hover:text-white transition-colors">
                <Icon name="globe" size={12} />
                grupovoetur.com.br
              </a>
              <span className="text-emerald-50/20">·</span>
              <a href="https://www.instagram.com/grupovoetur/" target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 hover:text-white transition-colors">
                <Icon name="sparkle" size={12} />
                @grupovoetur
              </a>
              <span className="text-emerald-50/20">·</span>
              <a href="https://br.linkedin.com/company/grupo-voetur" target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 hover:text-white transition-colors">
                <Icon name="briefcase" size={12} />
                LinkedIn
              </a>
            </div>
          </div>

          {/* Stats + sede */}
          <div className="flex items-end justify-between">
            <div className="flex gap-8 text-emerald-50/60">
              <div>
                <div className="text-2xl font-bold text-white">+1.200</div>
                <div className="text-[11px] uppercase tracking-wider mt-1">Colaboradores</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-white">12</div>
                <div className="text-[11px] uppercase tracking-wider mt-1">Empresas</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-white">40+</div>
                <div className="text-[11px] uppercase tracking-wider mt-1">Anos</div>
              </div>
            </div>
            <span className="font-mono text-[10px] text-emerald-50/40">Brasília · DF</span>
          </div>
        </div>
      </aside>

      {/* Painel direito — formulário */}
      <div className="flex flex-1 flex-col items-center justify-center bg-gray-50 dark:bg-gray-950 px-6 py-12">
        {/* Logo mobile */}
        <div className="md:hidden mb-8 flex items-center gap-3">
          <img src="/grupo-voetur-escuro.svg" alt="Grupo Voetur" className="block select-none" style={{ height: 22, width: "auto" }} />
          <span className="w-px h-6 bg-brand-ink/18" />
          <div className="leading-none">
            <div className="text-[16px] font-extrabold tracking-[0.2em] text-brand-ink inline-flex items-baseline">
              JARVIS<sup className="ml-1 text-[8px] opacity-60">®</sup>
            </div>
            <div className="text-[10px] text-brand-deep mt-0.5">Sistema interno</div>
          </div>
        </div>

        <div className="w-full max-w-[420px]">
          <div className="rounded-2xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-7 sm:p-9 shadow-card">
            <header className="mb-6">
              <h2 className="text-[26px] font-bold tracking-tight text-brand-ink dark:text-gray-100">Bem-vindo</h2>
              <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">Entre com sua conta corporativa Voetur.</p>
            </header>

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              {/* E-mail */}
              <div className="space-y-1.5">
                <label htmlFor="email" className="block text-[13px] font-medium text-brand-ink dark:text-gray-300">
                  E-mail corporativo
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-3 flex items-center text-gray-400 pointer-events-none">
                    <Icon name="mail" size={16} />
                  </span>
                  <input
                    id="email"
                    type="email"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="email"
                    placeholder="seu.nome@voetur.com.br"
                    required
                    autoFocus
                    className="w-full h-11 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 pl-9 pr-3.5 text-[14px] text-brand-ink dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:border-brand-mid focus:ring-2 focus:ring-brand-mid/30 transition-shadow"
                  />
                </div>
              </div>

              {/* Senha */}
              <div className="space-y-1.5">
                <label htmlFor="pw" className="block text-[13px] font-medium text-brand-ink dark:text-gray-300">
                  Senha
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-3 flex items-center text-gray-400 pointer-events-none">
                    <Icon name="lock" size={16} />
                  </span>
                  <input
                    id="pw"
                    type={showPw ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    placeholder="••••••••"
                    required
                    className="w-full h-11 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 pl-9 pr-10 text-[14px] text-brand-ink dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:border-brand-mid focus:ring-2 focus:ring-brand-mid/30 transition-shadow"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw((v) => !v)}
                    aria-label={showPw ? "Ocultar senha" : "Mostrar senha"}
                    className="absolute inset-y-0 right-2 h-full w-9 grid place-items-center text-gray-400 hover:text-brand-deep rounded-md"
                  >
                    <Icon name={showPw ? "eye-off" : "eye"} size={16} />
                  </button>
                </div>
              </div>

              {/* Manter conectado + Esqueci */}
              <div className="flex items-center justify-between text-[13px]">
                <label className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 accent-brand-green"
                  />
                  Manter conectado
                </label>
                <Link to="/esqueci-senha" className="text-voetur-600 font-medium hover:underline text-xs">Esqueci a senha</Link>
              </div>

              {error && <p className="text-sm text-rose-600">{error}</p>}

              <button
                type="submit"
                disabled={loading}
                className="inline-flex w-full h-12 items-center justify-center gap-2 rounded-lg bg-brand-green text-[15px] font-semibold text-white transition-colors hover:bg-brand-deep disabled:opacity-50 focus:outline-none shadow-sm"
              >
                {loading ? "Entrando…" : (
                  <>
                    Entrar
                    <Icon name="arrow-right" size={16} />
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 pt-6 border-t border-gray-100 dark:border-gray-800 text-center text-sm">
              <span className="text-gray-500 dark:text-gray-400">Primeiro acesso? </span>
              <Link to="/solicitar-acesso" className="text-brand-deep font-semibold hover:underline">
                Solicitar Acesso
              </Link>
            </div>
          </div>

          <p className="mt-6 text-center font-mono text-[11px] text-gray-400 dark:text-gray-500 flex items-center justify-center gap-2">
            <img src="/grupo-voetur-escuro.svg" alt="" className="select-none opacity-40" style={{ height: 14, width: "auto" }} />
            © Grupo Voetur 2026 · Conexão segura TLS 1.3
          </p>
        </div>
      </div>
    </main>
  );
}
