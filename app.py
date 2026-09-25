import streamlit as st
import json
from intel import run

st.set_page_config(page_title="Company Intel", page_icon="🔎", layout="wide")
st.title("🔎 Company Intelligence Tool")
st.caption("Feed it a company name + website → tech stack, hiring signals, firmographics, and technographic signals (PLM/PDM/CAD/ERP).")

with st.sidebar:
    st.markdown("### Debug")
    st.write(f"Last scan: **{st.session_state.get('last_company', '—')}**")
    if st.button("🔄 Reset"):
        st.session_state.clear()
        st.rerun()

col1, col2 = st.columns(2)
with col1:
    company = st.text_input("Company name", "Siemens")
with col2:
    domain = st.text_input("Website domain", "siemens.com")

if st.button("Run Scan", type="primary"):
    with st.spinner("Scanning... this can take 30–60 seconds"):
        st.session_state["report"] = run(company, domain)
        st.session_state["last_company"] = company
        st.session_state["last_domain"] = domain

report = st.session_state.get("report")

if report:
    st.subheader("🧱 Web Tech Stack")
    ts = report["tech_stack"]
    detected = ts.get("detected") or []
    if detected:
        st.write(", ".join(detected))
    else:
        st.write("None detected")
    if ts.get("http_status"):
        st.caption(f"HTTP {ts['http_status']} · {ts.get('html_length', 0):,} chars · {ts.get('final_url','')}")

    st.subheader("📢 Hiring Signals")
    hs = report["hiring_signals"]
    st.metric("Open roles found", hs["open_roles_found"])
    if hs.get("plm_cad_keywords_in_jobs"):
        st.success(f"PLM/CAD keywords in jobs: {', '.join(hs['plm_cad_keywords_in_jobs'])}")
    if hs.get("sample_roles"):
        for j in hs["sample_roles"]:
            st.markdown(f"- [{j['title']}]({j['url']})")
    elif hs.get("careers_page"):
        st.info(f"[Visit careers page →]({hs['careers_page']})")
    else:
        st.write("No matching jobs found on Remotive.")

    st.subheader("🔬 Technographic Signals")
    tg = report.get("technographics", {})
    st.caption(f"ATS detected: **{tg.get('ats_detected') or 'none'}** · Jobs scanned: **{tg.get('jobs_scanned', 0)}**")
    from_jobs = tg.get("from_jobs", {})
    if from_jobs:
        st.markdown("**From job postings (highest confidence):**")
        for category, vendors in from_jobs.items():
            with st.expander(f"📋 {category} — {len(vendors)} vendor(s)"):
                for vendor, evidence in vendors.items():
                    st.markdown(f"**{vendor}**")
                    for e in evidence[:5]:
                        st.markdown(f"  - [{e['job_title']}]({e['url']})")
    else:
        st.write("No vendor mentions found in public job postings.")

    st.subheader("🏢 Firmographics")
    fg = report["firmographics"]
    st.write(f"Employees mentioned: **{fg.get('employees_mentioned', '—')}**")
    st.write(f"Revenue mentioned: **{fg.get('revenue_mentioned', '—')}**")
    if not fg.get("revenue_mentioned"):
        st.caption(
            f"[Search '{report['company']} revenue' on Google →]"
            f"(https://www.google.com/search?q={report['company'].replace(' ','+')}+annual+revenue)"
        )
    st.markdown(f"[LinkedIn]({fg['linkedin_search']}) · [Crunchbase]({fg['crunchbase_search']}) · [Google employees]({fg['google_employees_search']})")

    st.subheader("⚙️ PLM / PDM / CAD — Manual Search Links")
    st.caption("Backup links if the technographic scan above didn't find anything.")
    for vendor, url in report["plm_pdm_cad_search_links"].items():
        st.markdown(f"- [{vendor}]({url})")

    st.download_button(
        "⬇️ Download JSON report",
        json.dumps(report, indent=2, default=str),
        file_name=f"{report['company'].replace(' ', '_')}_report.json",
    )