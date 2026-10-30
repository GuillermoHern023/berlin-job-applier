import os
import sys
import json
import re
import shutil
import urllib.parse
import smtplib
from datetime import datetime
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Ensure UTF-8 stdout
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"
DOCS_DIR = BASE_DIR / "docs"
REPORT_TXT_PATH = BASE_DIR / "latest_job_digest.txt"
DASHBOARD_HTML_PATH = BASE_DIR / "dashboard.html"
ARTIFACT_DASHBOARD_PATH = Path(r"C:\Users\guill\.gemini\antigravity\brain\e708b6f5-3e3c-4683-86c2-48a58698cce4\job_dashboard.html")

RECIPIENT_EMAILS = ["guillejhl@gmail.com", "schuetzenc@gmail.com"]
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1o2r4Qvn9SL7gOa05P-up9tiwnCXPmcnOG3kttL_H0Fk/edit"
REMOTE_WEB_URL = os.environ.get("JOB_DASHBOARD_URL", "https://guillermohern023.github.io/berlin-job-applier/")

from pdf_generator import load_master_profile, generate_master_cv
from tailor import (
    score_and_classify_job,
    select_tailored_content,
    generate_job_application_bundle,
)
from nancy_engine import (
    load_nancy_profile,
    score_nancy_job,
    select_nancy_tailored_content,
    generate_nancy_application_bundle,
    generate_nancy_master_cv,
    scrape_nancy_jobs,
)
from nancy_docx_generator import build_nancy_cv_docx
from sheets_sync import sync_jobs_to_google_sheet


def load_json(path: Path, default):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)



def detect_work_model(title: str, location: str, description: str):
    """
    Returns (label, is_100_onsite, score_bonus)
    """
    text = f"{title} {location} {description}".lower()

    # 1. Strict 100% Onsite check
    strict_onsite = [
        r"100\s*%\s*(präsenz|vor\s*ort|onsite|on-site)",
        r"reine\s*präsenz",
        r"kein\s*home\s*office",
        r"kein\s*homeoffice",
        r"keine\s*remote",
        r"ausschließlich\s*vor\s*ort",
        r"ausschließlich\s*in\s*präsenz",
        r"vollständig\s*vor\s*ort",
        r"nicht\s*remote",
        r"reine\s*vor-ort",
        r"vor-ort-präsenz",
        r"ohne\s*homeoffice",
        r"feste\s*präsenz\s*vor\s*ort",
        r"tägliche\s*präsenz",
        r"keine\s*home-office",
    ]
    for p in strict_onsite:
        if re.search(p, text):
            return ("100% Vor Ort", True, -35)

    front_desk = [r"rezeption", r"front\s*desk", r"empfangsmitarbeiter", r"empfangskraft"]
    for p in front_desk:
        if re.search(p, title.lower()):
            return ("100% Vor Ort (Empfang)", True, -25)

    # 2. Remote check
    remote_pat = [
        r"100\s*%\s*remote",
        r"vollständig\s*remote",
        r"fully\s*remote",
        r"remote\s*first",
        r"deutschlandweit\s*remote",
        r"100\s*%\s*homeoffice",
        r"100\s*%\s*home\s*office",
    ]
    for p in remote_pat:
        if re.search(p, text):
            return ("100% Remote", False, 15)

    # 3. Hybrid check
    hybrid_pat = [
        r"hybrid",
        r"home\s*office",
        r"homeoffice",
        r"mobiles\s*arbeiten",
        r"mobile\s*office",
        r"remote\s*anteil",
        r"flexibles\s*arbeiten",
        r"von\s*zu\s*hause",
        r"work\s*from\s*home",
        r"telearbeit",
        r"remote-option",
        r"home-office",
    ]
    for p in hybrid_pat:
        if re.search(p, text):
            return ("Hybrid (Home Office)", False, 10)

    return ("Flexibles Office", False, 0)


