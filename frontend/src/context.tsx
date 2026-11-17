import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "./api";
import { CheckCircle2, XCircle } from "lucide-react";

export type User = { id: number; username: string; full_name: string; full_name_te: string; role: string; is_active: boolean };

type AuthCtx = {
  user: User | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};
const AuthContext = createContext<AuthCtx>(null as unknown as AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) return setReady(true);
    api<User>("/auth/me").then(setUser).catch(() => setToken(null)).finally(() => setReady(true));
  }, []);

  const login = async (username: string, password: string) => {
    const r = await api<{ access_token: string; user: User }>("/auth/login", { body: { username, password } });
    setToken(r.access_token);
    setUser(r.user);
  };
  const logout = () => {
    setToken(null);
    setUser(null);
  };
  return <AuthContext.Provider value={{ user, ready, login, logout }}>{children}</AuthContext.Provider>;
}
export const useAuth = () => useContext(AuthContext);

// ---- tiny toast system (success / error messages come from real API results only)
type Toast = { id: number; kind: "ok" | "err"; text: string };
const ToastContext = createContext<{ ok: (t: string) => void; err: (t: string) => void }>(null as any);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((kind: "ok" | "err", text: string) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, kind, text }]);
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), kind === "err" ? 7000 : 3500);
  }, []);
  return (
    <ToastContext.Provider value={{ ok: (t) => push("ok", t), err: (t) => push("err", t) }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2">
        {items.map((i) => (
          <div key={i.id} className={`flex items-start gap-2 rounded-lg px-4 py-3 text-sm text-white shadow-lg ${i.kind === "ok" ? "bg-emerald-600" : "bg-red-600"}`}>
            {i.kind === "ok" ? <CheckCircle2 size={18} className="mt-0.5 shrink-0" /> : <XCircle size={18} className="mt-0.5 shrink-0" />}
            <span>{i.text}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
export const useToast = () => useContext(ToastContext);
