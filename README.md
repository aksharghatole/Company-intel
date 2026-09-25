# 🔎 Company Intel

A free, deployed technographic scanner. Feed it a company name + website, and it returns:

- 🧱 **Web/IT tech stack** — detected from `<script>` tags, `<link>` stylesheets, and HTTP headers
- 📢 **Hiring signals** — open roles pulled from the company's public ATS
- 🔬 **Technographic signals** — PLM, PDM, CAD, ERP, EDMS, CRM, and MES vendors mentioned in job postings
- 🏢 **Firmographics** — employee counts, revenue hints, and research links

**Live demo:** [company-intel.streamlit.app](https://company-intel.streamlit.app)

---

## 🎯 What It Does

The tool combines four detection layers:

| Layer | Source | Reliability |
|---|---|---|
| **Web tech stack** | DOM analysis + HTTP headers | High — no false positives |
| **ATS detection** | Greenhouse / Lever / Ashby public APIs | High — when public ATS exists |
| **Technographic vendors** | Job posting keyword matching | Medium–High — real evidence |
| **Firmographics** | HTML text extraction + manual links | Low — often needs manual research |

Every result includes **evidence links** (the specific job posting that mentioned a vendor) so you can verify manually.

---

## 🏆 Example: Formlabs

Input: `Formlabs` / `formlabs.com`

**Output:**
```
🧱 Web Tech Stack
Cloudflare, Next.js

📢 Hiring Signals
Open roles found: 0 → careers page linked

🔬 Technographic Signals
ATS detected: greenhouse:formlabs · Jobs scanned: 212

From job postings:
  📋 CAD — 3 vendors
  📋 PDM — 1 vendor
  📋 ERP — 1 vendor
  📋 CRM — 1 vendor

🏢 Firmographics
Employees mentioned: 750 employees
```

This is a **hardware 3D-printing company** — so finding CAD, PDM, ERP, and CRM tools in their job posts is exactly correct.

---

## 🛠️ How It Works

### 1. Web Tech Stack — DOM-based detection

Instead of naive text matching (`"shopify" in html`), the tool parses:

- `<script src="...">` — catches CDNs, analytics, payment SDKs
- `<link href="...">` — catches framework fingerprints (`/_next/`, `/_nuxt/`)
- **HTTP response headers** — catches CDNs (Cloudflare, CloudFront), servers (Nginx, Apache)

This avoids false positives from customer logos, testimonials, and mentions in page copy.

### 2. ATS Discovery — public API scraping

The tool tries to guess the company's ATS slug from its name/domain, then queries the public APIs:

- **Greenhouse:** `boards-api.greenhouse.io/v1/boards/{slug}/jobs`
- **Lever:** `api.lever.co/v0/postings/{slug}?mode=json`
- **Ashby:** `api.ashbyhq.com/posting-api/job-board/{slug}`

### 3. Technographic Scanner — job-posting keyword matching

Every job description is scanned against a curated taxonomy of 50+ enterprise vendors across 7 categories:

- **PLM:** Teamcenter, Windchill, ENOVIA, Aras, SAP PLM, Oracle Agile
- **PDM:** SolidWorks PDM, Autodesk Vault, Windchill PDMLink
- **CAD:** SolidWorks, CATIA, NX, Creo, AutoCAD, Inventor, Fusion 360
- **ERP:** SAP S/4HANA, NetSuite, Workday, Dynamics 365, Epicor
- **EDMS:** Documentum, OpenText, SharePoint, Alfresco, M-Files
- **CRM:** Salesforce, HubSpot, Dynamics CRM, Zoho
- **MES:** Opcenter, FactoryTalk, AVEVA MES, Apriso

Matches use **word-boundary regex** to avoid false positives (`cad` won't match `scad`).

### 4. Firmographics — regex extraction + manual links

The tool crawls `/about`, `/investor-relations`, and similar pages looking for:

- Employee counts: `"318K employees"`, `"750 staff"`, `"5,000+ people"`
- Revenue: `"$125 billion in revenue"`, `"€72M turnover"`

When extraction fails (most common case), it generates **direct search links** to LinkedIn, Crunchbase, and Google — one click for manual research.

---

## ⚠️ Honest Limitations

This tool is **free** and runs on **Streamlit Cloud**. That means it's subject to limitations that commercial tools (ZoomInfo, 6sense, HG Insights) pay to solve:

| Limitation | Why | Workaround |
|---|---|---|
| **Enterprise PLM/PDM/CAD rarely appears** | Large manufacturers (Siemens, Boeing) use private career portals, not public ATS | Manual Google search links provided |
| **Tesla returns 403** | Bot protection (Cloudflare/Datadome) blocks cloud IPs | Inherent — no free fix |
| **Revenue rarely detected** | Company About pages use JS-rendered numbers | Google search link provided |
| **No Google case-study scraping** | Requires paid SERP API | Manual search links for 7 PLM vendors |

**Rule of thumb:** if a company uses Greenhouse, Lever, or Ashby — the tool works well. If they use Workday, SuccessFactors, or Taleo — you'll get the tech stack but not the technographics.

---

## 🚀 Setup

### Run locally

```bash
git clone https://github.com/aksharghatole/Company-intel
cd Company-intel
pip install -r requirements.txt
streamlit run app.py
```

### Deploy to Streamlit Cloud

1. Fork or push this repo to your GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Create new app → select repo → main branch → `app.py`
4. Deploy (takes ~2 minutes)

### Batch mode

Navigate to the **Batch Scan** page in the sidebar:

1. Download the CSV template
2. Fill it with `company, domain` columns
3. Upload the CSV
4. Click **Start Scan**
5. Download results as CSV or Excel

Keep batches under 50 rows to avoid Streamlit Cloud timeouts.

---

## 🧱 Tech Stack (of the tool itself)

| Component | Choice |
|---|---|
| **Language** | Python 3.11 |
| **UI** | Streamlit |
| **HTTP** | `requests` |
| **HTML parsing** | `BeautifulSoup` |
| **Data** | `pandas`, `openpyxl` |
| **Hosting** | Streamlit Community Cloud (free) |
| **Data sources** | Greenhouse API, Lever API, Ashby API, Remotive API |

**Total monthly cost: $0.**

---

## 📁 Project Structure

```
Company-intel/
├── app.py                          # Main single-company UI
├── intel.py                        # Core detection logic
├── technographics.py               # ATS + job scanning
├── batch.py                        # Batch CSV scanning
├── requirements.txt                # Dependencies
├── README.md                       # This file
└── pages/
    └── 1_Batch_Scan.py             # Batch UI
```

---

## 🧪 Sample Companies

| Company | Domain | What you'll see |
|---|---|---|
| **Stripe** | stripe.com | Next.js, Nginx, 691 jobs scanned |
| **Figma** | figma.com | CloudFront, Netlify, Next.js, 162 jobs |
| **Notion** | notion.com | Cloudflare, Next.js, React, 129 jobs |
| **Vercel** | vercel.com | Next.js, Vercel, 89 jobs |
| **Formlabs** | formlabs.com | **CAD, PDM, ERP, CRM hits** — the demo case 🏆 |
| **Siemens** | siemens.com | Employees: 318K (private ATS) |
| **Tesla** | tesla.com | HTTP 403 — blocked (expected) |

---

## 🎓 What This Tool Teaches

Building this tool demonstrates:

- **DOM + header analysis** outperforms naive text matching for tech detection
- **Public APIs** (Greenhouse, Lever, Ashby) are a goldmine for technographic data
- **Word-boundary regex** is essential for avoiding false positives
- **Cache-busting query params** bypass shared edge caches
- **Honest limitations** are better than fabricated results
- **Free scraping has a ceiling** — commercial tools exist because they aggregate 20+ sources

---

## 📜 License

MIT — do whatever you want with it.

---

## 🙏 Acknowledgements

- [Streamlit](https://streamlit.io) for free hosting
- [Greenhouse](https://developers.greenhouse.io), [Lever](https://github.com/lever/postings-api), [Ashby](https://developers.ashbyhq.com) for public ATS APIs
- [Wappalyzer](https://www.wappalyzer.com) for the DOM-matching inspiration

---

**Built as a portfolio project. Contributions welcome.**