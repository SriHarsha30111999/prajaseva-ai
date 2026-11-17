import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2, ClipboardCheck, ClipboardList, FileText, Gavel, MapPin, RotateCcw, Search, XCircle } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../context";
import { fmtDate, useI18n } from "../i18n";
import { ErrorState, Spinner, StatusBadge, useLoad } from "../components/ui";
import { AppTable, type AppRow } from "./Applications";

type Data = {
  stats: Record<string, number>;
  my_queue: number | null;
  recent: AppRow[];
};

const CARDS = [
  { key: "total", icon: FileText, color: "text-slate-600 bg-slate-100", status: "" },
  { key: "pending", icon: ClipboardList, color: "text-slate-600 bg-slate-100", status: "SUBMITTED" },
  { key: "under_scrutiny", icon: Search, color: "text-blue-600 bg-blue-50", status: "UNDER_SCRUTINY" },
  { key: "awaiting_field", icon: MapPin, color: "text-violet-600 bg-violet-50", status: "AWAITING_FIELD_VERIFICATION" },
  { key: "awaiting_final", icon: Gavel, color: "text-amber-600 bg-amber-50", status: "AWAITING_FINAL_REVIEW" },
  { key: "approved", icon: CheckCircle2, color: "text-emerald-600 bg-emerald-50", status: "APPROVED" },
  { key: "rejected", icon: XCircle, color: "text-red-600 bg-red-50", status: "REJECTED" },
  { key: "returned", icon: RotateCcw, color: "text-orange-600 bg-orange-50", status: "RETURNED_FOR_CORRECTION" },
];

export default function Dashboard() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const nav = useNavigate();
  const { data, error, loading, reload } = useLoad(() => api<Data>("/dashboard"));

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorState message={error} onRetry={reload} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t("welcome")}, {lang === "te" ? user?.full_name_te || user?.full_name : user?.full_name}</h1>
        <p className="text-sm text-slate-500">{t("role_" + user?.role)} · {fmtDate(new Date().toISOString(), lang)}</p>
      </div>

      {data.my_queue !== null && (
        <Link to="/applications?mine=1" className="card flex items-center justify-between border-l-4 border-l-saffron p-5 transition hover:shadow-md">
          <div className="flex items-center gap-4">
            <ClipboardCheck className="text-saffron" size={30} />
            <div>
              <div className="text-sm text-slate-500">{t("my_queue")}</div>
              <div className="text-xs text-slate-400">{t("my_queue_hint")}</div>
            </div>
          </div>
          <div className="text-3xl font-bold">{data.my_queue}</div>
        </Link>
      )}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {CARDS.map((c) => (
          <button key={c.key} onClick={() => nav(c.status ? `/applications?status=${c.status}` : "/applications")}
            className="card p-4 text-left transition hover:shadow-md">
            <div className={`mb-3 inline-flex rounded-lg p-2 ${c.color}`}><c.icon size={18} /></div>
            <div className="text-2xl font-bold">{data.stats[c.key]}</div>
            <div className="text-xs text-slate-500">{t("stat_" + c.key)}</div>
          </button>
        ))}
      </div>

      <div className="card">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h2 className="font-semibold">{t("recent_apps")}</h2>
          <Link to="/applications" className="text-sm font-medium text-brand-600 hover:underline">{t("view_all")}</Link>
        </div>
        <AppTable rows={data.recent} />
      </div>
    </div>
  );
}

export { StatusBadge };
