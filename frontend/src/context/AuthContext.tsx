import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from "react";
import { apiFetch, setUnauthorizedHandler } from "../lib/api";

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
    apiFetch<User>("/api/auth/me", { token: stored, signal: controller.signal })
      .then((u) => { setToken(stored); setUser(u); })
      .catch((e) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) {
          localStorage.removeItem(TOKEN_KEY);
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  async function login(username: string, password: string) {
    const data = await apiFetch<{ access_token: string; user: User }>(
      "/api/auth/login",
      { method: "POST", json: { username, password } }
    );
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  }

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
  }, [logout]);

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
