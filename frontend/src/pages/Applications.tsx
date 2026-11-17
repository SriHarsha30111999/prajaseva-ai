import { useSearchParams, useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../context";
import { fmtDate, useI18n } from "../i18n";
import { EmptyState, ErrorState, Spinner, StatusBadge, useLoad } from "../components/ui";

export type AppRow = {
  id: number; app_no: string; applicant_name: string; village: string; mandal: string; purpose: string;
  declared_income: number; submitted_at: string; status: string; current_stage: string;
};

const STATUSES = ["SUBMITTED", "UNDER_SCRUTINY", "RETURNED_FOR_CORRECTION", "AWAITING_FIELD_VERIFICATION", "AWAITING_FINAL_REVIEW", "APPROVED", "REJECTED"];

export function AppTable({ rows }: { rows: AppRow[] }) {
  const { t, lang } = useI18n();
  const nav = useNavigate();
  if (!rows.length) return <EmptyState title={t("no_apps")} hint={t("no_apps_hint")} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-5 py-3">{t("applicant")}</th>
            <th className="px-5 py-3">{t("app_id")}</th>
            <th className="px-5 py-3">{t("submitted_on")}</th>
            <th className="px-5 py-3">{t("stage")}</th>
            <th className="px-5 py-3">{t("status")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr key={r.id} onClick={() => nav(`/applications/${r.id}`)} className="cursor-pointer transition hover:bg-brand-50/50">
              <td className="px-5 py-3">
                <div className="font-medium text-slate-900">{r.applicant_name}</div>
                <div className="text-xs text-slate-500">{r.village}, {r.mandal}</div>
              </td>
              <td className="px-5 py-3 font-mono text-xs">{r.app_no}</td>
              <td className="whitespace-nowrap px-5 py-3 text-slate-600">{fmtDate(r.submitted_at, lang)}</td>
              <td className="px-5 py-3">{t("role_" + r.current_stage)}</td>
              <td className="px-5 py-3"><StatusBadge status={r.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Applications() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const q = params.get("q") ?? "";
  const mine = params.get("mine") === "1";

  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    v ? p.set(k, v) : p.delete(k);
    setParams(p, { replace: true });
  };

  const { data, error, loading, reload } = useLoad(
    () => api<AppRow[]>(`/applications?${new URLSearchParams({ ...(status && { status }), ...(q && { q }), ...(mine && { mine: "true" }) })}`),
    [status, q, mine],
  );

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("nav_applications")}</h1>
      <div className="card flex flex-wrap items-center gap-3 p-4">
        <div className="relative min-w-60 flex-1">
          <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
          <input className="input pl-9" placeholder={t("search_ph")} value={q} onChange={(e) => set("q", e.target.value)} />
        </div>
        <select className="input w-auto" value={status} onChange={(e) => set("status", e.target.value)}>
          <option value="">{t("all_statuses")}</option>
          {STATUSES.map((s) => <option key={s} value={s}>{t("status_" + s)}</option>)}
        </select>
        {user?.role !== "ADMIN" && (
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input type="checkbox" checked={mine} onChange={(e) => set("mine", e.target.checked ? "1" : "")} /> {t("only_mine")}
          </label>
        )}
      </div>
      <div className="card">
        {loading && !data ? <Spinner /> : error ? <ErrorState message={error} onRetry={reload} /> : <AppTable rows={data ?? []} />}
      </div>
    </div>
  );
}
