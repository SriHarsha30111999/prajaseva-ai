import { useState, type FormEvent } from "react";
import { AlertTriangle, CheckCircle2, Download, FileText, Gavel, Loader2, Send, Sparkles, Upload, XCircle } from "lucide-react";
import { api, downloadDocument } from "../api";
import { useToast } from "../context";
import { fmtDate, useI18n } from "../i18n";
import { AIBanner, EmptyState, Section } from "../components/ui";
import type { AILog, Detail, PanelProps } from "../types";

const DOC_TYPES = ["AADHAAR", "RATION_CARD", "INCOME_DECLARATION", "SALARY_SLIP", "OTHER"];

/** Wraps an async action with a busy flag + error toast. */
function useBusy() {
  const toast = useToast();
  const [busy, setBusy] = useState("");
  const run = async (name: string, fn: () => Promise<void>) => {
    setBusy(name);
    try { await fn(); } catch (e: any) { toast.err(e.message); } finally { setBusy(""); }
  };
  return { busy, run };
}

function Spin({ on, children }: { on: boolean; children: React.ReactNode }) {
  return <>{on ? <Loader2 size={16} className="animate-spin" /> : null}{children}</>;
}

function ViewOnly() {
  const { t } = useI18n();
  return <div className="rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-600">{t("read_only_notice")}</div>;
}

const List = ({ items, tone }: { items: string[]; tone: "warn" | "ok" | "plain" }) => (
  <ul className="space-y-1.5 text-sm">
    {items.map((x, i) => (
      <li key={i} className="flex gap-2">
        {tone === "warn" ? <AlertTriangle size={15} className="mt-1 shrink-0 text-amber-500" /> : tone === "ok" ? <CheckCircle2 size={15} className="mt-1 shrink-0 text-emerald-500" /> : <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />}
        <span>{x}</span>
      </li>
    ))}
  </ul>
);

// =================================================================== Stage 1: Document review

