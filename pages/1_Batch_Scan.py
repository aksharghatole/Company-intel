import streamlit as st
import pandas as pd
from batch import scan_dataframe, results_to_csv_bytes, results_to_excel_bytes

st.set_page_config(page_title="Batch Scan", page_icon="📊", layout="wide")

st.title("📊 Batch Company Scan")
st.caption("Upload a CSV with columns `company` and `domain`, scan them all at once, download the results.")

# --- Template download ---
template = pd.DataFrame({
    "company": ["Siemens", "Shopify", "Linear"],
    "domain": ["siemens.com", "shopify.com", "linear.app"],
})
st.download_button(
    "⬇️ Download CSV template",
    template.to_csv(index=False).encode("utf-8"),
    file_name="company_template.csv",
    mime="text/csv",
)

# --- Upload ---
uploaded = st.file_uploader("Upload your CSV", type=["csv"])

if uploaded is not None:
    try:
        df = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        st.stop()

    required = {"company", "domain"}
    if not required.issubset(df.columns):
        st.error(f"CSV must have columns: {required}. Found: {list(df.columns)}")
        st.stop()

    if df.empty:
        st.warning("Upload at least one company.")
        st.stop()
    st.success(f"Loaded {len(df)} companies.")
    st.dataframe(df.head(10), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        max_workers = st.slider("Concurrent workers", 1, 10, 5)
    with col2:
        delay = st.slider("Pause between companies per worker (s)", 0.0, 2.0, 0.3, 0.1)

    # Bind results to the uploaded file so download reruns keep the report visible.
    import hashlib
    upload_key = hashlib.sha256(uploaded.getvalue()).hexdigest()
    if st.session_state.get("batch_upload_key") != upload_key:
        st.session_state.pop("batch_results", None)
        st.session_state["batch_upload_key"] = upload_key

    if st.button("🚀 Start Scan", type="primary"):
        progress = st.progress(0, text="Starting...")
        status = st.empty()

        # scan in one shot (progress bar updates at end — see note below)
        status.info(f"Scanning {len(df)} companies with {max_workers} workers...")
        results = scan_dataframe(df, max_workers=max_workers, delay=delay)

        st.session_state["batch_results"] = results
        progress.progress(100, text="Done!")
        status.success(f"Scanned {len(results)} companies.")

    results = st.session_state.get("batch_results")
    if results is not None:
        st.subheader("Results")
        st.caption("ATS boards are inferred from company names/domains; verify job evidence before treating a vendor mention as confirmed software use.")
        st.dataframe(results.drop(columns=["job_evidence_json"], errors="ignore"), use_container_width=True)

        csv_bytes = results_to_csv_bytes(results)
        xlsx_bytes = results_to_excel_bytes(results)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "⬇️ Download CSV",
                csv_bytes,
                file_name="company_intel.csv",
                mime="text/csv",
            )
        with c2:
            st.download_button(
                "⬇️ Download Excel",
                xlsx_bytes,
                file_name="company_intel.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
