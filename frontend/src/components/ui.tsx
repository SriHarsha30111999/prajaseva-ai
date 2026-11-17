import { useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, FlaskConical, Inbox, Loader2, Sparkles } from "lucide-react";
import { useI18n } from "../i18n";

const STATUS_STYLE: Record<string, string> = {
  SUBMITTED: "bg-slate-100 text-slate-700 ring-slate-300",
  UNDER_SCRUTINY: "bg-blue-50 text-blue-700 ring-blue-200",
  RETURNED_FOR_CORRECTION: "bg-orange-50 text-orange-700 ring-orange-200",
  AWAITING_FIELD_VERIFICATION: "bg-violet-50 text-violet-700 ring-violet-200",
  AWAITING_FINAL_REVIEW: "bg-amber-50 text-amber-700 ring-amber-200",
  APPROVED: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  REJECTED: "bg-red-50 text-red-700 ring-red-200",
};

export function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  return (
    <span className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${STATUS_STYLE[status] ?? ""}`}>
      {t("status_" + status)}
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center justify-center gap-2 p-10 text-sm text-slate-500">
      <Loader2 className="animate-spin" size={18} /> {label ?? t("loading")}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <div className="card flex flex-col items-center gap-2 p-10 text-center">
      <AlertTriangle className="text-red-500" />
      <div className="font-medium">{t("error_title")}</div>
      <div className="text-sm text-slate-500">{message}</div>
      {onRetry && <button className="btn-secondary mt-2" onClick={onRetry}>{t("retry")}</button>}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center gap-1 p-10 text-center text-slate-500">
      <Inbox className="text-slate-300" size={36} />
      <div className="font-medium text-slate-600">{title}</div>
      {hint && <div className="text-sm">{hint}</div>}
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className="text-sm text-slate-800">{children}</div>
    </div>
  );
}

export function Section({ title, icon, right, children }: { title: string; icon?: ReactNode; right?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-3">
        <h3 className="flex items-center gap-2 font-semibold text-slate-800">{icon}{title}</h3>
        {right}
      </header>
      <div className="p-5">{children}</div>
    </section>
  );
}

/** Always shows whether an AI result came from a real LLM or from clearly-labelled demo samples. */
export function AIBanner({ mode, model, by, at }: { mode: "live" | "demo"; model: string; by?: string; at?: string }) {
  const { t } = useI18n();
  const demo = mode === "demo";
  return (
    <div className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs ring-1 ring-inset ${demo ? "bg-amber-50 text-amber-800 ring-amber-300" : "bg-brand-50 text-brand-700 ring-brand-100"}`}>
      {demo ? <FlaskConical size={15} className="mt-0.5 shrink-0" /> : <Sparkles size={15} className="mt-0.5 shrink-0" />}
      <div>
        <div className="font-semibold">{demo ? t("ai_demo_label") : t("ai_live_label")}</div>
        <div className="opacity-80">{[model !== "none (demo mode)" && model, by && `${t("generated_by")}: ${by}`, at].filter(Boolean).join(" · ")}</div>
      </div>
    </div>
  );
}

/** Fetch helper hook with loading / error / reload. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    setLoading(true);
    fn().then((d) => live && (setData(d), setError(""))).catch((e) => live && setError(e.message)).finally(() => live && setLoading(false));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, setData, error, loading, reload: () => setTick((x) => x + 1) };
}