function AnalysisView({ log }: { log: AILog }) {
  const { t, lang } = useI18n();
  const o = log.output ?? {};
  const sev: Record<string, string> = { high: "bg-red-50 text-red-700", medium: "bg-amber-50 text-amber-700", low: "bg-slate-100 text-slate-600" };
  return (
    <div className="space-y-5">
      <AIBanner mode={log.mode} model={log.model} by={log.requested_by} at={fmtDate(log.created_at, lang, true)} />
      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <h4 className="label">{t("missing_info")}</h4>
          {o.missing_information?.length ? <List items={o.missing_information} tone="warn" /> : <div className="text-sm text-slate-500">{t("none_found")}</div>}
        </div>
        <div>
          <h4 className="label">{t("discrepancies")}</h4>
          {o.discrepancies?.length ? (
            <ul className="space-y-2 text-sm">
              {o.discrepancies.map((d: any, i: number) => (
                <li key={i} className="flex gap-2">
                  <span className={`h-fit shrink-0 rounded px-1.5 py-0.5 text-[11px] font-semibold ${sev[d.severity] ?? sev.low}`}>{t("sev_" + d.severity)}</span>
                  <span>{d.issue}</span>
                </li>
              ))}
            </ul>
          ) : <div className="text-sm text-slate-500">{t("none_found")}</div>}
        </div>
      </div>
      <div className="rounded-lg bg-slate-50 p-3 text-sm">
        <div className="mb-1"><b>{t("fv_suggestion")}:</b> {o.field_verification_reason}</div>
        <div><b>{t("suggested_next")}:</b> {o.suggested_next_step}</div>
      </div>
      {!!o.extracted_documents?.length && (
        <div>
          <h4 className="label">{t("extracted_info")}</h4>
          <div className="grid gap-3 md:grid-cols-2">
            {o.extracted_documents.map((d: any, i: number) => (
              <div key={i} className="rounded-lg border border-slate-200 p-3 text-xs">
                <div className="mb-1 font-semibold text-slate-700">{t("doc_" + d.doc_type)}</div>
                {Object.entries(d.fields ?? {}).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3 border-t border-slate-100 py-1"><span className="text-slate-500">{k}</span><span className="text-right font-medium">{String(v)}</span></div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function DocumentsTab({ app, setApp, reload }: PanelProps) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const { busy, run } = useBusy();
  const [sel, setSel] = useState<number | null>(app.documents[0]?.id ?? null);
  const [fvNeeded, setFvNeeded] = useState(false);
  const [remarks, setRemarks] = useState("");
  const [upType, setUpType] = useState("AADHAAR");
  const [file, setFile] = useState<File | null>(null);
  const can = (a: string) => app.available_actions.includes(a);
  const doc = app.documents.find((d) => d.id === sel);
  const have = new Set(app.documents.map((d) => d.doc_type));
  const remarksOk = remarks.trim().length >= 5;

  const analyze = () => run("ai", async () => {
    await api<AILog>(`/applications/${app.id}/ai/analyze`, { body: { lang } });
    reload();
  });
  const decide = (kind: "forward" | "return") => run(kind, async () => {
    const body = kind === "forward" ? { field_verification_required: fvNeeded, remarks } : { remarks };
    setApp(await api<Detail>(`/applications/${app.id}/${kind}`, { body }));
    toast.ok(t("action_done"));
  });
  const upload = (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    run("upload", async () => {
      const form = new FormData();
      form.append("doc_type", upType);
      form.append("file", file);
      setApp(await api<Detail>(`/applications/${app.id}/documents`, { form }));
      setFile(null);
      toast.ok(t("action_done"));
    });
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-5">
        <div className="space-y-5 lg:col-span-2">
          <Section title={t("required_checklist")}>
            <ul className="space-y-2 text-sm">
              {app.required_documents.map((k) => (
                <li key={k} className="flex items-center justify-between">
                  <span>{t("doc_" + k)}</span>
                  {have.has(k) ? <span className="flex items-center gap-1 text-emerald-600"><CheckCircle2 size={15} /> {t("present")}</span>
                    : <span className="flex items-center gap-1 text-red-600"><XCircle size={15} /> {t("missing")}</span>}
                </li>
              ))}
            </ul>
          </Section>
          <Section title={t("documents")}>
            {app.documents.length ? (
              <ul className="space-y-1.5">
                {app.documents.map((d) => (
                  <li key={d.id}>
                    <button onClick={() => setSel(d.id)} className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition ${sel === d.id ? "border-brand-500 bg-brand-50" : "border-slate-200 hover:bg-slate-50"}`}>
                      <FileText size={16} className="shrink-0 text-slate-400" />
                      <span className="min-w-0 flex-1"><div className="font-medium">{t("doc_" + d.doc_type)}</div><div className="truncate text-xs text-slate-500">{d.filename}</div></span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : <EmptyState title={t("no_docs")} />}
            {can("upload_document") && (
              <form onSubmit={upload} className="mt-4 space-y-2 border-t border-slate-100 pt-4">
                <div className="label">{t("upload_doc")}</div>
                <select className="input" value={upType} onChange={(e) => setUpType(e.target.value)}>{DOC_TYPES.map((k) => <option key={k} value={k}>{t("doc_" + k)}</option>)}</select>
                <input className="block w-full text-xs file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2" type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                <button className="btn-secondary w-full" disabled={!file || busy === "upload"}><Spin on={busy === "upload"}><Upload size={16} /> {t("upload")}</Spin></button>
              </form>
            )}
          </Section>
        </div>

        <div className="lg:col-span-3">
          <Section title={doc ? t("doc_" + doc.doc_type) : t("doc_content")}
            right={doc && <button className="btn-secondary !px-3 !py-1.5 text-xs" onClick={() => downloadDocument(doc.id, doc.filename).catch((e) => toast.err(e.message))}><Download size={14} /> {t("download")}</button>}>
            {doc ? (
              <>
                <div className="mb-2 text-xs text-slate-500">{t("doc_content")} · {doc.filename}</div>
                <pre className="min-h-48 whitespace-pre-wrap rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 font-mono text-sm leading-7">{doc.content_text || t("binary_preview")}</pre>
              </>
            ) : <EmptyState title={t("select_doc")} />}
          </Section>
        </div>
      </div>

      <Section title={t("ai_assist")} icon={<Sparkles size={18} className="text-brand-600" />}
        right={can("ai_analyze") && <button className="btn-primary !py-1.5" disabled={busy === "ai"} onClick={analyze}><Spin on={busy === "ai"}>{busy === "ai" ? t("analyzing") : app.analysis ? t("rerun_analysis") : t("run_analysis")}</Spin></button>}>
        <p className="mb-4 text-xs text-slate-500">{t("ai_assist_hint")}</p>
        {app.analysis ? <AnalysisView log={app.analysis} /> : <EmptyState title={t("no_analysis")} />}
      </Section>

      {can("forward") ? (
        <Section title={t("vro_decision")}>
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              {[[true, t("need_field")], [false, t("no_field")]].map(([v, label]) => (
                <label key={String(v)} className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm ${fvNeeded === v ? "border-brand-500 bg-brand-50" : "border-slate-200"}`}>
                  <input type="radio" className="mt-1" checked={fvNeeded === v} onChange={() => setFvNeeded(v as boolean)} /> {label as string}
                </label>
              ))}
            </div>
            <p className="text-xs text-slate-500">{t("need_field_hint")}</p>
            <div>
              <label className="label">{t("remarks")}</label>
              <textarea className="input min-h-24" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
              {!remarksOk && <div className="mt-1 text-xs text-slate-400">{t("remarks_required")}</div>}
            </div>
            <div className="flex flex-wrap gap-3">
              <button className="btn-primary" disabled={!remarksOk || !!busy} onClick={() => decide("forward")}><Spin on={busy === "forward"}><Send size={16} /> {t("forward")}</Spin></button>
              <button className="btn-secondary text-orange-700" disabled={!remarksOk || !!busy} onClick={() => decide("return")}><Spin on={busy === "return"}>{t("return_correction")}</Spin></button>
            </div>
          </div>
        </Section>
      ) : null}
    </div>
  );
}

// =================================================================== Stage 2: Field verification

const OBS_KEYS = ["visit_date", "persons_met", "residence_type", "livelihood", "assets", "neighbour_statement", "notes"] as const;

export function ReportCards({ app }: { app: Detail }) {
  const { t, lang } = useI18n();
  return (
    <div className="space-y-4">
      {app.reports.map((r) => (
        <div key={r.id} className="rounded-lg border border-slate-200 p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
            <span>{t("by")} <b className="text-slate-700">{r.submitted_by}</b> · {fmtDate(r.submitted_at, lang, true)}</span>
            {r.ai_mode && <span className={`rounded px-2 py-0.5 font-medium ${r.ai_mode === "demo" ? "bg-amber-50 text-amber-800" : "bg-brand-50 text-brand-700"}`}>{r.ai_mode === "demo" ? t("drafted_by_ai_demo") : t("drafted_by_ai_live")}</span>}
          </div>
          <p className="whitespace-pre-wrap text-sm leading-7">{r.report_text}</p>
          <div className="mt-3 grid gap-2 border-t border-slate-100 pt-3 text-xs sm:grid-cols-2">
            {OBS_KEYS.filter((k) => r.observations?.[k]).map((k) => (
              <div key={k}><span className="text-slate-500">{t(k)}: </span>{r.observations[k]}</div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function FieldTab({ app, setApp }: PanelProps) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const { busy, run } = useBusy();
  const [obs, setObs] = useState<Record<string, string>>(Object.fromEntries(OBS_KEYS.map((k) => [k, k === "visit_date" ? new Date().toISOString().slice(0, 10) : ""])));
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<AILog | null>(null);
  const can = (a: string) => app.available_actions.includes(a);

  const generate = () => run("gen", async () => {
    const log = await api<AILog>(`/applications/${app.id}/ai/field-report?lang=${lang}`, { body: obs });
    setDraft(log);
    setText(log.output.report_text);
  });
  const submit = () => run("submit", async () => {
    setApp(await api<Detail>(`/applications/${app.id}/field-report`, { body: { observations: obs, report_text: text, ai_mode: draft?.mode ?? null } }));
    toast.ok(t("action_done"));
  });

  return (
    <div className="space-y-5">
      {can("submit_field_report") && (
        <Section title={t("field_obs")}>
          <div className="grid gap-4 md:grid-cols-2">
            {OBS_KEYS.map((k) => (
              <div key={k} className={k === "notes" || k === "neighbour_statement" ? "md:col-span-2" : ""}>
                <label className="label">{t(k)}</label>
                {k === "visit_date" ? <input type="date" className="input" value={obs[k]} onChange={(e) => setObs({ ...obs, [k]: e.target.value })} />
                  : k === "notes" || k === "neighbour_statement" ? <textarea className="input min-h-20" value={obs[k]} onChange={(e) => setObs({ ...obs, [k]: e.target.value })} />
                  : <input className="input" value={obs[k]} onChange={(e) => setObs({ ...obs, [k]: e.target.value })} />}
              </div>
            ))}
          </div>
          <div className="mt-5 space-y-3 border-t border-slate-100 pt-5">
            <button className="btn-primary" disabled={busy === "gen"} onClick={generate}><Spin on={busy === "gen"}><Sparkles size={16} /> {busy === "gen" ? t("generating") : t("gen_report")}</Spin></button>
            {draft && <AIBanner mode={draft.mode} model={draft.model} by={draft.requested_by} />}
            <div>
              <label className="label">{t("report_text")}</label>
              <textarea className="input min-h-44 leading-7" placeholder={t("report_ph")} value={text} onChange={(e) => setText(e.target.value)} />
            </div>
            <button className="btn-success" disabled={text.trim().length < 10 || !!busy} onClick={submit}><Spin on={busy === "submit"}><Send size={16} /> {t("submit_report")}</Spin></button>
          </div>
        </Section>
      )}
      <Section title={t("submitted_reports")}>
        {app.reports.length ? <ReportCards app={app} /> : <EmptyState title={t("no_field_report")} hint={t("no_field_report_hint")} />}
      </Section>
      {!can("submit_field_report") && !app.reports.length && <ViewOnly />}
    </div>
  );
}

// =================================================================== Stage 3: Final review

export function FinalTab({ app, setApp, reload }: PanelProps) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const { busy, run } = useBusy();
  const [remarks, setRemarks] = useState("");
  const can = (a: string) => app.available_actions.includes(a);
  const vro = app.history.filter((h) => h.role === "VRO" && h.remarks && !h.action.startsWith("SCRUTINY"));
  const s = app.summary?.output;
  const ok = remarks.trim().length >= 5;

  const summarize = () => run("sum", async () => {
    await api<AILog>(`/applications/${app.id}/ai/summary`, { body: { lang } });
    reload();
  });
  const decide = (decision: "APPROVE" | "REJECT" | "RETURN") => run(decision, async () => {
    if (!window.confirm(t("confirm_decision"))) return;
    setApp(await api<Detail>(`/applications/${app.id}/decision`, { body: { decision, remarks } }));
    toast.ok(t("action_done"));
  });

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-2">
        <Section title={t("vro_obs")}>
          {vro.length ? (
            <ul className="space-y-3 text-sm">
              {vro.map((h) => <li key={h.id} className="rounded-lg bg-slate-50 p-3"><div className="mb-1 text-xs text-slate-500">{h.user_name} · {fmtDate(h.created_at, lang, true)}</div>{h.remarks}</li>)}
            </ul>
          ) : <EmptyState title={t("no_vro_obs")} />}
        </Section>
        <Section title={t("submitted_reports")}>
          {app.reports.length ? <ReportCards app={app} /> : <EmptyState title={t("no_field_report")} hint={t("no_field_report_hint")} />}
        </Section>
      </div>

      <Section title={t("case_summary")} icon={<Sparkles size={18} className="text-brand-600" />}
        right={can("ai_summary") && <button className="btn-primary !py-1.5" disabled={busy === "sum"} onClick={summarize}><Spin on={busy === "sum"}>{busy === "sum" ? t("generating") : t("gen_summary")}</Spin></button>}>
        {app.summary && s ? (
          <div className="space-y-4">
            <AIBanner mode={app.summary.mode} model={app.summary.model} by={app.summary.requested_by} at={fmtDate(app.summary.created_at, lang, true)} />
            <p className="text-sm leading-7">{s.summary}</p>
            {!!s.key_points?.length && <div><h4 className="label">{t("key_points")}</h4><List items={s.key_points} tone="plain" /></div>}
            {!!s.concerns?.length && <div><h4 className="label">{t("concerns")}</h4><List items={s.concerns} tone="warn" /></div>}
          </div>
        ) : <EmptyState title={t("no_summary")} />}
      </Section>

      {can("decide") ? (
        <Section title={t("final_decision")} icon={<Gavel size={18} />}>
          <p className="mb-3 text-xs text-slate-500">{t("final_decision_hint")}</p>
          <label className="label">{t("remarks")}</label>
          <textarea className="input min-h-24" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
          {!ok && <div className="mt-1 text-xs text-slate-400">{t("remarks_required")}</div>}
          <div className="mt-4 flex flex-wrap gap-3">
            <button className="btn-success" disabled={!!busy} onClick={() => decide("APPROVE")}><Spin on={busy === "APPROVE"}><CheckCircle2 size={16} /> {t("approve")}</Spin></button>
            <button className="btn-danger" disabled={!ok || !!busy} onClick={() => decide("REJECT")}><Spin on={busy === "REJECT"}><XCircle size={16} /> {t("reject")}</Spin></button>
            <button className="btn-secondary" disabled={!ok || !!busy} onClick={() => decide("RETURN")}><Spin on={busy === "RETURN"}>{t("return_vro")}</Spin></button>
          </div>
        </Section>
      ) : app.status !== "AWAITING_FINAL_REVIEW" && !["APPROVED", "REJECTED"].includes(app.status) ? <ViewOnly /> : null}
    </div>
  );
}