def prune_and_refresh_job_ages(jobs, max_days=10):
    now = datetime.now().date()
    fresh_jobs = []
    pruned_count = 0
    for j in jobs:
        # Require direct apply URL - if there's no real apply link, exclude the job completely
        raw_url = str(j.get("job_url") or "").strip()
        if not raw_url or raw_url.lower() in ["nan", "none", "null", ""] or not (raw_url.startswith("http://") or raw_url.startswith("https://")) or "google.com/search" in raw_url:
            pruned_count += 1
            continue

        wm_label, is_100_onsite, _ = detect_work_model(j.get("title", ""), j.get("location", ""), j.get("description", ""))
        j["work_model"] = wm_label
        j["is_100_onsite"] = is_100_onsite

        dp = j.get("date_posted")
        diff = 99
        if dp:
            try:
                dt = datetime.strptime(str(dp).strip(), "%Y-%m-%d").date()
                diff = max(0, (now - dt).days)
            except Exception:
                diff = j.get("days_ago", 99)
        else:
            diff = j.get("days_ago", 99)

        j["days_ago"] = diff
        if diff == 0:
            j["posted_ago"] = f"🔥 Today ({dp or now.strftime('%Y-%m-%d')})"
        elif diff == 1:
            j["posted_ago"] = f"🔥 1 day ago ({dp})"
        elif diff <= 3:
            j["posted_ago"] = f"⚡ {diff} days ago ({dp})"
        else:
            j["posted_ago"] = f"{diff} days ago ({dp})"

        if diff <= max_days:
            fresh_jobs.append(j)
        else:
            pruned_count += 1

    return fresh_jobs, pruned_count


def run_fresh_scrape_if_requested(do_scrape: bool):
    g_jobs = load_json(DATA_DIR / "jobs_db.json", [])
    n_jobs = load_json(DATA_DIR / "nancy_jobs_db.json", [])

    if do_scrape:
        print("[1/5] Running live LinkedIn & Indeed scrape for Guillermo & Nancy...")
        from scraper import run_job_scrape
        try:
            res_g = run_job_scrape(
                search_terms=[
                    "Working Student Project Management",
                    "Working Student Product Management",
                    "Working Student Operations AI",
                    "Werkstudent IT Projektmanagement",
                    "Working Student Business Analyst",
                    "Werkstudent Data Analytics Reporting",
                ],
                location="Berlin, Germany",
                results_wanted=15,
                hours_old=168,
            )
            g_jobs = load_json(DATA_DIR / "jobs_db.json", g_jobs)
            print(f"  -> Guillermo scrape complete (+{res_g.get('added_count', 0)} new roles, {len(g_jobs)} total).")
        except Exception as e:
            print(f"  -> Warning during Guillermo scrape: {e}")

        try:
            res_n = scrape_nancy_jobs(
                search_terms=[
                    "Werkstudent Office Management",
                    "Werkstudent Teamassistenz",
                    "Werkstudent Assistenz",
                    "Werkstudent Backoffice",
                    "Office Manager Teilzeit",
                    "Working Student Office Management",
                    "Working Student Team Assistant",
                    "Werkstudent Verwaltung",
                    "Werkstudent HR Assistenz",
                    "Werkstudent Event Organisation",
                ],
                location="Berlin, Germany",
                results_wanted=15,
                hours_old=168,
            )
            n_jobs = load_json(DATA_DIR / "nancy_jobs_db.json", n_jobs)
            print(f"  -> Nancy scrape complete (+{res_n.get('added_count', 0)} new roles, {len(n_jobs)} total).")
        except Exception as e:
            print(f"  -> Warning during Nancy scrape: {e}")

    # Enforce strict freshness policy: prune anything older than 1.5 weeks (10 days)
    g_jobs, g_pruned = prune_and_refresh_job_ages(g_jobs, max_days=10)
    n_jobs, n_pruned = prune_and_refresh_job_ages(n_jobs, max_days=10)
    print(f"  -> Job Lifecycle Audit: Pruned {g_pruned} stale Guillermo jobs and {n_pruned} stale Nancy jobs (>1.5 weeks / 10 days old).")
    print(f"  -> Active Fresh Jobs: {len(g_jobs)} for Guillermo, {len(n_jobs)} for Nancy.")
    save_json(DATA_DIR / "jobs_db.json", g_jobs)
    save_json(DATA_DIR / "nancy_jobs_db.json", n_jobs)

    return g_jobs, n_jobs


