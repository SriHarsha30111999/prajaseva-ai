import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../context";
import { useI18n } from "../i18n";
import { LangToggle, Logo } from "../components/Layout";
import { useLoad } from "../components/ui";

export default function Login() {
  const { user, login } = useAuth();
  const { t } = useI18n();
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // DEMO ONLY: the backend lists demo credentials so they can be shown here.
  const demo = useLoad(() => api<{ username: string; role: string; password: string }[]>("/meta/demo-users"));

  if (user) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
      nav("/");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <div className="flex flex-1 flex-col justify-between bg-brand-900 p-8 text-white lg:p-14">
        <Logo light />
        <div className="my-10 max-w-md">
          <h1 className="text-3xl font-bold leading-snug lg:text-4xl">{t("app_name")}</h1>
          <p className="mt-3 text-lg text-white/80">{t("tagline")}</p>
          <ul className="mt-8 space-y-3 text-sm text-white/80">
            {["login_pt1", "login_pt2", "login_pt3"].map((x) => (
              <li key={x} className="flex items-center gap-2"><ShieldCheck size={16} className="text-saffron" /> {t(x)}</li>
            ))}
          </ul>
        </div>
        <p className="max-w-md text-xs text-white/60">{t("demo_banner")}</p>
      </div>

      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="mb-6 flex justify-end"><LangToggle /></div>
          <form onSubmit={submit} className="card space-y-4 p-6">
            <h2 className="text-xl font-semibold">{t("sign_in")}</h2>
            <div>
              <label className="label">{t("username")}</label>
              <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
            </div>
            <div>
              <label className="label">{t("password")}</label>
              <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
            <button className="btn-primary w-full" disabled={busy}>{busy ? t("signing_in") : t("sign_in")}</button>
          </form>

          {demo.data && (
            <div className="card mt-5 p-4">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{t("demo_credentials")}</div>
              <div className="grid gap-2 sm:grid-cols-2">
                {demo.data.map((u) => (
                  <button key={u.username} type="button" onClick={() => { setUsername(u.username); setPassword(u.password); }}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-left text-xs transition hover:border-brand-500 hover:bg-brand-50">
                    <div className="font-semibold text-slate-800">{t("role_" + u.role)}</div>
                    <div className="text-slate-500">{u.username} / {u.password}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
