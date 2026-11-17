"""AI assistance: live LLM call (Anthropic Messages API) with a clearly-labelled demo fallback.

AI only ASSISTS officers. It never approves or rejects an application.

Configure with environment variables (or backend/.env):
  ANTHROPIC_API_KEY=...        # enables live mode
  LLM_MODEL=claude-sonnet-5-5  # optional
"""
import json
import os
import re

import httpx

API_URL = "https://api.anthropic.com/v1/messages"
REQUIRED_DOCS = {"AADHAAR": "Aadhaar card", "RATION_CARD": "Ration card", "INCOME_DECLARATION": "Income self-declaration"}


class AIError(Exception):
    """Raised when a live LLM call fails. Surfaced to the user - never hidden behind fake output."""


def api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


def model_name() -> str:
    return os.environ.get("LLM_MODEL", "claude-sonnet-5-5")


def status() -> dict:
    live = bool(api_key())
    return {"mode": "live" if live else "demo", "model": model_name() if live else "none (demo mode)"}


# ---------------------------------------------------------------- live LLM

SYSTEM = (
    "You assist Telangana revenue officers processing Income Certificate applications (demo data only). "
    "You never approve or reject; you only extract, flag and summarise for a human officer. "
    "Reply with ONE valid JSON object matching the requested schema, with no prose or markdown. "
    "Write human-readable text values in {language}."
)

SCHEMAS = {
    "ANALYSIS": {
        "extracted_documents": [{"document_id": 0, "doc_type": "", "fields": {"field name": "value"}}],
        "missing_information": ["string"],
        "discrepancies": [{"field": "string", "issue": "string", "severity": "low|medium|high"}],
        "field_verification_suggested": True,
        "field_verification_reason": "string",
        "suggested_next_step": "string",
    },
    "FIELD_REPORT": {"report_text": "string", "key_findings": ["string"], "concerns": ["string"]},
    "CASE_SUMMARY": {"summary": "string", "key_points": ["string"], "concerns": ["string"]},
}

TASKS = {
    "ANALYSIS": (
        "Extract key fields from each document, list missing required information "
        f"(required documents: {', '.join(REQUIRED_DOCS)}), and flag inconsistencies between the application "
        "and the documents. Say whether a field inspection seems useful (it is conditional, not always required)."
    ),
    "FIELD_REPORT": "Write a concise, neutral field verification report from the officer's observations only. Do not invent facts.",
    "CASE_SUMMARY": "Summarise the full case for the Tahsildar: facts, VRO scrutiny, field report (if any), open concerns. Do not recommend approve/reject.",
}


