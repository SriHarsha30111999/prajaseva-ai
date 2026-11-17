import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { FileText, FlaskConical, History, LayoutDashboard, LogOut, Menu, Sparkles, Users, X } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../context";
import { useI18n } from "../i18n";
import { useLoad } from "./ui";

export function LangToggle({ dark = false }: { dark?: boolean }) {
  const { lang, setLang } = useI18n();
  const base = "px-3 py-1 text-xs font-semibold transition";
  const on = dark ? "bg-white text-brand-900" : "bg-brand-600 text-white";
  const off = dark ? "text-white/80 hover:bg-white/10" : "text-slate-600 hover:bg-slate-100";
  return (
    <div className={`inline-flex overflow-hidden rounded-lg border ${dark ? "border-white/30" : "border-slate-300"}`}>
      <button className={`${base} ${lang === "te" ? on : off}`} onClick={() => setLang("te")}>తెలుగు</button>
      <button className={`${base} ${lang === "en" ? on : off}`} onClick={() => setLang("en")}>English</button>
    </div>
  );
}

export function Logo({ light = false }: { light?: boolean }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-saffron text-lg font-bold text-brand-900">ప్ర</div>
      <div className={light ? "text-white" : "text-slate-900"}>
        <div className="text-base font-bold leading-tight">{t("app_name")}</div>
        <div className={`text-[11px] leading-tight ${light ? "text-white/70" : "text-slate-500"}`}>{t("brand_sub")}</div>
      </div>
    </div>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { t, lang } = useI18n();
  const [open, setOpen] = useState(false);
  const ai = useLoad(() => api<{ mode: "live" | "demo"; model: string }>("/ai/status"));

  const links = [
    { to: "/", label: t("nav_dashboard"), icon: LayoutDashboard, end: true },
    { to: "/applications", label: t("nav_applications"), icon: FileText },
    { to: "/history", label: t("nav_history"), icon: History },
    ...(user?.role === "ADMIN" ? [{ to: "/users", label: t("nav_users"), icon: Users }] : []),
  ];

  return (
    <div className="min-h-screen lg:flex">
      {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-brand-900 p-4 transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="mb-8 flex items-center justify-between">
          <Logo light />
          <button className="text-white lg:hidden" onClick={() => setOpen(false)}><X size={20} /></button>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} onClick={() => setOpen(false)}
              className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${isActive ? "bg-white/15 text-white" : "text-white/70 hover:bg-white/10 hover:text-white"}`}>
              <l.icon size={18} /> {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="rounded-lg bg-white/10 p-3 text-white">
          <div className="text-sm font-semibold">{lang === "te" ? user?.full_name_te || user?.full_name : user?.full_name}</div>
          <div className="mb-3 text-xs text-white/70">{t("role_" + user?.role)}</div>
          <button onClick={logout} className="flex items-center gap-2 text-xs font-medium text-white/80 hover:text-white"><LogOut size={14} /> {t("logout")}</button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:px-8">
          <button className="lg:hidden" onClick={() => setOpen(true)}><Menu /></button>
          <div className="hidden text-sm text-slate-500 md:block">{t("tagline")}</div>
          <div className="ml-auto flex items-center gap-3">
            {ai.data && (
              <span className={`hidden items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset sm:inline-flex ${ai.data.mode === "demo" ? "bg-amber-50 text-amber-800 ring-amber-300" : "bg-emerald-50 text-emerald-700 ring-emerald-200"}`}>
                {ai.data.mode === "demo" ? <FlaskConical size={13} /> : <Sparkles size={13} />}
                {ai.data.mode === "demo" ? t("ai_mode_demo") : `${t("ai_mode_live")} · ${ai.data.model}`}
              </span>
            )}
            <LangToggle />
          </div>
        </header>
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-center text-xs text-amber-800 lg:px-8">{t("demo_banner")}</div>
        <main className="mx-auto w-full max-w-7xl flex-1 p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
