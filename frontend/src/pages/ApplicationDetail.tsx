import { useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, Circle, MinusCircle, PlayCircle, Trash2, UserCheck, XCircle } from "lucide-react";
import { api } from "../api";
import { useAuth, useToast } from "../context";
import { fmtDate, fmtMoney, useI18n } from "../i18n";
import { EmptyState, ErrorState, Field, Section, Spinner, StatusBadge, useLoad } from "../components/ui";
import { DocumentsTab, FieldTab, FinalTab } from "./StagePanels";
import type { Detail } from "../types";

export type HistoryRow = {
  id: number; action: string; user_name: string; role: string; remarks: string;
  previous_status: string | null; new_status: string | null; created_at: string;
};

export function HistoryTable({ rows, extra, extraHead }: { rows: HistoryRow[]; extra?: (r: HistoryRow) => ReactNode; extraHead?: string }) {
  const { t, lang } = useI18n();
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">{t("col_time")}</th>
            {extra && <th className="px-4 py-3">{extraHead}</th>}
            <th className="px-4 py-3">{t("col_action")}</th>
            <th className="px-4 py-3">{t("col_user")}</th>
            <th className="px-4 py-3">{t("col_remarks")}</th>
            <th className="px-4 py-3">{t("col_change")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 align-top">
          {rows.map((h) => (
            <tr key={h.id}>
              <td className="whitespace-nowrap px-4 py-3 text-slate-600">{fmtDate(h.created_at, lang, true)}</td>
              {extra && <td className="px-4 py-3">{extra(h)}</td>}
              <td className="px-4 py-3 font-medium">{t("action_" + h.action) === "action_" + h.action ? h.action : t("action_" + h.action)}</td>
              <td className="px-4 py-3">{h.user_name}<div className="text-xs text-slate-500">{t("role_" + h.role)}</div></td>
              <td className="max-w-xs px-4 py-3 text-slate-600">{h.remarks || "-"}</td>
              <td className="px-4 py-3">
                {h.previous_status === h.new_status ? <span className="text-xs text-slate-400">-</span> : (
                  <div className="flex flex-wrap items-center gap-1.5">
                    {h.previous_status ? <StatusBadge status={h.previous_status} /> : <span className="text-xs text-slate-400">-</span>}
                    <ArrowRight size={12} className="text-slate-400" />
                    {h.new_status && <StatusBadge status={h.new_status} />}
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------- workflow timeline

type StepState = "done" | "current" | "todo" | "skipped" | "warn";

function Timeline({ app }: { app: Detail }) {
  const { t } = useI18n();
  const s = app.status;
  const finished = s === "APPROVED" || s === "REJECTED";
  const afterVro = ["AWAITING_FIELD_VERIFICATION", "AWAITING_FINAL_REVIEW", "APPROVED", "REJECTED"].includes(s);
  const afterField = ["AWAITING_FINAL_REVIEW", "APPROVED", "REJECTED"].includes(s);

  const fieldState: StepState =
    s === "AWAITING_FIELD_VERIFICATION" ? "current" : afterField ? (app.field_verification_required === false ? "skipped" : "done") : "todo";
  const steps: { label: string; state: StepState; note?: string }[] = [
    { label: t("step_submitted"), state: "done" },
    {
      label: s === "RETURNED_FOR_CORRECTION" ? t("step_applicant") : t("step_scrutiny"),
      state: s === "RETURNED_FOR_CORRECTION" ? "warn" : afterVro ? "done" : "current",
    },
    { label: t("step_field"), state: fieldState, note: fieldState === "skipped" ? t("step_skipped") : fieldState === "todo" ? t("step_optional") : undefined },
    { label: t("step_final"), state: s === "AWAITING_FINAL_REVIEW" ? "current" : finished ? "done" : "todo" },
    { label: s === "REJECTED" ? t("status_REJECTED") : s === "APPROVED" ? t("status_APPROVED") : t("step_decision"), state: finished ? (s === "APPROVED" ? "done" : "warn") : "todo" },
  ];

  const style: Record<StepState, string> = {
    done: "bg-emerald-500 text-white",
    current: "bg-brand-600 text-white ring-4 ring-brand-100",
    todo: "bg-slate-200 text-slate-500",
    skipped: "bg-slate-100 text-slate-400 ring-1 ring-slate-300",
    warn: "bg-orange-500 text-white",
  };
  return (
    <ol className="grid grid-cols-5 gap-2">
      {steps.map((st, i) => (
        <li key={i} className="relative flex flex-col items-center text-center">
          {i > 0 && <span className={`absolute right-1/2 top-4 h-0.5 w-full -translate-y-1/2 ${["done", "current", "warn"].includes(st.state) || st.state === "skipped" ? "bg-emerald-300" : "bg-slate-200"}`} />}
          <span className={`relative z-10 flex h-8 w-8 items-center justify-center rounded-full ${style[st.state]}`}>
            {st.state === "done" ? <Check size={16} /> : st.state === "skipped" ? <MinusCircle size={16} /> : st.state === "warn" ? (s === "REJECTED" ? <XCircle size={16} /> : <UserCheck size={16} />) : st.state === "current" ? <PlayCircle size={16} /> : <Circle size={10} />}
          </span>
          <span className={`mt-2 text-xs font-medium ${st.state === "todo" ? "text-slate-400" : "text-slate-700"}`}>{st.label}</span>
          {st.note && <span className="text-[10px] text-slate-400">{st.note}</span>}
        </li>
      ))}
    </ol>
  );
}

// ------------------------------------------------------------- page

type Tab = "details" | "documents" | "field" | "final" | "history";

export default function ApplicationDetail() {
  const { id } = useParams();
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const toast = useToast();
  const nav = useNavigate();
  const { data, setData, error, loading, reload } = useLoad(() => api<Detail>(`/applications/${id}`), [id]);
  const [tab, setTab] = useState<Tab | null>(null);
  const firstTab = useRef<Tab | null>(null); // chosen once, so the tab does not jump after an action

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorState message={error} onRetry={reload} />;
  const app = data;

  const defaultTab: Tab = user?.role === "VRO" ? "documents" : user?.role === "REVENUE_INSPECTOR" ? "field" : user?.role === "TAHSILDAR" ? "final" : "details";
  firstTab.current ??= app.available_actions.length && user?.role !== "ADMIN" ? defaultTab : "details";
  const active = tab ?? firstTab.current;

  const can = (a: string) => app.available_actions.includes(a);
  const act = async (path: string, ok?: string, method = "POST") => {
    try {
      setData(await api<Detail>(`/applications/${app.id}/${path}`, { method }));
      toast.ok(ok ?? t("action_done"));
    } catch (e: any) { toast.err(e.message); }
  };
  const del = async () => {
    if (!window.confirm(t("confirm_delete"))) return;
    try { await api(`/admin/applications/${app.id}`, { method: "DELETE" }); nav("/applications"); } catch (e: any) { toast.err(e.message); }
  };

  const tabs: [Tab, string][] = [["details", t("tab_details")], ["documents", t("tab_documents")], ["field", t("tab_field")], ["final", t("tab_final")], ["history", t("tab_history")]];
  const ctx = { app, setApp: setData, reload };

  return (
    <div className="space-y-5">
      <Link to="/applications" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft size={14} /> {t("back")}</Link>

      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="font-mono text-xs text-slate-500">{app.app_no}</div>
            <h1 className="text-2xl font-bold">{app.applicant_name}</h1>
            <div className="mt-1 text-sm text-slate-500">{app.purpose} · {t("submitted_on")} {fmtDate(app.submitted_at, lang)}</div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <StatusBadge status={app.status} />
            {app.archived && <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-medium text-white">{t("archived_badge")}</span>}
            <div className="text-xs text-slate-500">{t("waiting_on")} <b>{t("role_" + app.current_stage)}</b></div>
          </div>
        </div>
        <div className="mt-6"><Timeline app={app} /></div>
        {(can("start_scrutiny") || can("resubmit") || can("archive")) && (
          <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
            {can("start_scrutiny") && <button className="btn-primary" onClick={() => act("start-scrutiny")}><PlayCircle size={16} /> {t("start_scrutiny")}</button>}
            {can("resubmit") && <button className="btn-secondary" onClick={() => act("resubmit")}>{t("resubmit_demo")}</button>}
            {can("archive") && <button className="btn-secondary ml-auto text-red-600" onClick={del}><Trash2 size={16} /> {t("delete_app")}</button>}
          </div>
        )}
      </div>

      <div className="flex gap-1 overflow-x-auto border-b border-slate-200">
        {tabs.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition ${active === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
            {label}
          </button>
        ))}
      </div>

      {active === "details" && (
        <Section title={t("applicant_details")}>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <Field label={t("applicant")}>{app.applicant_name}</Field>
            <Field label={t("guardian")}>{app.guardian_name}</Field>
            <Field label={t("age_gender")}>{app.age} / {app.gender}</Field>
            <Field label={t("address")}>{app.address}</Field>
            <Field label={t("village")}>{app.village}</Field>
            <Field label={t("mandal_district")}>{app.mandal} / {app.district}</Field>
            <Field label={t("occupation")}>{app.occupation}</Field>
            <Field label={t("household")}>{app.household_members}</Field>
            <Field label={t("declared_income")}><b>{fmtMoney(app.declared_income)}</b></Field>
            <Field label={t("purpose")}>{app.purpose}</Field>
            <Field label={t("fv_required")}>
              {app.field_verification_required === null ? t("fv_not_decided") : app.field_verification_required ? t("fv_yes") : t("fv_no")}
            </Field>
          </div>
        </Section>
      )}
      {active === "documents" && <DocumentsTab {...ctx} />}
      {active === "field" && <FieldTab {...ctx} />}
      {active === "final" && <FinalTab {...ctx} />}
      {active === "history" && (
        <Section title={t("history")}>
          {app.history.length ? <div className="-m-5"><HistoryTable rows={app.history} /></div> : <EmptyState title={t("no_history")} />}
        </Section>
      )}
    </div>
  );
}
