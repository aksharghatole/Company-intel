"""Public job feeds and conservative ATS link discovery."""
import re
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from safe_web import safe_request
from workday import parse_workday_board

SLUG = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; IntelBot/1.0)"}


def valid_slug(value):
    return isinstance(value, str) and bool(SLUG.fullmatch(value))


def _json(url, params=None):
    # URLs are constructed using fixed provider hosts and validated identifiers.
    try:
        response = requests.get(url, params=params, timeout=6, allow_redirects=False,
                                headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                return data
    except (requests.RequestException, ValueError):
        pass
    return None


def _rows(data, key):
    if isinstance(data, dict) and isinstance(data.get(key), list):
        return [j for j in data[key] if isinstance(j, dict)]
    return None


def _text(*values):
    return " ".join(v for v in values if isinstance(v, str))


def _url(*values):
    for value in values:
        if isinstance(value, str):
            try:
                parsed = urlsplit(value)
                if parsed.scheme == "https" and parsed.hostname and not parsed.username:
                    return value
            except ValueError:
                continue
    return ""


def fetch_workable(slug):
    if not valid_slug(slug):
        return None
    data = _json(f"https://www.workable.com/api/accounts/{slug}", {"details": "true"})
    rows = _rows(data, "jobs")
    if rows is None:
        return None
    return [{"title": j.get("title") or "",
             "content": _text(j.get("description"), j.get("requirements")),
             "url": _url(j.get("url"), j.get("shortlink"), j.get("application_url"))}
            for j in rows]


def fetch_recruitee(slug):
    if not valid_slug(slug) or "_" in slug:
        return None
    data = _json(f"https://{slug}.recruitee.com/api/offers")
    rows = _rows(data, "offers")
    if rows is None:
        return None
    return [{"title": j.get("title") or "",
             "content": _text(j.get("description"), j.get("requirements")),
             "url": _url(j.get("careers_url"), j.get("careers_apply_url"),
                         f"https://{slug}.recruitee.com/o/{j['slug']}" if valid_slug(j.get("slug")) else "")}
            for j in rows]


def fetch_smartrecruiters(slug):
    if not valid_slug(slug):
        return None
    base = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    # Limit detail requests to keep batch scanning bounded. Only successfully
    # retrieved details are returned; coverage is a sample, not a total.
    data = _json(base, {"limit": 12})
    rows = _rows(data, "content")
    if rows is None:
        return None
    jobs = []
    for j in rows[:12]:
        identifier = str(j.get("id") or j.get("uuid") or "")
        if not valid_slug(identifier):
            continue
        detail = _json(f"{base}/{identifier}")
        if not detail:
            continue
        sections = (detail.get("jobAd") or {}).get("sections") or {}
        if not isinstance(sections, dict):
            sections = {}
        content = _text(*(v.get("text") for v in sections.values() if isinstance(v, dict)))
        jobs.append({"title": detail.get("name") or j.get("name") or "",
                     "content": content,
                     "url": _url(detail.get("postingUrl"), detail.get("applyUrl"),
                                 f"{base}/{identifier}")})
    return jobs if not rows or jobs else None


def parse_board_link(url):
    """Recognize only exact ATS host patterns; never follow a supplied API URL."""
    try:
        p = urlsplit(url)
        if p.scheme not in ("http", "https") or p.username or p.password or p.port not in (None, 80, 443):
            return None
        host = (p.hostname or "").lower()
        parts = [part for part in p.path.split("/") if part]
    except ValueError:
        return None
    workday = parse_workday_board(url)
    if workday:
        return "workday", workday
    hosts = {"boards.greenhouse.io": "greenhouse", "job-boards.greenhouse.io": "greenhouse",
             "jobs.lever.co": "lever", "jobs.ashbyhq.com": "ashby",
             "jobs.smartrecruiters.com": "smartrecruiters", "careers.smartrecruiters.com": "smartrecruiters",
             "apply.workable.com": "workable"}
    if host in hosts and parts and valid_slug(parts[0]):
        if host == "apply.workable.com" and parts[0].lower() in {"j", "jobs"}:
            return None
        return hosts[host], parts[0]
    for suffix, name in ((".recruitee.com", "recruitee"), (".workable.com", "workable")):
        if host.endswith(suffix):
            slug = host[:-len(suffix)]
            if valid_slug(slug) and slug.lower() not in {"www", "apply", "help", "api", "app"}:
                return name, slug
    return None


def discover_board_links(domain):
    """Return (provider, slug, source URL) from at most two company pages."""
    found = []
    allowed = {domain, domain.removeprefix("www."), "www." + domain.removeprefix("www.")}
    for path in ("/careers", "/"):
        try:
            response = safe_request(f"https://{domain}{path}", headers=HEADERS, timeout=5)
            final_host = urlsplit(response.url).hostname
            if final_host not in allowed:
                # A redirect to the board itself is evidence of association.
                board = parse_board_link(response.url)
                if board:
                    found.append((*board, f"https://{domain}{path}"))
                continue
            if response.status_code != 200:
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup.find_all(["a", "iframe"]):
                link = tag.get("href") or tag.get("src")
                if not isinstance(link, str):
                    continue
                board = parse_board_link(urljoin(response.url, link))
                if board:
                    found.append((*board, response.url))
        except (requests.RequestException, ValueError, OSError):
            continue
        if found:
            break
    return list(dict.fromkeys(found))[:4]
