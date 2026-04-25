import { NavLink, Outlet, Link } from "react-router-dom";
import { useAuth, Role } from "../context/AuthContext";

type NavItem = {
  id: string;
  label: string;
  path: string;
  roles: Role[];
};

const NAV_ITEMS: NavItem[] = [
  { id: "home", label: "Início", path: "/", roles: ["admin", "user"] },
  { id: "moneypenny", label: "Moneypenny", path: "/moneypenny", roles: ["admin", "user"] },
  { id: "perfil", label: "Perfil", path: "/perfil", roles: ["admin", "user"] },
  { id: "access", label: "Gestão de Acesso", path: "/admin/acesso", roles: ["admin"] },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const visible = NAV_ITEMS.filter((i) => user && i.roles.includes(user.role));

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b bg-white px-6 py-3 shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-base font-bold text-gray-900">Sistema</span>
          <div className="flex items-center gap-3">
            <Link to="/perfil" className="text-sm text-gray-600 hover:text-blue-600 hover:underline">
              {user?.display_name}
            </Link>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                user?.role === "admin"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              {user?.role === "admin" ? "Admin" : "Usuário"}
            </span>
            <button
              onClick={logout}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 transition-colors hover:bg-gray-50"
            >
              Sair
            </button>
          </div>
        </div>
      </header>

      <div className="flex flex-1">
        <aside className="w-56 border-r bg-white">
          <nav className="p-3 space-y-0.5">
            {visible.map((item) => (
              <NavLink
                key={item.id}
                to={item.path}
                end={item.path === "/"}
                className={({ isActive }) =>
                  `block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-blue-50 text-blue-700"
                      : "text-gray-700 hover:bg-gray-50"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="flex-1 overflow-auto bg-gray-50">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