def ensure_top_jobs_tailored(g_jobs, n_jobs):
    print("[2/5] Ensuring Master CVs (PDF + Word) and Top Matches have Tailored 1-Page Bundles...")
    g_profile = load_master_profile()
    n_profile = load_nancy_profile()

    generate_master_cv()
    generate_nancy_master_cv()
    build_nancy_cv_docx(n_profile, OUTPUT_DIR / "Nancy_Schuetze_Lebenslauf_Master.docx")

    # Auto-tailor top 8 Guillermo jobs if not yet tailored
    g_tailored_count = 0
    for j in g_jobs:
        if j.get("cv_url"):
            g_tailored_count += 1
            continue
        if g_tailored_count < 8 and j.get("match_score", 0) >= 75:
            bundle = generate_job_application_bundle(j)
            j["cv_pdf"] = bundle.get("cv_pdf", "")
            j["cover_letter_pdf"] = bundle.get("cover_letter_pdf", "")
            j["cv_url"] = bundle["cv_url"]
            j["cover_letter_url"] = bundle["cover_letter_url"]
            if j.get("status") == "New":
                j["status"] = "Ready to Apply"
            g_tailored_count += 1

    # Also pre-attach tailored preview text for every job so static GitHub Pages mode can preview Cover Letters
    for j in g_jobs:
        t = select_tailored_content(j, g_profile)
        j["tailored_preview"] = {
            "selected_bullets": j.get("selected_bullets") or t.get("selected_bullets", []),
            "cover_letter_paragraphs": j.get("cover_letter_paragraphs") or t.get("cover_letter_paragraphs", []),
        }

    # Auto-tailor top 6 Nancy jobs if not yet tailored
    n_tailored_count = 0
    for j in n_jobs:
        if j.get("cv_url"):
            n_tailored_count += 1
            continue
        if n_tailored_count < 6 and j.get("match_score", 0) >= 75:
            bundle = generate_nancy_application_bundle(j)
            j["cv_pdf"] = bundle.get("cv_pdf", "")
            j["cover_letter_pdf"] = bundle.get("cover_letter_pdf", "")
            j["cv_url"] = bundle["cv_url"]
            j["cover_letter_url"] = bundle["cover_letter_url"]
            if j.get("status") == "New":
                j["status"] = "Ready to Apply"
            n_tailored_count += 1

    for j in n_jobs:
        t = select_nancy_tailored_content(j, n_profile)
        j["tailored_preview"] = {
            "selected_bullets": [],
            "cover_letter_paragraphs": j.get("cover_letter_paragraphs") or t.get("cover_letter_paragraphs", []),
        }

    save_json(DATA_DIR / "jobs_db.json", g_jobs)
    save_json(DATA_DIR / "nancy_jobs_db.json", n_jobs)
    return g_jobs, n_jobs


def build_independent_website(g_jobs, n_jobs):
    """
    Builds a 100% independent static website inside docs/ (ready for GitHub Pages, Netlify, Vercel)
    and standalone dashboard.html with all jobs, tailored previews, and PDF/DOCX files bundled.
    """
    print("[3/5] Building independent static website (docs/index.html & dashboard.html)...")
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    docs_files_dir = DOCS_DIR / "files"
    if docs_files_dir.exists():
        shutil.rmtree(docs_files_dir)
    shutil.copytree(OUTPUT_DIR, docs_files_dir)

    # Also ensure local /files symlink/copy works when opening dashboard.html from BASE_DIR
    local_files_dir = BASE_DIR / "files"
    if local_files_dir.exists():
        shutil.rmtree(local_files_dir)
    shutil.copytree(OUTPUT_DIR, local_files_dir)

    g_profile = load_master_profile()
    all_auto1_bullets = g_profile.get("auto1_bullet_pool", [])

    static_state = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "spreadsheet_url": GOOGLE_SHEET_URL,
        "all_auto1_bullets": all_auto1_bullets,
        "jobs": g_jobs,
        "nancy_jobs": n_jobs,
    }

    if (STATIC_DIR / "docx.umd.js").exists():
        shutil.copy2(STATIC_DIR / "docx.umd.js", DOCS_DIR / "docx.umd.js")
    nancy_assets_src = DATA_DIR / "nancy_assets"
    if nancy_assets_src.exists():
        for target_base in [OUTPUT_DIR, DOCS_DIR / "files", BASE_DIR / "files"]:
            target_assets = target_base / "nancy_assets"
            if target_assets.exists():
                shutil.rmtree(target_assets)
            shutil.copytree(nancy_assets_src, target_assets)

    template_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    safe_json = json.dumps(static_state, ensure_ascii=False).replace("</", "<\\/")
    state_script = f"<script>window.STATIC_STATE = {safe_json};</script>"
    standalone_html = template_html.replace("<!-- STATIC_STATE_INJECTION_POINT -->", state_script)

    (DOCS_DIR / "index.html").write_text(standalone_html, encoding="utf-8")
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
    DASHBOARD_HTML_PATH.write_text(standalone_html, encoding="utf-8")
    try:
        ARTIFACT_DASHBOARD_PATH.write_text(standalone_html, encoding="utf-8")
    except Exception:
        pass
    print(f"  -> Independent site built at: {DOCS_DIR / 'index.html'} and {DASHBOARD_HTML_PATH}")


