import { createContext, useContext, useEffect, useState, ReactNode } from "react";

export type Role = "admin" | "user";

export type User = {
  username: string;
  display_name: string;
  email: string;
  role: Role;
  active: boolean;
};

type AuthContextType = {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | null>(null);

const TOKEN_KEY = "auth_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) { setLoading(false); return; }
    const controller = new AbortController();
    fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${stored}` },
      signal: controller.signal,
    })
      .then((r) => (r.ok ? (r.json() as Promise<User>) : Promise.reject()))
      .then((u) => { setToken(stored); setUser(u); })
      .catch((e) => { if (e?.name !== "AbortError") localStorage.removeItem(TOKEN_KEY); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  async function login(username: string, password: string) {
    const r = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!r.ok) {
      const err = await r.json();
      throw new Error((err as { detail?: string }).detail ?? "Erro ao fazer login");
    }
    const data = (await r.json()) as { access_token: string; user: User };
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
