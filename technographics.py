import re, requests, time, uuid

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; IntelBot/1.0)"}

TECH_TAXONOMY = {
    "PLM": ["Teamcenter", "Windchill", "ENOVIA", "Aras PLM", "SAP PLM",
            "Oracle Agile PLM", "Centric PLM", "PTC FlexPLM"],
    "PDM": ["SolidWorks PDM", "Windchill PDMLink", "Teamcenter PDM", "Autodesk Vault"],
    "CAD": ["SolidWorks", "CATIA", "Siemens NX", "Creo", "AutoCAD",
            "Inventor", "Fusion 360", "Revit", "Onshape", "Solid Edge"],
    "ERP": ["SAP S/4HANA", "SAP ECC", "Oracle ERP", "NetSuite",
            "Dynamics 365", "Workday", "Epicor", "Acumatica"],
    "EDMS": ["Documentum", "OpenText", "SharePoint", "Alfresco", "M-Files"],
    "CRM": ["Salesforce", "HubSpot", "Dynamics CRM", "Zoho"],
    "MES": ["Opcenter", "FactoryTalk", "AVEVA MES", "Apriso", "Plex"],
}


def _bust():
    return f"_cb={int(time.time())}{uuid.uuid4().hex[:6]}"


def guess_slugs(company, domain):
    base = domain.split(".")[0].lower()
    name = company.lower().replace(" ", "").replace(",", "").replace(".", "")
    return list(dict.fromkeys([base, name, base.replace("-", ""), name.replace("-", "")]))


def fetch_greenhouse(slug):
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true&{_bust()}",
            timeout=10)
        if r.status_code == 200:
            return [{
                "title": j.get("title", ""),
                "content": j.get("content", ""),
                "url": j.get("absolute_url", ""),
            } for j in r.json().get("jobs", [])]
    except Exception:
        pass
    return None


def fetch_lever(slug):
    try:
        r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json&{_bust()}",
                         timeout=10)
        if r.status_code == 200:
            return [{
                "title": j.get("text", ""),
                "content": j.get("descriptionPlain", "") + " " +
                           " ".join(l.get("text", "") for l in j.get("lists", [])),
                "url": j.get("hostedUrl", ""),
            } for j in r.json()]
    except Exception:
        pass
    return None


def fetch_ashby(slug):
    try:
        r = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}?{_bust()}",
            timeout=10)
        if r.status_code == 200:
            return [{
                "title": j.get("title", ""),
                "content": j.get("descriptionPlain", ""),
                "url": j.get("jobUrl", ""),
            } for j in r.json().get("jobs", [])]
    except Exception:
        pass
    return None


def fetch_jobs_free(company, domain):
    slugs = guess_slugs(company, domain)
    for slug in slugs[:2]:
        for name, fn in [("greenhouse", fetch_greenhouse),
                         ("lever", fetch_lever),
                         ("ashby", fetch_ashby)]:
            jobs = fn(slug)
            if jobs:
                return jobs, f"{name}:{slug}"
    return [], None


def scan_jobs_for_tech(jobs):
    findings = {}
    # Short vendor names that need extra context to avoid false positives
    CONTEXT_REQUIRED = {"CAD", "NX", "PTC", "PLM", "PDM", "Creo"}
    CONTEXT_TERMS = ["software", "tool", "experience", "proficient", "using",
                     "knowledge", "solidworks", "autocad", "plm", "system"]

    for job in jobs:
        text = (job["title"] + " " + job["content"]).lower()
        for category, vendors in TECH_TAXONOMY.items():
            for vendor in vendors:
                pattern = r"\b" + re.escape(vendor.lower()) + r"\b"
                m = re.search(pattern, text)
                if not m:
                    continue
                # For short/ambiguous names, require context nearby
                if vendor in CONTEXT_REQUIRED:
                    window = text[max(0, m.start()-100):m.end()+100]
                    if not any(term in window for term in CONTEXT_TERMS):
                        continue
                findings.setdefault(category, {}).setdefault(vendor, []).append({
                    "job_title": job["title"],
                    "url": job["url"],
                })
    return findings


def scan_technographics_free(company, domain):
    jobs, ats = fetch_jobs_free(company, domain)
    return {
        "ats_detected": ats,
        "jobs_scanned": len(jobs),
        "from_jobs": scan_jobs_for_tech(jobs),
        "from_google": {},
    }