def build_job_cards_email_html(jobs_list, is_nancy=False, limit=6):
    rows_html = []
    # 1. Filter out jobs that the user is not interested in, archived, or already applied to
    active_jobs = [
        j for j in jobs_list
        if str(j.get("status", "")).lower() not in ["applied", "not interested", "archived", "rejected"]
        and not (is_nancy and j.get("is_100_onsite"))
    ]

    # 2. Sort by Freshness first (days_ago 0 = Today, 1 = Yesterday), then by match_score
    def sort_key(j):
        da = j.get("days_ago", 99)
        tier = 0 if da <= 1 else (1 if da <= 3 else 2)
        score = -(j.get("match_score", 0))
        return (tier, score, da)

    sorted_jobs = sorted(active_jobs, key=sort_key)
    top_jobs = sorted_jobs[:limit]

    accent = "#db2777" if is_nancy else "#4f46e5"
    badge_bg = "#fdf2f8" if is_nancy else "#eef2ff"
    badge_fg = "#9d174d" if is_nancy else "#3730a3"

    for idx, j in enumerate(top_jobs, 1):
        days_ago = j.get("days_ago", 99)
        recency_badge = ""
        if days_ago == 0:
            recency_badge = '<span style="display: inline-block; background-color: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; font-size: 11px; font-weight: 800; padding: 2px 8px; border-radius: 6px; margin-right: 6px;">🔥 NEU HEUTE</span>'
        elif days_ago == 1:
            recency_badge = '<span style="display: inline-block; background-color: #ffedd5; color: #c2410c; border: 1px solid #fdba74; font-size: 11px; font-weight: 800; padding: 2px 8px; border-radius: 6px; margin-right: 6px;">⚡ NEU GESTERN</span>'
        score = j.get("match_score", 80)
        title = j.get("title", "Working Student Role")
        company = j.get("company", "Berlin Company")
        loc = j.get("location", "Berlin")
        posted = j.get("posted_ago") or j.get("date_posted") or "Recent"
        apps = j.get("applicants_text") or "Direct Portal"
        edited = "✅ CV & CL Edited" if j.get("cv_url") else "⏳ Ready to Tailor"
        if is_nancy and j.get("cv_url"):
            edited = "✅ Lebenslauf & Anschreiben bereit"
        lang_fit = j.get("language_req") or ("📍 Near Zoo" if is_nancy else "🇬🇧 English Friendly")
        url = j.get("job_url", GOOGLE_SHEET_URL)
        why = j.get("why_fits", "")

        rows_html.append(f"""
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid {accent}; border-radius: 10px; margin-bottom: 12px;">
          <tr>
            <td style="padding: 14px 16px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td valign="top" style="padding-right: 10px;">
                    {recency_badge}
                    <span style="display: inline-block; background-color: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; font-size: 11px; font-weight: 800; padding: 2px 8px; border-radius: 6px; margin-right: 6px;">
                      {score}% Match
                    </span>
                    <span style="display: inline-block; background-color: {badge_bg}; color: {badge_fg}; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px; margin-right: 6px;">
                      {edited}
                    </span>
                    <span style="display: inline-block; background-color: #f1f5f9; color: #334155; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 6px;">
                      {lang_fit}
                    </span>
                    <div style="font-size: 15px; font-weight: 800; color: #0f172a; margin: 8px 0 4px 0;">
                      {idx}. {title}
                    </div>
                    <div style="font-size: 12px; font-weight: 600; color: #475569; margin-bottom: 6px;">
                      🏢 {company} &nbsp;•&nbsp; 📍 {loc} &nbsp;•&nbsp; 🕒 {posted} &nbsp;•&nbsp; 👥 {apps}
                    </div>
                    <div style="font-size: 11px; color: #64748b; line-height: 1.4;">
                      {why}
                    </div>
                  </td>
                  <td valign="middle" align="right" width="135" style="min-width: 125px;">
                    <a href="{url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: {accent}; color: #ffffff !important; font-size: 12px; font-weight: 800; text-decoration: none; padding: 10px 14px; border-radius: 8px; text-align: center;">
                      {"⚡ Bewerben ➔" if is_nancy else "⚡ Quick Apply ➔"}
                    </a>
                    <a href="{REMOTE_WEB_URL}#user={'nancy' if is_nancy else 'guillermo'}" target="_blank" rel="noopener noreferrer" style="display: block; margin-top: 6px; font-size: 11px; color: #94a3b8; text-decoration: underline; text-align: center;">
                      ❌ {"Nicht interessiert" if is_nancy else "Not Interested"}
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
        """)
    return "\n".join(rows_html)


