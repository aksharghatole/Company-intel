import time
import json
from technographics import scan_technographics_free, TECH_TAXONOMY
import pandas as pd
from safe_web import normalize_domain
from concurrent.futures import ThreadPoolExecutor, as_completed
from intel import (
    get_tech_stack,
    get_hiring_signals,
    get_firmographics,
)


def scan_one(row):
    """Scan a single company row. Expects dict with 'company' and 'domain'."""
    raw_company = row.get("company", "")
    raw_domain = row.get("domain", "")
    company = "" if pd.isna(raw_company) else str(raw_company).strip()
    domain = "" if pd.isna(raw_domain) else str(raw_domain).strip()
    if not company or not domain:
        return {
            "company": company,
            "domain": domain,
            "error": "missing company or domain",
        }

    try:
        domain = normalize_domain(domain)
        tech = get_tech_stack(domain)
        hiring = get_hiring_signals(company, domain)
        firm = get_firmographics(company, domain)
    except Exception as e:
        return {"company": company, "domain": domain, "error": str(e)}

    # The ATS scan is independent of the website scan; keep partial results.
    ats_error = ""
    try:
        signals = scan_technographics_free(company, domain)
    except Exception as exc:
        signals = {}
        ats_error = str(exc)
    findings = signals.get("from_jobs", {})
    evidence = [
        {"category": category, "vendor": vendor,
         "job_title": item.get("job_title", ""), "url": item.get("url", "")}
        for category, vendors in sorted(findings.items())
        for vendor, items in sorted(vendors.items())
        for item in items
    ]
    # Deduplicate repeated job links while preserving evidence order.
    evidence = list({(e["category"], e["vendor"], e["job_title"], e["url"]): e
                     for e in evidence}.values())

    return {
        "company": company,
        "domain": domain,
        "tech_stack": ", ".join(tech.get("detected", [])),
        "open_roles": hiring.get("open_roles_found", 0),
        "plm_cad_keywords": ", ".join(hiring.get("plm_cad_keywords_in_jobs", [])),
        "careers_page": hiring.get("careers_page") or "",
        "employees": firm.get("employees_mentioned", ""),
        "revenue": firm.get("revenue_mentioned", ""),
        "linkedin": firm.get("linkedin_search", ""),
        "ats_detected": signals.get("ats_detected") or "",
        "ats_jobs_scanned": signals.get("jobs_scanned"),
        "ats_status": ("error" if ats_error else
                       "board found (unverified identity)" if signals.get("ats_detected")
                       else "no public board found"),
        **{f"{category.lower()}_vendors": ", ".join(sorted(findings.get(category, {})))
           for category in TECH_TAXONOMY},
        "evidence_count": len(evidence),
        "job_evidence_json": json.dumps(evidence, ensure_ascii=False),
        "error": "; ".join(filter(None, [tech.get("error", ""), ats_error])),
    }


def scan_dataframe(df, max_workers=5, delay=0.3):
    """
    Scan a DataFrame of companies in parallel.
    df must have columns: company, domain
    Returns a DataFrame with results.
    """
    rows = df.to_dict(orient="records")
    results = [None] * len(rows)
    if not rows:
        return pd.DataFrame(columns=["company", "domain", "error"])

    def scan_with_delay(row):
        try:
            return scan_one(row)
        finally:
            # Pause the worker before it picks up the next company.
            if delay > 0:
                time.sleep(delay)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(scan_with_delay, row): i for i, row in enumerate(rows)}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as exc:
                results[i] = {"company": rows[i].get("company", ""),
                              "domain": rows[i].get("domain", ""), "error": str(exc)}
    return pd.DataFrame(results)


def _spreadsheet_safe(df):
    """Prevent untrusted input or scraped text becoming spreadsheet formulas."""
    def escape(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value
    return df.apply(lambda col: col.map(escape))


def evidence_dataframe(df):
    rows = []
    for _, row in df.iterrows():
        raw = row.get("job_evidence_json")
        if not isinstance(raw, str):
            continue
        for evidence in json.loads(raw):
            rows.append({"company": row.get("company"), "domain": row.get("domain"), **evidence})
    return pd.DataFrame(rows, columns=["company", "domain", "category", "vendor", "job_title", "url"])


def results_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return _spreadsheet_safe(df).to_csv(index=False).encode("utf-8")


def results_to_excel_bytes(df: pd.DataFrame) -> bytes:
    import io
    buf = io.BytesIO()
    # Keep the full structured evidence on its own sheet, not in a long cell.
    summary = df.drop(columns=["job_evidence_json"], errors="ignore")
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        _spreadsheet_safe(summary).to_excel(writer, index=False, sheet_name="Company Intel")
        _spreadsheet_safe(evidence_dataframe(df)).to_excel(writer, index=False, sheet_name="Job Evidence")
    return buf.getvalue()
