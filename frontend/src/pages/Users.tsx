import { useState, type FormEvent } from "react";
import { RotateCcw } from "lucide-react";
import { api } from "../api";
import { useToast, type User } from "../context";
import { useI18n } from "../i18n";
import { ErrorState, Section, Spinner, useLoad } from "../components/ui";

const ROLES = ["VRO", "REVENUE_INSPECTOR", "TAHSILDAR", "ADMIN"];

export default function UsersPage() {
  const { t } = useI18n();
  const toast = useToast();
  const { data, error, loading, reload } = useLoad(() => api<User[]>("/admin/users"));
  const [form, setForm] = useState({ username: "", full_name: "", full_name_te: "", role: "VRO", password: "" });

  const create = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api("/admin/users", { body: form });
      toast.ok(t("user_created"));
      setForm({ username: "", full_name: "", full_name_te: "", role: "VRO", password: "" });
      reload();
    } catch (err: any) { toast.err(err.message); }
  };
  const toggle = async (u: User) => {
    try { await api(`/admin/users/${u.id}/toggle-active`, { method: "POST" }); reload(); } catch (err: any) { toast.err(err.message); }
  };
  const reset = async () => {
    if (!window.confirm(t("confirm_reset"))) return;
    try { await api("/admin/reset-demo-data", { method: "POST" }); toast.ok(t("reset_done")); } catch (err: any) { toast.err(err.message); }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("users_title")}</h1>
        <button className="btn-secondary" onClick={reset}><RotateCcw size={16} /> {t("reset_demo")}</button>
      </div>

      <Section title={t("nav_users")}>
        {loading && !data ? <Spinner /> : error ? <ErrorState message={error} onRetry={reload} /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
                <tr><th className="py-2">{t("full_name")}</th><th>{t("username")}</th><th>{t("role")}</th><th>{t("status")}</th><th /></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data!.map((u) => (
                  <tr key={u.id}>
                    <td className="py-2.5 font-medium">{u.full_name}</td>
                    <td className="font-mono text-xs">{u.username}</td>
                    <td>{t("role_" + u.role)}</td>
                    <td><span className={`rounded-full px-2 py-0.5 text-xs ${u.is_active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{u.is_active ? t("active") : t("inactive")}</span></td>
                    <td className="text-right"><button className="text-xs font-medium text-brand-600 hover:underline" onClick={() => toggle(u)}>{u.is_active ? t("deactivate") : t("activate")}</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title={t("add_user")}>
        <form onSubmit={create} className="grid gap-4 md:grid-cols-2">
          <div><label className="label">{t("username")}</label><input className="input" required minLength={3} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></div>
          <div><label className="label">{t("password")}</label><input className="input" type="password" required minLength={6} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
          <div><label className="label">{t("full_name")} (English)</label><input className="input" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
          <div><label className="label">{t("full_name")} (తెలుగు)</label><input className="input" value={form.full_name_te} onChange={(e) => setForm({ ...form, full_name_te: e.target.value })} /></div>
          <div>
            <label className="label">{t("role")}</label>
            <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {ROLES.map((r) => <option key={r} value={r}>{t("role_" + r)}</option>)}
            </select>
          </div>
          <div className="flex items-end"><button className="btn-primary">{t("create")}</button></div>
        </form>
      </Section>
    </div>
  );
}