def _call_llm(kind: str, payload: dict, lang: str) -> dict:
    language = "Telugu" if lang == "te" else "English"
    prompt = (
        f"{TASKS[kind]}\n\nJSON schema to follow:\n{json.dumps(SCHEMAS[kind])}\n\n"
        f"Case data:\n{json.dumps(payload, default=str, ensure_ascii=False)}"
    )
    try:
        r = httpx.post(
            API_URL,
            headers={"x-api-key": api_key(), "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={
                "model": model_name(),
                "max_tokens": 2000,
                "system": SYSTEM.format(language=language),
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
    except httpx.HTTPError as e:
        raise AIError(f"Could not reach the LLM service: {e}")
    if r.status_code != 200:
        raise AIError(f"LLM API returned {r.status_code}: {r.text[:200]}")
    text = "".join(b.get("text", "") for b in r.json().get("content", []))
    start, end = text.find("{"), text.rfind("}")
    try:
        out = json.loads(text[start : end + 1])
    except (ValueError, json.JSONDecodeError):
        raise AIError("The LLM returned a response that was not valid JSON. Please retry.")
    return _validate(kind, out)


# Expected shape of each live response: key -> type. Anything malformed is an error, never silently patched up.
SHAPES = {
    "ANALYSIS": {"extracted_documents": list, "missing_information": list, "discrepancies": list,
                 "field_verification_reason": str, "suggested_next_step": str},
    "FIELD_REPORT": {"report_text": str, "key_findings": list, "concerns": list},
    "CASE_SUMMARY": {"summary": str, "key_points": list, "concerns": list},
}
MUST_BE_NONEMPTY = {"FIELD_REPORT": "report_text", "CASE_SUMMARY": "summary"}


def _validate(kind: str, out) -> dict:
    if not isinstance(out, dict):
        raise AIError("The LLM response was not a JSON object. Please retry.")
    for key, typ in SHAPES[kind].items():
        if key not in out:  # optional-looking fields may be omitted; fill with an empty value of the right type
            out[key] = typ()
        if not isinstance(out[key], typ):
            raise AIError(f"The LLM response had an invalid '{key}' field. Please retry.")
    must = MUST_BE_NONEMPTY.get(kind)
    if must and not out[must].strip():
        raise AIError("The LLM returned an empty response. Please retry.")
    if kind == "ANALYSIS":
        out["discrepancies"] = [
            {"field": str(d.get("field", "")), "issue": str(d.get("issue", "")),
             "severity": d.get("severity") if d.get("severity") in ("low", "medium", "high") else "medium"}
            for d in out["discrepancies"] if isinstance(d, dict)
        ]
        out["extracted_documents"] = [d for d in out["extracted_documents"] if isinstance(d, dict)]
        out["missing_information"] = [str(x) for x in out["missing_information"]]
    return out


# ---------------------------------------------------------------- demo mode

# DEMO MODE:
# Sample AI responses are used when an external LLM API key
# is not configured. These responses are not actual AI predictions.
# They are produced by simple text rules / templates over the demo data.

T = {
    "en": {
        "missing_doc": "Required document not uploaded: {name}",
        "name_mismatch": "Name on {doc} ('{doc_val}') differs from application name ('{app_val}')",
        "income_mismatch": "Income in {doc} (Rs. {doc_val:,}) differs from declared income (Rs. {app_val:,})",
        "village_mismatch": "Village on {doc} ('{doc_val}') differs from application village ('{app_val}')",
        "next_ok": "No issues found by the sample rules. Officer may proceed after reviewing documents.",
        "next_issues": "Review the flagged items; consider returning for correction or verifying in the field.",
        "fv_yes": "Discrepancies or missing details were flagged; a field inspection may help resolve them.",
        "fv_no": "No discrepancies flagged by the sample rules; field inspection appears optional.",
        "report_head": "Field verification report (sample draft generated from the officer's entries).",
        "visit": "Visit date: {v}. Persons met: {p}.",
        "house": "Residence: {r}.",
        "livelihood": "Livelihood observed: {l}.",
        "assets": "Assets observed: {a}.",
        "neigh": "Neighbours' statement: {n}.",
        "notes": "Additional notes: {n}.",
        "none": "not recorded",
        "sum_head": "{name} (age {age}) of {village}, {mandal}, {district} applied for an Income Certificate for '{purpose}', declaring annual income of Rs. {income:,}.",
        "sum_docs": "{n} document(s) on file: {types}.",
        "sum_vro": "VRO scrutiny remarks: {r}",
        "sum_field": "A field report was submitted: see the Field Report section.",
        "sum_nofield": "No field verification was performed for this application.",
        "sum_no_vro": "No VRO remarks recorded.",
        "concern_none": "No open concerns identified by the sample rules.",
    },
    "te": {
        "missing_doc": "అవసరమైన పత్రం అప్‌లోడ్ కాలేదు: {name}",
        "name_mismatch": "{doc} లోని పేరు ('{doc_val}') దరఖాస్తులోని పేరు ('{app_val}')తో సరిపోలడం లేదు",
        "income_mismatch": "{doc} లోని ఆదాయం (రూ. {doc_val:,}) ప్రకటించిన ఆదాయం (రూ. {app_val:,})తో సరిపోలడం లేదు",
        "village_mismatch": "{doc} లోని గ్రామం ('{doc_val}') దరఖాస్తులోని గ్రామం ('{app_val}')తో సరిపోలడం లేదు",
        "next_ok": "నమూనా నియమాల ప్రకారం సమస్యలు కనిపించలేదు. పత్రాలను సమీక్షించి అధికారి ముందుకు సాగవచ్చు.",
        "next_issues": "గుర్తించిన అంశాలను సమీక్షించండి; దిద్దుబాటుకు తిరిగి పంపడం లేదా క్షేత్ర స్థాయిలో పరిశీలించడం పరిగణించండి.",
        "fv_yes": "తేడాలు/లోపాలు గుర్తించబడ్డాయి; క్షేత్ర తనిఖీ సహాయపడవచ్చు.",
        "fv_no": "నమూనా నియమాల ప్రకారం తేడాలు లేవు; క్షేత్ర తనిఖీ ఐచ్ఛికం.",
        "report_head": "క్షేత్ర పరిశీలన నివేదిక (అధికారి నమోదుల ఆధారంగా నమూనా ముసాయిదా).",
        "visit": "సందర్శన తేదీ: {v}. కలిసిన వ్యక్తులు: {p}.",
        "house": "నివాసం: {r}.",
        "livelihood": "గమనించిన జీవనోపాధి: {l}.",
        "assets": "గమనించిన ఆస్తులు: {a}.",
        "neigh": "పొరుగువారి ప్రకటన: {n}.",
        "notes": "అదనపు గమనికలు: {n}.",
        "none": "నమోదు కాలేదు",
        "sum_head": "{village}, {mandal}, {district}కు చెందిన {name} (వయస్సు {age}) '{purpose}' కోసం ఆదాయ ధృవీకరణ పత్రానికి దరఖాస్తు చేశారు; వార్షిక ఆదాయం రూ. {income:,} గా ప్రకటించారు.",
        "sum_docs": "{n} పత్రం(లు) ఉన్నాయి: {types}.",
        "sum_vro": "VRO పరిశీలన వ్యాఖ్యలు: {r}",
        "sum_field": "క్షేత్ర నివేదిక సమర్పించబడింది: క్షేత్ర నివేదిక విభాగం చూడండి.",
        "sum_nofield": "ఈ దరఖాస్తుకు క్షేత్ర పరిశీలన జరగలేదు.",
        "sum_no_vro": "VRO వ్యాఖ్యలు నమోదు కాలేదు.",
        "concern_none": "నమూనా నియమాల ప్రకారం ఎలాంటి సమస్యలు లేవు.",
    },
}


def _parse_fields(text: str) -> dict:
    fields = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            if k.strip() and v.strip():
                fields[k.strip()] = v.strip()
    return fields


def _num(s: str) -> int | None:
    m = re.search(r"[\d,]{3,}", s)
    return int(m.group().replace(",", "")) if m else None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _demo_analysis(p: dict, lang: str) -> dict:
    t, app = T[lang], p["application"]
    extracted, discrepancies = [], []
    have = {d["doc_type"] for d in p["documents"]}
    missing = [t["missing_doc"].format(name=n) for k, n in REQUIRED_DOCS.items() if k not in have]
    for d in p["documents"]:
        f = _parse_fields(d["content_text"])
        extracted.append({"document_id": d["id"], "doc_type": d["doc_type"], "fields": f})
        label = d["doc_type"].replace("_", " ").title()
        if f.get("Name") and _norm(f["Name"]) != _norm(app["applicant_name"]):
            discrepancies.append({"field": "name", "severity": "high",
                                  "issue": t["name_mismatch"].format(doc=label, doc_val=f["Name"], app_val=app["applicant_name"])})
        if f.get("Village") and _norm(f["Village"]) != _norm(app["village"]):
            discrepancies.append({"field": "village", "severity": "medium",
                                  "issue": t["village_mismatch"].format(doc=label, doc_val=f["Village"], app_val=app["village"])})
        inc = next((_num(v) for k, v in f.items() if "income" in k.lower() or "salary" in k.lower()), None)
        if inc and abs(inc - app["declared_income"]) > 0.1 * app["declared_income"]:
            discrepancies.append({"field": "income", "severity": "high",
                                  "issue": t["income_mismatch"].format(doc=label, doc_val=inc, app_val=int(app["declared_income"]))})
    flagged = bool(missing or discrepancies)
    return {
        "extracted_documents": extracted,
        "missing_information": missing,
        "discrepancies": discrepancies,
        "field_verification_suggested": flagged,
        "field_verification_reason": t["fv_yes"] if flagged else t["fv_no"],
        "suggested_next_step": t["next_issues"] if flagged else t["next_ok"],
    }


def _demo_field_report(p: dict, lang: str) -> dict:
    t, o = T[lang], p["observations"]
    g = lambda k: (o.get(k) or "").strip() or t["none"]
    lines = [t["report_head"], t["visit"].format(v=g("visit_date"), p=g("persons_met")),
             t["house"].format(r=g("residence_type")), t["livelihood"].format(l=g("livelihood")),
             t["assets"].format(a=g("assets")), t["neigh"].format(n=g("neighbour_statement"))]
    if (o.get("notes") or "").strip():
        lines.append(t["notes"].format(n=o["notes"].strip()))
    findings = [x for x in (g("residence_type"), g("livelihood"), g("assets")) if x != t["none"]]
    return {"report_text": "\n".join(lines), "key_findings": findings, "concerns": []}


def _demo_summary(p: dict, lang: str) -> dict:
    t, a = T[lang], p["application"]
    types = ", ".join(d["doc_type"] for d in p["documents"]) or "-"
    points = [t["sum_head"].format(name=a["applicant_name"], age=a["age"], village=a["village"], mandal=a["mandal"],
                                   district=a["district"], purpose=a["purpose"], income=int(a["declared_income"])),
              t["sum_docs"].format(n=len(p["documents"]), types=types),
              t["sum_vro"].format(r=p["vro_remarks"]) if p["vro_remarks"] else t["sum_no_vro"],
              t["sum_field"] if p["field_reports"] else t["sum_nofield"]]
    concerns = [d["issue"] for d in (p.get("analysis") or {}).get("discrepancies", [])] + \
               (p.get("analysis") or {}).get("missing_information", [])
    return {"summary": " ".join(points[:2]), "key_points": points[2:], "concerns": concerns or [t["concern_none"]]}


# ---------------------------------------------------------------- public API

_DEMO = {"ANALYSIS": _demo_analysis, "FIELD_REPORT": _demo_field_report, "CASE_SUMMARY": _demo_summary}


def run(kind: str, payload: dict, lang: str = "te") -> dict:
    """Return {mode, model, output}. mode is 'live' only when a real LLM produced the output."""
    lang = lang if lang in T else "te"
    if api_key():
        return {"mode": "live", "model": model_name(), "output": _call_llm(kind, payload, lang)}
    return {"mode": "demo", "model": "none (demo mode)", "output": _DEMO[kind](payload, lang)}
