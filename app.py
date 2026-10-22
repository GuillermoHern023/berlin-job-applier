import subprocess
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pdf_generator import (
    load_master_profile,
    generate_master_cv,
    OUTPUT_DIR,
)
from scraper import (
    load_jobs_db,
    save_jobs_db,
    run_job_scrape,
    make_job_id,
)
from tailor import (
    score_and_classify_job,
    select_tailored_content,
    generate_job_application_bundle,
)
from nancy_engine import (
    load_nancy_profile,
    load_nancy_jobs_db,
    save_nancy_jobs_db,
    generate_nancy_master_cv,
    score_nancy_job,
    select_nancy_tailored_content,
    generate_nancy_application_bundle,
    scrape_nancy_jobs,
)
from sheets_sync import (
    sync_jobs_to_google_sheet,
    export_local_csv,
    load_settings,
    check_gsheets_auth,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Guillermo & Nancy Auto-Job Applier & CV Tailor")
app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="files")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ScrapeRequest(BaseModel):
    user: str = "guillermo"
    search_terms: Optional[List[str]] = None
    location: str = "Berlin, Germany"
    results_wanted: int = 12
    hours_old: int = 336
    sites: Optional[List[str]] = ["linkedin", "indeed"]


class ManualJobRequest(BaseModel):
    user: str = "guillermo"
    title: str
    company: str
    location: str = "Berlin, Germany"
    job_url: str = ""
    description: str = ""
    salary: str = ""


class TailorRequest(BaseModel):
    user: str = "guillermo"
    custom_bullets: Optional[List[str]] = None
    custom_paragraphs: Optional[List[str]] = None


class StatusUpdateRequest(BaseModel):
    user: str = "guillermo"
    status: str
    notes: Optional[str] = None


@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/state")
def get_state():
    profile = load_master_profile()
    nancy_profile = load_nancy_profile()
    jobs = load_jobs_db()
    nancy_jobs = load_nancy_jobs_db()
    settings = load_settings()

    master_cv = OUTPUT_DIR / "Guillermo_Hernandez_CV_Master.pdf"
    if not master_cv.exists():
        generate_master_cv()

    nancy_cv = OUTPUT_DIR / "Nancy_Schuetze_Lebenslauf_Master.pdf"
    if not nancy_cv.exists():
        generate_nancy_master_cv()

    return {
        "profile": profile,
        "nancy_profile": nancy_profile,
        "jobs": jobs,
        "nancy_jobs": nancy_jobs,
        "master_cv_url": "/files/Guillermo_Hernandez_CV_Master.pdf",
        "nancy_cv_url": "/files/Nancy_Schuetze_Lebenslauf_Master.pdf",
        "gsheets_logged_in": check_gsheets_auth(),
        "spreadsheet_url": settings.get("spreadsheet_url", ""),
    }


@app.post("/api/scrape")
def api_scrape_jobs(req: ScrapeRequest):
    if req.user == "nancy":
        result = scrape_nancy_jobs(
            search_terms=req.search_terms,
            location=req.location,
            results_wanted=req.results_wanted,
            hours_old=req.hours_old,
            sites=req.sites,
        )
        nancy_jobs = load_nancy_jobs_db()
        export_local_csv(nancy_jobs, "Nancy_Job_Tracker_Quick_Apply.csv")
        return {"scrape_result": result, "jobs": nancy_jobs}

    result = run_job_scrape(
        search_terms=req.search_terms,
        location=req.location,
        results_wanted=req.results_wanted,
        hours_old=req.hours_old,
        sites=req.sites,
    )
    jobs = load_jobs_db()
    export_local_csv(jobs)
    return {"scrape_result": result, "jobs": jobs}


@app.post("/api/refresh-metadata")
def api_refresh_metadata(user: str = "guillermo"):
    from metadata_enricher import enrich_jobs_metadata
    if user == "nancy":
        jobs = load_nancy_jobs_db()
        enrich_jobs_metadata(jobs, force_refresh=True)
        save_nancy_jobs_db(jobs)
        export_local_csv(jobs, "Nancy_Job_Tracker_Quick_Apply.csv")
        return {"jobs": jobs}
    jobs = load_jobs_db()
    enrich_jobs_metadata(jobs, force_refresh=True)
    save_jobs_db(jobs)
    export_local_csv(jobs)
    return {"jobs": jobs}


