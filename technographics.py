import re, requests, time, uuid
from html import unescape
from bs4 import BeautifulSoup
from workday import fetch_workday, board_url
from ats_providers import (fetch_workable, fetch_recruitee, fetch_smartrecruiters,
                           discover_board_links, valid_slug)

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
    base = domain.lower().removeprefix("www.").split(".")[0]
    name = re.sub(r"[^a-z0-9_-]", "", company.lower())
    return [slug for slug in dict.fromkeys([base, name, base.replace("-", ""), name.replace("-", "")])
            if valid_slug(slug)]


def fetch_greenhouse(slug):
    if not valid_slug(slug):
        return None
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true&{_bust()}",
            timeout=6, allow_redirects=False)
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
    if not valid_slug(slug):
        return None
    try:
        r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json&{_bust()}",
                         timeout=6, allow_redirects=False)
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
    if not valid_slug(slug):
        return None
    try:
        r = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}?{_bust()}",
            timeout=6, allow_redirects=False)
        if r.status_code == 200:
            return [{
                "title": j.get("title", ""),
                "content": j.get("descriptionPlain", ""),
                "url": j.get("jobUrl", ""),
            } for j in r.json().get("jobs", [])]
    except Exception:
        pass
    return None


def _discover_jobs(company, domain):
    providers = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby,
                 "workable": fetch_workable, "recruitee": fetch_recruitee,
                 "smartrecruiters": fetch_smartrecruiters}
    tried = set()
    unavailable = None
    for name, slug, source in discover_board_links(domain):
        tried.add((name, slug.lower()))
        if name == "workday":
            jobs, status, total = fetch_workday(slug)
            result = (jobs or [], f"{name}:{slug}", "website-linked", source,
                      {"ats_access": status, "ats_board_url": board_url(slug),
                       "ats_total_reported": total})
            if jobs is not None:
                return result
            if unavailable is None:
                unavailable = result
            continue
        jobs = providers[name](slug)
        if jobs is not None:
            return jobs, f"{name}:{slug}", "website-linked", source, {"ats_access": "available"}
    # Do not replace a known but inaccessible board with an unverified guess.
    if unavailable is not None:
        return unavailable
    for slug in guess_slugs(company, domain)[:2]:
        for name, fetcher in providers.items():
            if (name, slug.lower()) in tried:
                continue
            jobs = fetcher(slug)
            if jobs:
                return jobs, f"{name}:{slug}", "inferred", "", {"ats_access": "available"}
    return [], None, "not found", "", {"ats_access": "not found"}


def discover_jobs(company, domain):
    return _discover_jobs(company, domain)[:4]


def fetch_jobs_free(company, domain):
    jobs, ats, _, _ = discover_jobs(company, domain)
    return jobs, ats


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
    jobs, ats, identity, source, metadata = _discover_jobs(company, domain)
    findings = scan_jobs_for_tech(jobs)
    return {
        "ats_detected": ats,
        "ats_identity": identity,
        "ats_source_url": source,
        **metadata,
        "ats_coverage": ("first listing page, up to 12 detailed jobs" if (ats or "").startswith("workday:") else
                         "sample (up to 12 detailed jobs)" if (ats or "").startswith("smartrecruiters:") else
                         "returned public jobs"),
        "jobs_scanned": len(jobs),
        "from_jobs": findings,
        "evidence_summary": summarize_evidence(findings),
        "from_google": {},
    }
