import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests


def resolve_direct_career_url(job: Dict[str, Any]) -> Optional[str]:
    """
    Resolves the official direct company careers portal or ATS apply URL.
    Returns None if no specific direct URL can be determined (frontend will fall back to smart search).
    """
    url = str(job.get("job_url") or "").strip()
    direct = str(job.get("direct_apply_url") or job.get("job_url_direct") or "").strip()
    if direct and direct.startswith("http"):
        return direct

    # Check if job_url is already an ATS or direct employer domain
    ats_domains = [
        "smartrecruiters.com", "greenhouse.io", "recruitee.com", "workdayjobs.com",
        "ashbyhq.com", "hibob.com", "softgarden.de", "corning.com", "grnh.se",
        "personio.de", "join.com", "jobs.personio.de"
    ]
    u_low = url.lower()
    if any(d in u_low for d in ats_domains) or ("linkedin.com" not in u_low and "indeed.com" not in u_low and url.startswith("http")):
        return url

    comp = str(job.get("company") or "").lower()
    title = str(job.get("title") or "")
    t_low = title.lower()
    enc_title = urllib.parse.quote_plus(title)

    if "tiktok" in comp:
        if "project management" in t_low or "gbs" in t_low:
            return "https://lifeattiktok.com/search/7694281881915672837"
        return f"https://careers.tiktok.com/position?keywords={enc_title}&location=Berlin"
    elif "sap" in comp:
        if "business ai" in t_low:
            return "https://jobs.smartrecruiters.com/SAP/744000109968962-working-student-f-m-d-product-management-for-sap-business-ai"
        if "hana cloud" in t_low:
            return "https://jobs.smartrecruiters.com/SAPITBusinessSysteme/744000162052409-working-student-w-m-d-sap-hana-cloud-infrastructure-"
        return f"https://jobs.sap.com/search/?q={enc_title}&locationsearch=Berlin"
    elif "knorr-bremse" in comp:
        return f"https://careers.knorr-bremse.com/search/?q={enc_title}&locationsearch=berlin"
    elif "siemens energy" in comp:
        return f"https://jobs.siemens-energy.com/careers?query={enc_title}&location=Berlin"
    elif "siemens" in comp:
        return f"https://jobs.siemens.com/careers?query={enc_title}&location=Berlin"
    elif "deloitte" in comp:
        return f"https://jobs.deloitte.de/search/?q={enc_title}&locationsearch=Berlin"
    elif "check24" in comp:
        return f"https://jobs.check24.de/jobs?location=Berlin&query={enc_title}"
    elif "deutsche bahn" in comp or comp == "db":
        return f"https://db.jobs/de-de/suche?keywords={enc_title}&location=Berlin"
    elif "tesla" in comp:
        return f"https://www.tesla.com/careers/search/?query={enc_title}&location=Berlin"
    elif "enpal" in comp:
        return f"https://jobs.enpal.de/jobs?query={enc_title}"
    elif "daimler" in comp:
        return f"https://www.daimlertruck.com/karriere/job-suche/?search={enc_title}&location=Berlin"
    elif "databricks" in comp:
        return "https://www.databricks.com/company/careers?location=Berlin"
    elif "kpmg" in comp:
        return f"https://kpmg.com/de/de/home/karriere/jobsuche.html?searchField={enc_title}"
    elif "pwc" in comp:
        return f"https://karriere.pwc.de/jobs?query={enc_title}"

    return None


