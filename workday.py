"""Best-effort access to website-linked Workday career boards.

CXS is an unofficial career-site endpoint. Never guess tenant/site identifiers,
follow API redirects, retry blocks, or bypass access controls.
"""
import re
from urllib.parse import quote, urlsplit, unquote

import requests

HOST = re.compile(r"([a-z0-9][a-z0-9-]{0,62})\.wd[0-9]{1,3}\.myworkdayjobs\.com")
SITE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}")
LOCALE = re.compile(r"[a-z]{2,3}-[A-Z]{2}")
RELEVANT = re.compile(r"\b(?:engineer(?:ing)?|firmware|embedded|hardware|software|PLM|PDM|CAD|electronic[s]?|developer|design|manufacturing)\b", re.I)
HEADERS = {"Accept": "application/json", "User-Agent": "CompanyIntel/1.0"}
LIMIT = 12


def parse_workday_board(url):
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if parsed.scheme != "https" or parsed.username is not None or parsed.password is not None or parsed.port not in (None, 443):
            return None
        if not HOST.fullmatch(host):
            return None
        parts = [p for p in parsed.path.split("/") if p]
        if parts and LOCALE.fullmatch(parts[0]):
            parts.pop(0)
        if not parts or not SITE.fullmatch(parts[0]) or parts[0].lower() in {"wday", "job", "login", "apply"}:
            return None
        return f"{host}/{parts[0]}"
    except ValueError:
        return None


def board_url(key):
    if not isinstance(key, str) or parse_workday_board("https://" + key) != key:
        return ""
    return "https://" + key


def _request_json(session, method, url, **kwargs):
    try:
        response = session.request(method, url, headers=HEADERS, timeout=5,
                                   allow_redirects=False, **kwargs)
        if response.status_code in (401, 403, 429) or response.headers.get("cf-mitigated", "").lower() == "challenge":
            return None, "access restricted"
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"
        data = response.json()
        if not isinstance(data, dict):
            return None, "unexpected response"
        return data, ""
    except (requests.RequestException, ValueError):
        return None, "request failed"


def _job_path(value):
    if not isinstance(value, str) or not value.startswith("/job/") or len(value) > 1500:
        return None
    try:
        p = urlsplit(value)
        decoded = unquote(p.path)
        if p.scheme or p.netloc or p.query or p.fragment or not decoded.startswith("/job/"):
            return None
        if "\\" in decoded or any(ord(c) < 32 for c in decoded) or any(part in (".", "..") for part in decoded.split("/")):
            return None
        # Canonicalize path encoding; do not permit nested escapes.
        if "%" in decoded:
            return None
        return quote(decoded, safe="/-_.~")
    except (ValueError, UnicodeError):
        return None


def fetch_workday(key):
    """Return (jobs, status, published total); None jobs means unavailable."""
    public_url = board_url(key)
    if not public_url:
        return None, "invalid board", None
    host, site = key.split("/")
    tenant = HOST.fullmatch(host).group(1)
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    with requests.Session() as session:
        session.trust_env = False
        data, error = _request_json(session, "POST", base + "/jobs",
                                   json={"limit": 20, "offset": 0, "searchText": "", "appliedFacets": {}})
        if error:
            return None, error, None
        rows = data.get("jobPostings")
        total = data.get("total")
        total = total if type(total) is int and total >= 0 else None
        if not isinstance(rows, list):
            return None, "unexpected response", total
        if not rows:
            return ([], "available", total) if total in (None, 0) else (None, "incomplete listing", total)
        rows = [row for row in rows[:20] if isinstance(row, dict)]
        rows.sort(key=lambda row: not bool(RELEVANT.search(str(row.get("title") or ""))))
        jobs, seen = [], set()
        failed = False
        for row in rows:
            if len(seen) >= LIMIT:
                break
            path = _job_path(row.get("externalPath"))
            if not path or path in seen:
                continue
            seen.add(path)
            detail, error = _request_json(session, "GET", base + path)
            if error:
                failed = True
                if error == "access restricted":
                    return (jobs if jobs else None), error, total
                continue
            info = detail.get("jobPostingInfo")
            if not isinstance(info, dict):
                failed = True
                continue
            jobs.append({"title": info.get("title") or row.get("title") or "",
                         "content": info.get("jobDescription") or "",
                         "url": public_url + path,
                         "posted_date": info.get("startDate") or "",
                         "location": info.get("location") or row.get("locationsText") or "",
                         "requisition_id": info.get("jobReqId") or ""})
        if not jobs:
            return None, "details unavailable", total
        return jobs, "partial details" if failed else "available", total