def format_daily_job_email(g_jobs, n_jobs, recipients=None):
    target_recipients = recipients or RECIPIENT_EMAILS
    today_str = datetime.now().strftime("%b %d, %Y")
    g_ready = sum(1 for j in g_jobs if j.get("cv_url"))
    n_ready = sum(1 for j in n_jobs if j.get("cv_url"))
    g_fresh = [j for j in g_jobs if (j.get("days_ago") or 99) <= 7 and not ("C1" in (j.get("language_req") or ""))]
    if len(g_fresh) < 5:
        g_fresh = g_jobs[:5]
    n_fresh = [j for j in n_jobs if (j.get("days_ago") or 99) <= 10]
    if len(n_fresh) < 5:
        n_fresh = n_jobs[:5]

    subject = f"🚀 Daily Berlin Job Applier Digest ({today_str}): {len(g_fresh)} Top PM/AI Roles + {len(n_fresh)} Office Mgmt Roles Near Zoo"

    plain_lines = [
        f"=== DAILY BERLIN JOB APPLIER & CV TAILOR DIGEST ({today_str}) ===",
        f"Live Google Sheet (Guillermo & Nancy Tabs): {GOOGLE_SHEET_URL}",
        f"Independent Web Dashboard: {REMOTE_WEB_URL}",
        "",
        f"--- 👨‍💻 GUILLERMO: TOP WORKING STUDENT PM / PRODUCT / AI ROLES ({g_ready} Pre-Tailored PDFs Ready) ---",
    ]
    for idx, j in enumerate(g_fresh[:5], 1):
        plain_lines.append(
            f"{idx}. [{j.get('match_score')}%] {j.get('title')} @ {j.get('company')} ({j.get('location')}) | "
            f"{j.get('posted_ago', 'Recent')} | {j.get('applicants_text', 'Direct')} | Edited: {'YES' if j.get('cv_url') else 'NO'}\n"
            f"   Apply: {j.get('job_url')}"
        )

    plain_lines.append("")
    plain_lines.append(f"--- 👩‍💼 NANCY: TOP OFFICE MANAGEMENT ROLES NEAR ZOOLOGISCHER GARTEN ({n_ready} Pre-Tailored PDFs Ready) ---")
    for idx, j in enumerate(n_fresh[:5], 1):
        plain_lines.append(
            f"{idx}. [{j.get('match_score')}%] {j.get('title')} @ {j.get('company')} ({j.get('location')}) | "
            f"{j.get('posted_ago', 'Recent')} | {j.get('applicants_text', 'Direct')} | Edited: {'YES' if j.get('cv_url') else 'NO'}\n"
            f"   Apply: {j.get('job_url')}"
        )

    plain_text = "\n".join(plain_lines)

    g_cards_html = build_job_cards_email_html(g_fresh, is_nancy=False, limit=5)
    n_cards_html = build_job_cards_email_html(n_fresh, is_nancy=True, limit=5)

    html_email = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f1f5f9; padding: 16px 8px;">
    <tr>
      <td align="center">
        <table width="640" cellpadding="0" cellspacing="0" border="0" style="max-width: 640px; width: 100%; background-color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #cbd5e1;">
          
          <!-- Header -->
          <tr>
            <td style="background-color: #0f172a; padding: 24px 20px; color: #ffffff; text-align: center;">
              <div style="display: inline-block; background-color: #312e81; color: #c7d2fe; border-radius: 20px; padding: 4px 14px; font-size: 11px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 10px;">
                🤖 Automated Daily Berlin Job Applier &amp; CV Tailor
              </div>
              <h1 style="margin: 0 0 6px 0; font-size: 22px; font-weight: 900; color: #ffffff;">
                Guillermo &amp; Nancy — Daily Job Matches
              </h1>
              <p style="margin: 0; color: #94a3b8; font-size: 13px;">
                {today_str} • {len(g_jobs)} Roles Tracked for Guillermo ({g_ready} Tailored) • {len(n_jobs)} Roles Tracked for Nancy ({n_ready} Tailored)
              </p>
            </td>
          </tr>

          <!-- Top Action Bar -->
          <tr>
            <td style="padding: 18px 20px 8px 20px; background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td width="50%" style="padding-right: 6px; padding-bottom: 10px;">
                    <a href="{GOOGLE_SHEET_URL}" target="_blank" rel="noopener noreferrer" style="display: block; background-color: #059669; color: #ffffff !important; font-size: 13px; font-weight: 800; text-decoration: none; padding: 12px 10px; border-radius: 8px; text-align: center;">
                      📗 Open Live Google Sheet (2 Tabs) ➔
                    </a>
                  </td>
                  <td width="50%" style="padding-left: 6px; padding-bottom: 10px;">
                    <a href="{REMOTE_WEB_URL}" target="_blank" rel="noopener noreferrer" style="display: block; background-color: #4f46e5; color: #ffffff !important; font-size: 13px; font-weight: 800; text-decoration: none; padding: 12px 10px; border-radius: 8px; text-align: center;">
                      🌐 Open Web App Dashboard ➔
                    </a>
                  </td>
                </tr>
              </table>
              <div style="font-size: 11px; color: #475569; text-align: center; padding-bottom: 8px;">
                📎 <strong>Attached to this email:</strong> Clean 1-Page Master CVs (PDF) and your #1 Top Tailored CV &amp; Cover Letter bundles!
              </div>
            </td>
          </tr>

          <!-- Guillermo Section -->
          <tr>
            <td style="padding: 20px 20px 8px 20px;">
              <div style="font-size: 16px; font-weight: 900; color: #1e1b4b; margin-bottom: 4px;">
                👨‍💻 Guillermo's Top Working Student Matches (Berlin &amp; Remote)
              </div>
              <div style="font-size: 12px; color: #64748b; margin-bottom: 14px;">
                Filtered for English-friendly Project Management, Product Management, AI Operations &amp; Business Ops roles.
              </div>
              {g_cards_html}
            </td>
          </tr>

          <!-- Nancy Section -->
          <tr>
            <td style="padding: 12px 20px 20px 20px;">
              <div style="border-top: 2px solid #f1f5f9; padding-top: 18px; font-size: 16px; font-weight: 900; color: #831843; margin-bottom: 4px;">
                👩‍💼 Nancy's Top Office Management Matches (Near Zoologischer Garten / City West)
              </div>
              <div style="font-size: 12px; color: #64748b; margin-bottom: 14px;">
                Prioritized for Charlottenburg, Savignyplatz, Kurfürstendamm &amp; Zoologischer Garten (right next to TU Berlin).
              </div>
              {n_cards_html}
              <div style="text-align: center; margin-top: 12px;">
                <a href="{REMOTE_WEB_URL}/?user=nancy" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #fce7f3; color: #9d174d !important; border: 1px solid #f9a8d4; font-size: 12px; font-weight: 800; text-decoration: none; padding: 10px 18px; border-radius: 8px;">
                  👩‍💼 Open Nancy's Direct Web Tab ➔
                </a>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 14px 20px; text-align: center; color: #94a3b8; font-size: 11px; line-height: 1.6;">
              Delivered automatically to {', '.join(target_recipients)} • Antigravity Job Applier Engine<br>
              <a href="{GOOGLE_SHEET_URL}" style="color: #059669; text-decoration: none; font-weight: 700;">Google Sheet Tracker</a> &nbsp;|&nbsp;
              <a href="{REMOTE_WEB_URL}" style="color: #4f46e5; text-decoration: none; font-weight: 700;">Live Web Dashboard</a>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return subject, plain_text, html_email