def compute_days_ago(date_posted_str: str, posted_time_ago_raw: str = "") -> tuple[int, str]:
    """
    Returns (days_ago: int, human_label: str)
    """
    now = datetime.now().date()
    raw_clean = (posted_time_ago_raw or "").strip()

    # Check if raw LinkedIn string says hours/minutes ago
    if raw_clean:
        low = raw_clean.lower()
        if any(w in low for w in ["hour", "minute", "stunde", "minute", "just now", "gerade"]):
            return 0, f"🔥 {raw_clean} ({now.strftime('%Y-%m-%d')})"
        m_day = re.search(r"(\d+)\s*(?:day|tag)", low)
        if m_day:
            d = int(m_day.group(1))
            prefix = "🔥 " if d <= 1 else ("⚡ " if d <= 3 else "")
            return d, f"{prefix}{raw_clean} ({date_posted_str or 'Recent'})"
        m_wk = re.search(r"(\d+)\s*(?:week|woche)", low)
        if m_wk:
            d = int(m_wk.group(1)) * 7
            return d, f"{raw_clean} ({date_posted_str})"

    if date_posted_str and re.match(r"^\d{4}-\d{2}-\d{2}$", str(date_posted_str).strip()):
        try:
            dt = datetime.strptime(str(date_posted_str).strip(), "%Y-%m-%d").date()
            diff = max(0, (now - dt).days)
            if diff == 0:
                return 0, f"🔥 Today ({date_posted_str})"
            elif diff == 1:
                return 1, f"🔥 Yesterday ({date_posted_str})"
            elif diff <= 3:
                return diff, f"⚡ {diff} days ago ({date_posted_str})"
            else:
                return diff, f"{diff} days ago ({date_posted_str})"
        except Exception:
            pass

    return 99, str(date_posted_str or "Recent")


def parse_applicants_badge(raw_app: str, source: str) -> tuple[int, str]:
    """
    Returns (numeric_estimate, display_badge)
    """
    clean = " ".join((raw_app or "").split()).strip()
    if not clean:
        if "linkedin" in (source or "").lower():
            return 999, "LinkedIn (Click to view)"
        return 999, "Direct Portal (No counter)"

    low = clean.lower()
    # e.g. "Be among the first 25 applicants" / "Gehören Sie zu den ersten 25 Bewerbern"
    if "first 25" in low or "ersten 25" in low or "under 25" in low:
        return 12, f"🟢 < 25 applicants ({clean})"

    m = re.search(r"(\d+)", clean)
    if m:
        num = int(m.group(1))
        if "over" in low or "über" in low or "mehr als" in low or num >= 100:
            return max(num, 150), f"🔴 {clean}"
        elif num <= 35:
            return num, f"🟢 {clean}"
        else:
            return num, f"🟡 {clean}"

    return 999, clean


def _fetch_single_linkedin_meta(job: Dict[str, Any]) -> Dict[str, Any]:
    url = str(job.get("job_url") or "")
    source = str(job.get("source") or "")
    date_posted = str(job.get("date_posted") or "")

    raw_posted_ago = ""
    raw_applicants = ""

    if "linkedin.com/jobs/view/" in url:
        try:
            resp = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=6,
            )
            if resp.status_code == 200:
                html = resp.text
                m_app = re.search(r'num-applicants[^>]*>([^<]+)<', html)
                if m_app:
                    raw_applicants = " ".join(m_app.group(1).split())
                m_post = re.search(r'posted-time-ago[^>]*>([^<]+)<', html)
                if m_post:
                    raw_posted_ago = " ".join(m_post.group(1).split())
                if not job.get("description") or len(str(job.get("description")).strip()) < 50:
                    m_desc = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', html, re.DOTALL)
                    if m_desc:
                        clean_desc = re.sub(r'<[^>]+>', ' ', m_desc.group(1))
                        job["description"] = " ".join(clean_desc.split())
        except Exception:
            pass

    days_ago, posted_label = compute_days_ago(date_posted, raw_posted_ago)
    app_num, app_label = parse_applicants_badge(raw_applicants, source)

    job["days_ago"] = days_ago
    job["posted_ago"] = posted_label
    job["applicants_num"] = app_num
    job["applicants_text"] = app_label
    job["direct_apply_url"] = resolve_direct_career_url(job)
    return job


def enrich_jobs_metadata(jobs: List[Dict[str, Any]], force_refresh: bool = False) -> List[Dict[str, Any]]:
    # Always ensure direct_apply_url is populated for all jobs
    for j in jobs:
        if force_refresh or not j.get("direct_apply_url"):
            j["direct_apply_url"] = resolve_direct_career_url(j)

    to_enrich = [
        j for j in jobs
        if force_refresh or "applicants_text" not in j or "posted_ago" not in j
    ]
    if not to_enrich:
        return jobs

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_fetch_single_linkedin_meta, to_enrich))

    return jobs
