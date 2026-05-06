import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, Link, useNavigate } from "react-router-dom";
import { useAuth, Role } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { useNotifications } from "../hooks/useNotifications";
import Icon from "./Icon";

type NavItem = {
  id: string;
  label: string;
  path: string;
  icon: string;
  roles: Role[];
};

const NAV_ITEMS: NavItem[] = [
  { id: "home",       label: "Início",          path: "/",                     icon: "home",     roles: ["admin", "user"] },
  { id: "moneypenny", label: "Moneypenny",       path: "/moneypenny",           icon: "sparkle",  roles: ["admin", "user"] },
  { id: "access",     label: "Gestão de Acesso", path: "/admin/acesso",         icon: "users",    roles: ["admin", "user"] },
  { id: "logs",       label: "Logs",             path: "/admin/logs",           icon: "file",     roles: ["admin"] },
  { id: "monitoring",    label: "Monitoramento",    path: "/admin/monitoramento",  icon: "chart",      roles: ["admin"] },
  { id: "freshservice",  label: "Freshservice",     path: "/freshservice",         icon: "briefcase",  roles: ["admin"] },
  { id: "agents",   label: "Agentes",   path: "/admin/agentes", icon: "cpu",    roles: ["admin"] },
  { id: "expenses",   label: "Gastos TI",   path: "/admin/gastos",      icon: "wallet", roles: ["admin"] },
  { id: "governance", label: "Governança",  path: "/admin/governanca",  icon: "shield", roles: ["admin"] },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const notifications = useNotifications();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const notifRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const visible = NAV_ITEMS.filter((i) => user && i.roles.includes(user.role));

  const initials = user?.display_name
    ?.split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("") ?? "?";

  // Fecha dropdowns ao clicar fora
  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setNotifOpen(false);
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setSearchOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  // Atalho Ctrl/Cmd+K para busca
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
        setSearchQuery("");
      }
      if (e.key === "Escape") {
        setSearchOpen(false);
        setNotifOpen(false);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

const filteredNav = visible.filter((i) =>
    i.label.toLowerCase().includes(searchQuery.toLowerCase())
  );

  function handleSearchSelect(path: string) {
    navigate(path);
    setSearchOpen(false);
    setSearchQuery("");
    searchInputRef.current?.blur();
  }

  const notifTypeStyle: Record<string, string> = {
    down:           "bg-red-500",
    degraded:       "bg-amber-500",
    pending_user:   "bg-blue-500",
    agent_proposal: "bg-orange-500",
    cto_message:    "bg-indigo-500",
    critical_event: "bg-red-600",
  };

  // Badges movidos para AgentsDashboard (tabs internas)

  const SidebarContent = () => (
    <>
      <div className="px-3 py-4">
        <div className="mb-2 px-2 font-mono text-[10px] uppercase tracking-[0.2em] text-gray-400 dark:text-gray-500">
          Navegação
        </div>
        <nav className="space-y-0.5">
          {visible.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              end={item.path === "/"}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `relative flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-[14px] font-medium transition-colors ${
                  isActive
                    ? "bg-brand-soft text-brand-deep dark:bg-brand-green/15 dark:text-brand-mid"
                    : "text-gray-600 hover:bg-brand-soft hover:text-brand-deep dark:text-gray-400 dark:hover:bg-brand-green/10 dark:hover:text-brand-mid"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full bg-brand-green" />
                  )}
                  <Icon name={item.icon} size={17} strokeWidth={isActive ? 2 : 1.75} />
                  <span className="flex-1">{item.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="mt-auto border-t border-gray-100 dark:border-gray-800 px-3 py-4">
        <nav className="space-y-0.5">
          <NavLink
            to="/perfil"
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `relative flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-[14px] font-medium transition-colors ${
                isActive
                  ? "bg-brand-soft text-brand-deep dark:bg-brand-green/15 dark:text-brand-mid"
                  : "text-gray-600 hover:bg-brand-soft hover:text-brand-deep dark:text-gray-400 dark:hover:bg-brand-green/10 dark:hover:text-brand-mid"
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full bg-brand-green" />
                )}
                <Icon name="settings" size={17} strokeWidth={isActive ? 2 : 1.75} />
                <span>Perfil</span>
              </>
            )}
          </NavLink>
        </nav>
      </div>
    </>
  );

  return (
    <div className="flex min-h-screen flex-col bg-white dark:bg-gray-950">
      {/* Header */}
      <header className="h-16 bg-brand-ink text-white flex items-center px-4 sm:px-6 gap-3 relative z-10 shadow-md">
        {/* Hamburguer mobile */}
        <button
          onClick={() => setMobileOpen(true)}
          className="md:hidden h-10 w-10 grid place-items-center rounded-lg hover:bg-white/10"
          aria-label="Abrir menu"
        >
          <Icon name="menu" size={20} />
        </button>

        {/* Logo + JARVIS */}
        <div className="flex items-center gap-3">
          <img
            src="/grupo-voetur-branco.svg"
            alt="Grupo Voetur"
            className="block select-none"
            style={{ height: 24, width: "auto" }}
          />
          <span className="w-px h-6 bg-white/15" />
          <div className="leading-none">
            <div className="text-[15px] font-extrabold tracking-[0.2em] inline-flex items-baseline">
              JARVIS
              <sup className="ml-1 text-[8px] font-medium tracking-normal opacity-70">®</sup>
            </div>
            <div className="hidden sm:block text-[10px] text-emerald-300/90 mt-0.5">Sistema interno</div>
          </div>
        </div>

        {/* Busca */}
        <div className="relative hidden md:block ml-4" ref={searchRef}>
          <div className="relative flex items-center">
            <span className="absolute left-3 text-emerald-50/50 pointer-events-none">
              <Icon name="search" size={15} />
            </span>
            <input
              ref={searchInputRef}
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setSearchOpen(true); }}
              onFocus={() => setSearchOpen(true)}
              placeholder="Buscar…"
              className="h-9 w-64 lg:w-80 rounded-lg bg-white/[0.08] pl-8 pr-14 text-[13px] text-white placeholder:text-emerald-50/50 focus:outline-none focus:bg-white/[0.15] transition-colors"
            />
            <span className="absolute right-3 font-mono text-[10px] text-emerald-50/40 border border-white/15 rounded px-1.5 py-0.5 pointer-events-none">⌘K</span>
          </div>

          {searchOpen && (
            <div className="absolute top-full left-0 mt-2 w-64 lg:w-80 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-pop z-50 overflow-hidden">
              <div className="py-1 max-h-64 overflow-y-auto">
                {filteredNav.length === 0 && (
                  <p className="px-4 py-3 text-sm text-gray-400 dark:text-gray-500">Nenhum resultado</p>
                )}
                {filteredNav.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleSearchSelect(item.path)}
                    className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                  >
                    <Icon name={item.icon} size={15} />
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex-1" />

        {/* Toggle tema claro/escuro */}
        <button
          onClick={toggleTheme}
          title={theme === "dark" ? "Modo claro" : "Modo escuro"}
          aria-label={theme === "dark" ? "Modo claro" : "Modo escuro"}
          className="h-10 w-10 grid place-items-center rounded-lg hover:bg-white/10 transition-colors text-white"
        >
          {theme === "dark" ? (
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="4"/>
              <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
            </svg>
          )}
        </button>

        {/* Notificações */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => setNotifOpen((v) => !v)}
            className="relative h-10 w-10 grid place-items-center rounded-lg hover:bg-white/10"
            aria-label="Notificações"
          >
            <Icon name="bell" size={18} />
            {notifications.length > 0 && (
              <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-red-500 ring-2 ring-brand-ink animate-pulse" />
            )}
          </button>

          {notifOpen && (
            <div className="absolute right-0 top-full mt-2 w-80 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-pop z-50 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">Alertas</span>
                {notifications.length > 0 && (
                  <span className="rounded-full bg-red-100 dark:bg-red-900/30 px-2 py-0.5 text-xs font-semibold text-red-600 dark:text-red-400">
                    {notifications.length}
                  </span>
                )}
              </div>
              <div className="max-h-80 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="px-4 py-6 text-center">
                    <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
                      <svg className="h-5 w-5 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Tudo certo por aqui!</p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-50 dark:divide-gray-800">
                    {notifications.map((n) => (
                      <div
                        key={n.id}
                        className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors cursor-pointer"
                        onClick={() => {
                          if (n.type === "pending_user") navigate("/admin/acesso");
                          else navigate("/admin/monitoramento");
                          setNotifOpen(false);
                        }}
                      >
                        <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${notifTypeStyle[n.type] ?? "bg-gray-400"} ${n.type === "down" ? "animate-pulse" : ""}`} />
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{n.title}</p>
                          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400 truncate">{n.body}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {notifications.length > 0 && (
                <div className="border-t border-gray-100 dark:border-gray-800 px-4 py-2.5">
                  <button
                    onClick={() => { navigate("/admin/monitoramento"); setNotifOpen(false); }}
                    className="text-xs text-brand-green hover:underline"
                  >
                    Ver monitoramento →
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Usuário */}
        <div className="hidden sm:flex items-center gap-3 pl-3 border-l border-white/10">
          <div className="text-right leading-tight">
            <div className="text-[13px] font-semibold">{user?.display_name}</div>
            <div className="mt-0.5 flex items-center justify-end">
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                user?.role === "admin"
                  ? "bg-brand-deep text-white"
                  : "bg-transparent border border-white/30 text-white"
              }`}>
                {user?.role === "admin" ? "Admin" : "Colaborador"}
              </span>
            </div>
          </div>
          <Link
            to="/perfil"
            className="h-9 w-9 rounded-full bg-brand-green grid place-items-center text-white font-semibold text-sm hover:bg-brand-deep transition-colors"
          >
            {initials}
          </Link>
        </div>

        {/* Sair */}
        <button
          onClick={logout}
          className="inline-flex items-center gap-2 h-9 px-3 rounded-lg border border-white/30 text-white text-sm font-medium hover:bg-white/10 transition-colors"
        >
          <Icon name="log-out" size={16} />
          <span className="hidden sm:inline">Sair</span>
        </button>
      </header>

      <div className="flex flex-1">
        {/* Sidebar desktop */}
        <aside className="hidden md:flex w-56 flex-col border-r border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900">
          <SidebarContent />
        </aside>

        {/* Drawer mobile */}
        {mobileOpen && (
          <>
            <div
              className="md:hidden fixed inset-0 bg-black/40 z-40"
              onClick={() => setMobileOpen(false)}
            />
            <aside className="md:hidden fixed top-0 left-0 bottom-0 w-[260px] bg-white dark:bg-gray-900 border-r border-gray-100 dark:border-gray-800 z-50 flex flex-col">
              <div className="h-16 px-4 flex items-center justify-between border-b border-gray-100 dark:border-gray-800">
                <div className="flex items-center gap-2">
                  <img src="/grupo-voetur-escuro.svg" alt="Grupo Voetur" className="block dark:hidden select-none" style={{ height: 20, width: "auto" }} />
                  <img src="/grupo-voetur-branco.svg" alt="Grupo Voetur" className="hidden dark:block select-none" style={{ height: 20, width: "auto" }} />
                  <span className="text-[14px] font-extrabold tracking-[0.2em] text-brand-ink dark:text-white">JARVIS</span>
                </div>
                <button
                  onClick={() => setMobileOpen(false)}
                  className="h-9 w-9 grid place-items-center rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 dark:text-gray-300"
                  aria-label="Fechar menu"
                >
                  <Icon name="x" size={18} />
                </button>
              </div>
              <SidebarContent />
            </aside>
          </>
        )}

        {/* Busca mobile (overlay) */}
        {searchOpen && (
          <div className="md:hidden fixed inset-0 z-50 bg-black/50 flex items-start justify-center pt-16 px-4">
            <div className="w-full max-w-sm rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-pop overflow-hidden">
              <div className="p-3">
                <input
                  ref={searchInputRef}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Buscar página..."
                  className="w-full rounded-lg bg-gray-50 dark:bg-gray-800 px-3 py-2.5 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none"
                />
              </div>
              <div className="pb-2 max-h-64 overflow-y-auto">
                {filteredNav.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleSearchSelect(item.path)}
                    className="flex w-full items-center gap-3 px-4 py-3 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    <Icon name={item.icon} size={15} />
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        <main className="flex-1 overflow-auto bg-gray-50 dark:bg-gray-950">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