def send_job_digest_email(subject, plain_text, html_email, g_jobs, n_jobs, recipients=None):
    target_recipients = recipients or RECIPIENT_EMAILS
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    sender_email = os.environ.get("SENDER_EMAIL", smtp_user or "job-applier@antigravity.local")

    env_path = Path.home() / ".env"
    if env_path.exists() and (not smtp_user or not smtp_pass):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    k, v = k.strip(), v.strip().strip("\"'")
                    if k == "SMTP_HOST" and not smtp_host:
                        smtp_host = v
                    if k == "SMTP_USER" and not smtp_user:
                        smtp_user = v
                    if k == "SMTP_PASS" and not smtp_pass:
                        smtp_pass = v.replace(" ", "")
                    if k == "SENDER_EMAIL" and not sender_email:
                        sender_email = v

    recipients_str = ", ".join(target_recipients)
    REPORT_TXT_PATH.write_text(f"Subject: {subject}\nTo: {recipients_str}\n\n{plain_text}", encoding="utf-8")
    print(f"[5/5] Saved plain-text report to {REPORT_TXT_PATH}")

    if not (smtp_host and smtp_user and smtp_pass):
        print("[WARN] SMTP credentials not found in ~/.env. Skipping outbound email.")
        return False

    try:
        msg = MIMEMultipart("mixed")
        msg["From"] = sender_email
        msg["To"] = recipients_str
        msg["Subject"] = subject

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(plain_text, "plain", "utf-8"))
        alt.attach(MIMEText(html_email, "html", "utf-8"))
        msg.attach(alt)

        # Attach Master PDFs + #1 Top Tailored CV & Cover Letter for each
        attachments = [
            OUTPUT_DIR / "Guillermo_Hernandez_CV_Master.pdf",
            OUTPUT_DIR / "Nancy_Schuetze_Lebenslauf_Master.pdf",
        ]
        # Add #1 tailored job PDF for Guillermo & Nancy if available
        for j in g_jobs:
            p_cv = j.get("cv_pdf") or j.get("cv_pdf_path")
            p_cl = j.get("cover_letter_pdf") or j.get("cover_letter_pdf_path")
            if p_cv and Path(p_cv).exists():
                attachments.append(Path(p_cv))
                if p_cl and Path(p_cl).exists():
                    attachments.append(Path(p_cl))
                break
        for j in n_jobs:
            p_cv = j.get("cv_pdf") or j.get("cv_pdf_path")
            p_cl = j.get("cover_letter_pdf") or j.get("cover_letter_pdf_path")
            if p_cv and Path(p_cv).exists():
                attachments.append(Path(p_cv))
                if p_cl and Path(p_cl).exists():
                    attachments.append(Path(p_cl))
                break

        for file_path in attachments:
            if file_path.exists():
                with open(file_path, "rb") as fp:
                    part = MIMEApplication(fp.read(), Name=file_path.name)
                part["Content-Disposition"] = f'attachment; filename="{file_path.name}"'
                msg.attach(part)

        print(f"  -> Dispatching HTML email + {len(attachments)} CV/CL attachments via {smtp_host}:{smtp_port} to {recipients_str}...")
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(sender_email, target_recipients, msg.as_string())
        server.quit()
        print(f"[SUCCESS] Rich HTML Job Digest + CV attachments sent to {recipients_str}!")
        return True
    except Exception as e:
        print(f"[ERROR] SMTP send failed: {e}")
        return False


