import csv
import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
SETTINGS_PATH = DATA_DIR / "settings.json"
GSHEETS_CMD = r"C:\Users\guill\.gemini\config\plugins\gsheets\skills\gsheets\scripts\gsheets.cmd"

SHEET_HEADERS = [
    "Match Score",
    "Status",
    "CV & Cover Letter Edited?",
    "Posted / Age",
    "Applicants Count",
    "Job Title",
    "Company",
    "Category",
    "Location",
    "Language / Proximity Fit",
    "Pay / Rate",
    "Direct Apply URL",
    "Tailored CV PDF Path",
    "Tailored Cover Letter Path",
    "Why You Match / Key Keywords",
    "Source",
]


def load_settings() -> Dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {"spreadsheet_id": "", "spreadsheet_url": ""}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"spreadsheet_id": "", "spreadsheet_url": ""}


def save_settings(settings: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def export_local_csv(jobs: List[Dict[str, Any]], filename: str = "Job_Tracker_Quick_Apply.csv") -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / filename
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(SHEET_HEADERS)
        for j in jobs:
            writer.writerow(_job_to_row(j))
    return csv_path


def _job_to_row(j: Dict[str, Any]) -> List[str]:
    has_pdfs = bool(j.get("cv_pdf") and j.get("cover_letter_pdf"))
    edited_status = "✅ Yes (Tailored PDFs Ready)" if has_pdfs else "⏳ No (Not tailored yet)"
    posted_ago = str(j.get("posted_ago") or j.get("date_posted") or "Recent")
    applicants = str(j.get("applicants_text") or "Direct Portal (No counter)")
    return [
        f"{j.get('match_score', 0)}%",
        str(j.get("status", "New")),
        edited_status,
        posted_ago,
        applicants,
        str(j.get("title", "")),
        str(j.get("company", "")),
        str(j.get("category_label", "Project Management")),
        str(j.get("location", "")),
        str(j.get("language_req", "English Friendly")),
        str(j.get("extracted_pay", "Not listed")),
        str(j.get("job_url", "")),
        str(j.get("cv_pdf", "Not generated yet")),
        str(j.get("cover_letter_pdf", "Not generated yet")),
        str(j.get("why_fits", "")),
        str(j.get("source", "")),
    ]


def check_gsheets_auth() -> bool:
    try:
        res = subprocess.run(
            [GSHEETS_CMD, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return "Logged in" in (res.stdout + res.stderr)
    except Exception:
        return False


def sync_jobs_to_google_sheet(
    guillermo_jobs: List[Dict[str, Any]],
    nancy_jobs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    csv_path = export_local_csv(guillermo_jobs, "Job_Tracker_Quick_Apply.csv")
    if nancy_jobs is not None:
        export_local_csv(nancy_jobs, "Nancy_Job_Tracker_Quick_Apply.csv")

    if not check_gsheets_auth():
        return {
            "synced": False,
            "reason": "Google Sheets CLI not logged in yet. Local CSV updated.",
            "local_csv": str(csv_path),
        }

    settings = load_settings()
    sheet_id = settings.get("spreadsheet_id")
    if not sheet_id:
        return {"synced": False, "reason": "No spreadsheet ID configured.", "local_csv": str(csv_path)}

    g_rows = [SHEET_HEADERS] + [_job_to_row(j) for j in guillermo_jobs]
    batch_payload = [
        {"op": "clear", "range": "'Guillermo - PM & AI'!A1:P500"},
        {"op": "write", "range": "'Guillermo - PM & AI'!A1", "data": g_rows},
    ]

    if nancy_jobs is not None:
        n_rows = [SHEET_HEADERS] + [_job_to_row(j) for j in nancy_jobs]
        batch_payload.extend([
            {"op": "clear", "range": "'Nancy - Office Mgmt (Zoo)'!A1:P500"},
            {"op": "write", "range": "'Nancy - Office Mgmt (Zoo)'!A1", "data": n_rows},
        ])

    batch_file = DATA_DIR / "sheets_batch_sync.json"
    with open(batch_file, "w", encoding="utf-8") as f:
        json.dump(batch_payload, f, ensure_ascii=False, indent=2)

    res = subprocess.run(
        [GSHEETS_CMD, "mutate", "batch", sheet_id, "-f", str(batch_file)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if res.returncode != 0:
        return {
            "synced": False,
            "reason": res.stderr or res.stdout,
            "local_csv": str(csv_path),
            "spreadsheet_url": settings.get("spreadsheet_url", ""),
        }

    return {
        "synced": True,
        "rows_written": len(guillermo_jobs) + (len(nancy_jobs) if nancy_jobs else 0),
        "spreadsheet_id": sheet_id,
        "spreadsheet_url": settings["spreadsheet_url"],
        "local_csv": str(csv_path),
    }
