import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from intel import (
    get_tech_stack,
    get_hiring_signals,
    get_firmographics,
)


def scan_one(row):
    """Scan a single company row. Expects dict with 'company' and 'domain'."""
    company = str(row.get("company", "")).strip()
    domain = str(row.get("domain", "")).strip()
    if not company or not domain:
        return {
            "company": company,
            "domain": domain,
            "error": "missing company or domain",
        }

    try:
        tech = get_tech_stack(domain)
        hiring = get_hiring_signals(company, domain)
        firm = get_firmographics(company, domain)
    except Exception as e:
        return {"company": company, "domain": domain, "error": str(e)}

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
        "error": "",
    }


def scan_dataframe(df, max_workers=5, delay=0.3):
    """
    Scan a DataFrame of companies in parallel.
    df must have columns: company, domain
    Returns a DataFrame with results.
    """
    rows = df.to_dict(orient="records")
    results = []
    total = len(rows)

    progress_placeholder = None  # set by caller if needed

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(scan_one, r): r for r in rows}
        for i, fut in enumerate(as_completed(futures), 1):
            results.append(fut.result())
            # small delay to avoid hammering sites
            time.sleep(delay / max_workers)

    return pd.DataFrame(results)


def results_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def results_to_excel_bytes(df: pd.DataFrame) -> bytes:
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Company Intel")
    return buf.getvalue()