def main():
    do_scrape = ("--no-scrape" not in sys.argv)
    no_email = ("--no-email" in sys.argv)
    custom_recipients = None

    for arg in sys.argv:
        if arg == "--only-guillermo":
            custom_recipients = ["guillejhl@gmail.com"]
        elif arg == "--only-nancy":
            custom_recipients = ["schuetzenc@gmail.com"]
        elif arg.startswith("--recipient="):
            custom_recipients = [arg.split("=", 1)[1].strip()]

    g_jobs, n_jobs = run_fresh_scrape_if_requested(do_scrape=do_scrape)
    g_jobs, n_jobs = ensure_top_jobs_tailored(g_jobs, n_jobs)
    build_independent_website(g_jobs, n_jobs)

    print("[4/5] Syncing both tabs to Google Sheets...")
    try:
        res = sync_jobs_to_google_sheet(g_jobs, n_jobs)
        print(f"  -> Google Sheets synced: {res.get('rows_written')} total rows ({res.get('spreadsheet_url')}).")
        # Save back any preserved statuses from Google Sheets to disk
        save_json(DATA_DIR / "jobs_db.json", g_jobs)
        save_json(DATA_DIR / "nancy_jobs_db.json", n_jobs)
    except Exception as e:
        print(f"  -> Google Sheets sync warning: {e}")

    if not no_email:
        subject, plain_text, html_email = format_daily_job_email(g_jobs, n_jobs, recipients=custom_recipients)
        send_job_digest_email(subject, plain_text, html_email, g_jobs, n_jobs, recipients=custom_recipients)


if __name__ == "__main__":
    main()
