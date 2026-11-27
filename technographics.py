import re, requests, time, uuid
from html import unescape
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; IntelBot/1.0)"}

TECH_TAXONOMY = {
    "PLM": ["3DEXPERIENCE", "Teamcenter", "Windchill", "ENOVIA", "Aras PLM", "SAP PLM",
            "Oracle Agile PLM", "Centric PLM", "PTC FlexPLM"],
    "PDM": ["ENOVIA SmarTeam", "SolidWorks PDM", "Windchill PDMLink", "Teamcenter PDM", "Autodesk Vault"],
    "CAD": ["SolidWorks", "CATIA", "Siemens NX", "Creo", "AutoCAD",
            "Inventor", "Fusion 360", "Revit", "Onshape", "Solid Edge"],
    "ERP": ["SAP S/4HANA", "SAP ECC", "Oracle ERP", "NetSuite",
            "Dynamics 365", "Workday", "Epicor", "Acumatica"],
    "EDMS": ["Documentum", "OpenText", "SharePoint", "Alfresco", "M-Files"],
    "CRM": ["Salesforce", "HubSpot", "Dynamics CRM", "Zoho"],
    "MES": ["Opcenter", "FactoryTalk", "AVEVA MES", "Apriso", "Plex"],
    "Embedded": ["Embedded software", "Firmware", "Embedded Linux", "RTOS",
                 "FreeRTOS", "Zephyr RTOS", "AUTOSAR", "Device drivers",
                 "PCB design", "Hardware bring-up", "Board bring-up", "Microcontrollers"],
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


# Canonical names with carefully bounded alternative spellings.
ALIASES = {
    "3DEXPERIENCE": ("3D EXPERIENCE", "3DX"),
    "ENOVIA SmarTeam": ("SmarTeam",),
    "Embedded software": ("embedded systems software", "embedded C", "embedded C++"),
    "Device drivers": ("device driver",),
    "PCB design": ("PCB layout", "printed circuit board design"),
    "Hardware bring-up": ("hardware bring up", "hardware bringup"),
    "Board bring-up": ("board bring up", "board bringup"),
    "Microcontrollers": ("microcontroller", "MCU programming"),
}
AMBIGUOUS = {
    "3DX": r"\b(?:plm|enovia|catia|dassault|platform|3dexperience|solidworks)\b",
    "Creo": r"\b(?:cad|ptc|design|modeling|modelling|software)\b",
    "Inventor": r"\b(?:autodesk|cad|3d modeling|3d modelling|mechanical design)\b",
    "Plex": r"\b(?:mes|manufacturing execution|rockwell|erp)\b",
    "Workday": r"\b(?:hcm|hris|erp|workday financials|workday integration|workday system|workday reporting)\b",
    "Device drivers": r"\b(?:kernel|linux|embedded|firmware|hardware|driver development)\b",
    "device driver": r"\b(?:kernel|linux|embedded|firmware|hardware|driver development)\b",
}


def _job_text(job):
    title = str(job.get("title") or "")
    content = BeautifulSoup(unescape(str(job.get("content") or "")), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", title + " — " + content).strip()


def scan_jobs_for_tech(jobs):
    """Return job mentions, not proof of installed software or outsourcing demand."""
    findings = {}
    for job in jobs:
        text = _job_text(job)
        for category, vendors in TECH_TAXONOMY.items():
            for vendor in vendors:
                accepted = None
                for alias in (vendor, *ALIASES.get(vendor, ())):
                    pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
                    for match in re.finditer(pattern, text, re.I):
                        window = text[max(0, match.start()-100):match.end()+100]
                        rule = AMBIGUOUS.get(alias)
                        if rule and not re.search(rule, window, re.I):
                            continue
                        accepted = match
                        break
                    if accepted:
                        break
                if not accepted:
                    continue
                snippet = text[max(0, accepted.start()-80):accepted.end()+100]
                findings.setdefault(category, {}).setdefault(vendor, []).append({
                    "job_title": job.get("title") or "",
                    "url": job.get("url") or "",
                    "matched_term": accepted.group(),
                    "snippet": snippet,
                })
    return findings


def summarize_evidence(findings):
    """Score corroboration of mentions only; board identity remains unverified."""
    summary = {}
    for category, signals in findings.items():
        summary[category] = {}
        for name, evidence in signals.items():
            links = {item.get("url") for item in evidence if item.get("url")}
            summary[category][name] = {
                "distinct_job_links": len(links),
                "strength": ("multiple job links" if len(links) > 1 else
                             "single job link" if links else "unlinked mention"),
            }
    return summary


def scan_technographics_free(company, domain):
    jobs, ats = fetch_jobs_free(company, domain)
    findings = scan_jobs_for_tech(jobs)
    return {
        "ats_detected": ats,
        "jobs_scanned": len(jobs),
        "from_jobs": findings,
        "evidence_summary": summarize_evidence(findings),
        "from_google": {},
    }
