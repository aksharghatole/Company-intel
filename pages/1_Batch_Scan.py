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

    st.success(f"Loaded {len(df)} companies.")
    st.dataframe(df.head(10), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        max_workers = st.slider("Concurrent workers", 1, 10, 5)
    with col2:
        delay = st.slider("Delay between requests (s)", 0.0, 2.0, 0.3, 0.1)

    if st.button("🚀 Start Scan", type="primary"):
        progress = st.progress(0, text="Starting...")
        status = st.empty()

        # scan in one shot (progress bar updates at end — see note below)
        status.info(f"Scanning {len(df)} companies with {max_workers} workers...")
        results = scan_dataframe(df, max_workers=max_workers, delay=delay)

        progress.progress(100, text="Done!")
        status.success(f"Scanned {len(results)} companies.")

        st.subheader("Results")
        st.dataframe(results, use_container_width=True)

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