@app.post("/api/jobs/manual")
def api_add_manual_job(req: ManualJobRequest):
    jid = make_job_id(req.company, req.title, req.job_url)
    job_obj = {
        "id": jid,
        "title": req.title,
        "company": req.company,
        "location": req.location,
        "job_url": req.job_url,
        "source": "Manual",
        "date_posted": "Today",
        "salary": req.salary,
        "description": req.description,
        "status": "New",
        "cv_pdf": "",
        "cover_letter_pdf": "",
        "cv_url": "",
        "cover_letter_url": "",
        "notes": "",
    }
    if req.user == "nancy":
        jobs = load_nancy_jobs_db()
        job_obj.update(score_nancy_job(job_obj))
        jobs = [j for j in jobs if j["id"] != jid]
        jobs.insert(0, job_obj)
        save_nancy_jobs_db(jobs)
        export_local_csv(jobs, "Nancy_Job_Tracker_Quick_Apply.csv")
        return {"job": job_obj, "jobs": jobs}

    jobs = load_jobs_db()
    job_obj.update(score_and_classify_job(job_obj))
    jobs = [j for j in jobs if j["id"] != jid]
    jobs.insert(0, job_obj)
    save_jobs_db(jobs)
    export_local_csv(jobs)
    return {"job": job_obj, "jobs": jobs}


@app.get("/api/jobs/{job_id}/preview-tailor")
def api_preview_tailor(job_id: str, user: str = "guillermo"):
    if user == "nancy":
        jobs = load_nancy_jobs_db()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        n_profile = load_nancy_profile()
        tailored = select_nancy_tailored_content(job, n_profile)
        return {
            "job": job,
            "tailored": tailored,
            "all_auto1_bullets": [],
        }

    jobs = load_jobs_db()
    job = next((j for j in jobs if j["id"] == job_id), None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    profile = load_master_profile()
    tailored = select_tailored_content(job, profile)
    return {
        "job": job,
        "tailored": tailored,
        "all_auto1_bullets": profile["auto1_bullet_pool"],
    }


@app.post("/api/jobs/{job_id}/tailor")
def api_tailor_job(job_id: str, req: TailorRequest):
    if req.user == "nancy":
        jobs = load_nancy_jobs_db()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        bundle = generate_nancy_application_bundle(job, custom_paragraphs=req.custom_paragraphs)
        job["cv_pdf"] = bundle["cv_pdf"]
        job["cover_letter_pdf"] = bundle["cover_letter_pdf"]
        job["cv_url"] = bundle["cv_url"]
        job["cover_letter_url"] = bundle["cover_letter_url"]
        if job.get("status") == "New":
            job["status"] = "Ready to Apply"
        save_nancy_jobs_db(jobs)
        export_local_csv(jobs, "Nancy_Job_Tracker_Quick_Apply.csv")
        return {"job": job, "bundle": bundle}

    jobs = load_jobs_db()
    job = next((j for j in jobs if j["id"] == job_id), None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    bundle = generate_job_application_bundle(
        job,
        custom_bullets=req.custom_bullets,
        custom_paragraphs=req.custom_paragraphs,
    )
    job["cv_pdf"] = bundle["cv_pdf"]
    job["cover_letter_pdf"] = bundle["cover_letter_pdf"]
    job["cv_url"] = bundle["cv_url"]
    job["cover_letter_url"] = bundle["cover_letter_url"]
    if job.get("status") == "New":
        job["status"] = "Ready to Apply"

    save_jobs_db(jobs)
    export_local_csv(jobs)
    return {"job": job, "bundle": bundle}


@app.post("/api/jobs/{job_id}/status")
def api_update_job_status(job_id: str, req: StatusUpdateRequest):
    if req.user == "nancy":
        jobs = load_nancy_jobs_db()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job["status"] = req.status
        save_nancy_jobs_db(jobs)
        export_local_csv(jobs, "Nancy_Job_Tracker_Quick_Apply.csv")
        return {"job": job}

    jobs = load_jobs_db()
    job = next((j for j in jobs if j["id"] == job_id), None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job["status"] = req.status
    save_jobs_db(jobs)
    export_local_csv(jobs)
    return {"job": job}


@app.post("/api/jobs/{job_id}/open-folder")
def api_open_job_folder(job_id: str, user: str = "guillermo"):
    jobs = load_nancy_jobs_db() if user == "nancy" else load_jobs_db()
    job = next((j for j in jobs if j["id"] == job_id), None)
    if not job or not job.get("cv_pdf"):
        subprocess.Popen(["explorer.exe", str(OUTPUT_DIR)])
        return {"opened": str(OUTPUT_DIR)}
    cv_path = Path(job["cv_pdf"])
    subprocess.Popen(["explorer.exe", f"/select,{str(cv_path)}"])
    return {"opened": str(cv_path.parent)}


@app.post("/api/sync-sheets")
def api_sync_sheets():
    g_jobs = load_jobs_db()
    n_jobs = load_nancy_jobs_db()
    return sync_jobs_to_google_sheet(g_jobs, n_jobs)
