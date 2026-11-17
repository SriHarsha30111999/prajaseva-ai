import { Link } from "react-router-dom";
import { api } from "../api";
import { fmtDate, useI18n } from "../i18n";
import { EmptyState, ErrorState, Spinner, useLoad } from "../components/ui";
import { HistoryTable, type HistoryRow } from "./ApplicationDetail";

type Row = HistoryRow & { app_id: number; app_no: string; applicant_name: string };

export default function HistoryPage() {
  const { t } = useI18n();
  const { data, error, loading, reload } = useLoad(() => api<Row[]>("/history"));
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">{t("nav_history")}</h1>
        <p className="text-sm text-slate-500">{t("history_global")}</p>
      </div>
      <div className="card">
        {loading && !data ? <Spinner /> : error ? <ErrorState message={error} onRetry={reload} /> : !data?.length ? <EmptyState title={t("no_history")} /> : (
          <HistoryTable rows={data} extra={(r) => (
            <Link to={`/applications/${(r as Row).app_id}`} className="font-medium text-brand-600 hover:underline">
              {(r as Row).app_no}<div className="text-xs font-normal text-slate-500">{(r as Row).applicant_name}</div>
            </Link>
          )} extraHead={t("app_id")} />
        )}
      </div>
    </div>
  );
}

export { fmtDate };
