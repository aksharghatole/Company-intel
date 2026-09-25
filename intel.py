import re, json, requests, time, uuid
from bs4 import BeautifulSoup
from technographics import scan_technographics_free

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; IntelBot/1.0)"}


def _cache_buster():
    return f"_cb={int(time.time())}{uuid.uuid4().hex[:6]}"


def _fetch(url, timeout=15, use_head=False):
    sep = "&" if "?" in url else "?"
    busted_url = f"{url}{sep}{_cache_buster()}"
    headers = {
        **HEADERS,
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    if use_head:
        return requests.head(busted_url, headers=headers, timeout=timeout,
                             allow_redirects=True)
    return requests.get(busted_url, headers=headers, timeout=timeout,
                        allow_redirects=True)


def get_tech_stack(domain):
    sigs = {
        "Shopify":            ("script", "cdn.shopify.com"),
        "Stripe.js":          ("script", "js.stripe.com"),
        "Google Analytics":   ("script", "googletagmanager.com/gtag"),
        "Google Tag Manager": ("script", "googletagmanager.com/gtm"),
        "Segment":            ("script", "cdn.segment.com"),
        "HubSpot":            ("script", "js.hs-scripts.com"),
        "Intercom":           ("script", "widget.intercom.io"),
        "Drift":              ("script", "js.driftt.com"),
        "Hotjar":             ("script", "static.hotjar.com"),
        "Mixpanel":           ("script", "cdn.mxpanel.com"),
        "Amplitude":          ("script", "cdn.amplitude.com"),
        "Optimizely":         ("script", "cdn.optimizely.com"),
        "Sentry":             ("script", "browser.sentry-cdn.com"),
        "Datadog":            ("script", "datadoghq-browser-agent.com"),
        "OneTrust":           ("script", "cdn.cookielaw.org"),
        "Cookiebot":          ("script", "consent.cookiebot.com"),
        "Cloudflare Insights":("script", "static.cloudflareinsights.com"),
        "Vercel Insights":    ("script", "vercel-insights.com"),
        "PayPal":             ("script", "paypal.com/sdk/js"),
        "Recurly":            ("script", "js.recurly.com"),
        "Zendesk":            ("script", "static.zdassets.com"),
        "Twilio":             ("script", "sdk.twilio.com"),
        "Auth0":              ("script", "cdn.auth0.com"),
        "Contentful":         ("script", "cdn.contentful.com"),
        "Next.js":            ("link", "/_next/static"),
        "Svelte":             ("link", "/_app/immutable"),
        "Nuxt":               ("link", "/_nuxt/"),
        "Gatsby":             ("link", "/page-data/"),
        "Cloudflare":         ("header", "cf-ray"),
        "AWS CloudFront":     ("header", "x-amz-cf-id"),
        "Vercel":             ("header", "x-vercel-id"),
        "Netlify":            ("header", "x-nf-request-id"),
        "Fastly":             ("header", "x-served-by"),
        "Akamai":             ("header", "x-akamai-transformed"),
        "Nginx":              ("header", "server: nginx"),
        "Apache":             ("header", "server: apache"),
        "Shopify Edge":       ("header", "x-shopify-stage"),
        "React":              ("inline", "__react"),
        "Vue.js":             ("inline", "__vue__"),
        "Angular":            ("inline", "ng-version"),
        "WordPress":          ("inline", "wp-content"),
        "jQuery":             ("inline", "jquery"),
        "Webflow":            ("inline", "webflow"),
        "Squarespace":        ("inline", "squarespace"),
        "Wix":                ("inline", "wix.com"),
        "Drupal":             ("inline", "drupal"),
    }

    found = set()
    try:
        r = _fetch(f"https://{domain}", timeout=15)
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        script_srcs = " ".join((s.get("src") or "").lower() for s in soup.find_all("script"))
        link_hrefs = " ".join((l.get("href") or "").lower() for l in soup.find_all("link"))
        inline_js = " ".join((s.string or "").lower() for s in soup.find_all("script") if not s.get("src"))
        headers_str = " ".join(f"{k.lower()}: {v.lower()}" for k, v in r.headers.items())

        for name, (kind, pattern) in sigs.items():
            pat = pattern.lower()
            if kind == "script" and pat in script_srcs:
                found.add(name)
            elif kind == "link" and pat in link_hrefs:
                found.add(name)
            elif kind == "header" and pat in headers_str:
                found.add(name)
            elif kind == "inline" and pat in inline_js:
                found.add(name)
    except Exception as e:
        return {"error": str(e), "detected": []}

    return {
        "detected": sorted(found),
        "http_status": r.status_code,
        "html_length": len(html),
        "final_url": r.url,
    }


def get_hiring_signals(company, domain):
    jobs = []
    try:
        r = requests.get("https://remotive.com/api/remote-jobs",
                         params={"company_name": company}, timeout=15)
        if r.status_code == 200:
            for j in r.json().get("jobs", []):
                job_company = (j.get("company_name") or "").lower()
                if company.lower() not in job_company:
                    continue
                jobs.append({
                    "title": j.get("title"),
                    "company": j.get("company_name"),
                    "category": j.get("category"),
                    "url": j.get("url"),
                })
            jobs = jobs[:25]
    except Exception:
        pass

    PLM_CAD_KEYWORDS = [
        "SolidWorks", "CATIA", "NX", "Creo", "AutoCAD", "Teamcenter",
        "Windchill", "ENOVIA", "Aras", "SAP PLM", "Oracle Agile",
        "Fusion 360", "Inventor", "Revit", "PLM", "PDM", "CAD",
        "Onshape", "Siemens", "PTC", "Dassault",
    ]
    text = " ".join([j.get("title", "") for j in jobs]).lower()
    mentions = [k for k in PLM_CAD_KEYWORDS if k.lower() in text]

    careers_url = None
    if len(jobs) == 0:
        for path in ["/careers", "/jobs", "/careers/", "/company/careers"]:
            try:
                r = _fetch(f"https://{domain}{path}", timeout=6, use_head=True)
                if r.status_code == 200:
                    careers_url = f"https://{domain}{path}"
                    break
            except Exception:
                continue

    return {
        "open_roles_found": len(jobs),
        "sample_roles": jobs[:10],
        "plm_cad_keywords_in_jobs": mentions,
        "careers_page": careers_url,
    }


def get_firmographics(company, domain):
    data = {"company": company, "domain": domain}
    paths = ["", "/about", "/about-us", "/company",
             "/investor-relations", "/investors", "/en/company",
             "/en/about", "/about/company-profile"]

    for path in paths:
        try:
            r = _fetch(f"https://{domain}{path}", timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(" ", strip=True)

            emp = re.search(
                r"([\d,\.]+\s*[kKmM]?\+?)\s*(employees|staff|people|team members)",
                text, re.I
            )
            rev = (
                re.search(
                    r"([\$€£]\s*[\d,\.]+\s*(?:billion|million|[bBmM]))"
                    r"[^\d]{0,30}(?:revenue|turnover|sales)",
                    text, re.I
                )
                or re.search(
                    r"(?:revenue|turnover|sales)[^\d]{0,30}"
                    r"([\$€£]?\s*[\d,\.]+\s*(?:billion|million|[bBmM]))",
                    text, re.I
                )
            )

            if emp and "employees_mentioned" not in data:
                data["employees_mentioned"] = emp.group(0).strip()
            if rev and "revenue_mentioned" not in data:
                data["revenue_mentioned"] = rev.group(0).strip()

            if "employees_mentioned" in data:
                break
        except Exception:
            continue

    data["linkedin_search"] = f"https://www.linkedin.com/company/{company.lower().replace(' ','-')}"
    data["crunchbase_search"] = f"https://www.crunchbase.com/textsearch?q={company.replace(' ','+')}"
    data["google_employees_search"] = (
        f"https://www.google.com/search?q={company.replace(' ','+')}+number+of+employees"
    )
    return data


def plm_cad_search_links(company):
    q = company.replace(" ", "+")
    return {
        "Siemens Teamcenter":  f"https://www.google.com/search?q={q}+Siemens+Teamcenter+case+study",
        "PTC Windchill":       f"https://www.google.com/search?q={q}+PTC+Windchill+case+study",
        "Dassault ENOVIA":     f"https://www.google.com/search?q={q}+Dassault+ENOVIA+case+study",
        "Dassault SOLIDWORKS": f"https://www.google.com/search?q={q}+SOLIDWORKS+case+study",
        "Autodesk Fusion":     f"https://www.google.com/search?q={q}+Autodesk+Fusion+case+study",
        "SAP PLM":             f"https://www.google.com/search?q={q}+SAP+PLM+case+study",
        "Aras PLM":            f"https://www.google.com/search?q={q}+Aras+PLM+case+study",
    }


def run(company, domain):
    return {
        "company": company,
        "domain": domain,
        "tech_stack": get_tech_stack(domain),
        "hiring_signals": get_hiring_signals(company, domain),
        "firmographics": get_firmographics(company, domain),
        "plm_pdm_cad_search_links": plm_cad_search_links(company),
        "technographics": scan_technographics_free(company, domain),
    }