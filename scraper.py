import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

from tailor import score_and_classify_job

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
JOBS_DB_PATH = DATA_DIR / "jobs_db.json"

DEFAULT_SEARCH_QUERIES = [
    {"search_term": "Working Student Project Management", "location": "Berlin, Germany"},
    {"search_term": "Working Student Product Management", "location": "Berlin, Germany"},
    {"search_term": "Working Student Operations AI", "location": "Berlin, Germany"},
    {"search_term": "Working Student Business Operations", "location": "Berlin, Germany"},
    {"search_term": "Working Student Project Manager Remote", "location": "Germany"},
]


def load_jobs_db() -> List[Dict[str, Any]]:
    if not JOBS_DB_PATH.exists():
        return []
    try:
        with open(JOBS_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_jobs_db(jobs: List[Dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(JOBS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)


def make_job_id(company: str, title: str, url: str) -> str:
    raw = f"{company.strip().lower()}|{title.strip().lower()}|{url.strip()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:10]


def clean_val(val: Any, default: str = "") -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    s = str(val).strip()
    return default if s.lower() in ("nan", "none", "null") else s


def run_job_scrape(
    search_terms: Optional[List[str]] = None,
    location: str = "Berlin, Germany",
    results_wanted: int = 15,
    hours_old: int = 168,
    sites: Optional[List[str]] = None,
) -> Dict[str, Any]:
    from jobspy import scrape_jobs

    if not sites:
        sites = ["linkedin", "indeed"]

    queries = (
        [{"search_term": q, "location": location} for q in search_terms]
        if search_terms
        else DEFAULT_SEARCH_QUERIES[:3]
    )

    existing_jobs = load_jobs_db()
    existing_ids = {j["id"] for j in existing_jobs}
    existing_keys = {f"{j.get('company','').lower()}|{j.get('title','').lower()}" for j in existing_jobs}

    newly_added = []
    errors = []

    for q in queries:
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=q["search_term"],
                location=q["location"],
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed="Germany",
                linkedin_fetch_description=True,
            )
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                title = clean_val(row.get("title"), "Working Student Role")
                company = clean_val(row.get("company"), "Unknown Company")
                job_url = clean_val(row.get("job_url_direct")) or clean_val(row.get("job_url"))
                loc = clean_val(row.get("location"), q["location"])
                desc = clean_val(row.get("description"), "")
                site = clean_val(row.get("site"), "linkedin")
                date_posted = clean_val(row.get("date_posted"), datetime.now().strftime("%Y-%m-%d"))

                # Skip senior/director roles immediately
                t_low = title.lower()
                if any(bad in t_low for bad in ["senior", "head of", "director", "vp ", "principal", "team lead", "teamleiter"]):
                    continue

                dedup_key = f"{company.lower()}|{title.lower()}"
                jid = make_job_id(company, title, job_url)
                if jid in existing_ids or dedup_key in existing_keys:
                    continue

                # Format salary if present in JobSpy columns
                min_amt = clean_val(row.get("min_amount"))
                max_amt = clean_val(row.get("max_amount"))
                currency = clean_val(row.get("currency"), "EUR")
                interval = clean_val(row.get("interval"), "")
                salary_str = ""
                if min_amt or max_amt:
                    salary_str = f"{min_amt}-{max_amt} {currency} ({interval})".strip(" -()")

                job_obj = {
                    "id": jid,
                    "title": title,
                    "company": company,
                    "location": loc,
                    "job_url": job_url,
                    "source": site.capitalize(),
                    "date_posted": date_posted,
                    "date_found": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "salary": salary_str,
                    "description": desc,
                    "status": "New",
                    "cv_pdf": "",
                    "cover_letter_pdf": "",
                    "cv_url": "",
                    "cover_letter_url": "",
                    "notes": "",
                    "synced_to_sheets": False,
                }

                analysis = score_and_classify_job(job_obj)
                job_obj.update(analysis)

                existing_jobs.append(job_obj)
                existing_ids.add(jid)
                existing_keys.add(dedup_key)
                newly_added.append(job_obj)

        except Exception as e:
            errors.append(f"{q['search_term']}: {str(e)}")

    from metadata_enricher import enrich_jobs_metadata
    enrich_jobs_metadata(existing_jobs)

    # Sort all jobs by match_score descending
    existing_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    save_jobs_db(existing_jobs)

    return {
        "added_count": len(newly_added),
        "total_count": len(existing_jobs),
        "newly_added": newly_added,
        "errors": errors,
    }
