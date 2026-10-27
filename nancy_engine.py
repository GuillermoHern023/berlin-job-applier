import json
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

from pdf_generator import render_html_to_pdf, OUTPUT_DIR, DATA_DIR

NANCY_PROFILE_PATH = DATA_DIR / "nancy_profile.json"
NANCY_JOBS_DB_PATH = DATA_DIR / "nancy_jobs_db.json"

NANCY_DEFAULT_QUERIES = [
    {"search_term": "Werkstudent Office Management", "location": "Berlin, Germany"},
    {"search_term": "Werkstudent Teamassistenz", "location": "Berlin, Germany"},
    {"search_term": "Werkstudent Assistenz", "location": "Berlin, Germany"},
    {"search_term": "Werkstudent Backoffice", "location": "Berlin, Germany"},
    {"search_term": "Office Manager Teilzeit", "location": "Berlin, Germany"},
    {"search_term": "Working Student Office Management", "location": "Berlin, Germany"},
    {"search_term": "Working Student Team Assistant", "location": "Berlin, Germany"},
    {"search_term": "Werkstudent Verwaltung", "location": "Berlin, Germany"},
    {"search_term": "Werkstudent HR Assistenz", "location": "Berlin, Germany"},
    {"search_term": "Werkstudent Event Organisation", "location": "Berlin, Germany"},
    {"search_term": "Werkstudent Sekretariat", "location": "Berlin, Germany"},
    {"search_term": "Office Assistant Berlin", "location": "Berlin, Germany"},
]


def load_nancy_profile() -> Dict[str, Any]:
    with open(NANCY_PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_nancy_jobs_db() -> List[Dict[str, Any]]:
    if not NANCY_JOBS_DB_PATH.exists():
        return []
    try:
        with open(NANCY_JOBS_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_nancy_jobs_db(jobs: List[Dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(NANCY_JOBS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)


def build_nancy_cv_html(profile: Dict[str, Any], custom_headline: Optional[str] = None) -> str:
    p = profile["personal_info"]
    headline = custom_headline or p["role_headline_de"]

    photo_uri = (DATA_DIR / p["photo_path"]).resolve().as_uri()
    sig_uri = (DATA_DIR / p["signature_path"]).resolve().as_uri()
    today_str = datetime.now().strftime("%d.%m.%Y")

    exp_html = ""
    for exp in profile["experience_de"]:
        bullets = exp.get("bullets", [])
        if bullets:
            bullets_html = "\n".join(f"<li>{b}</li>" for b in bullets)
            b_list_html = f'<ul class="bullet-list">{bullets_html}</ul>'
        else:
            b_list_html = ""
        exp_html += f"""
        <div class="row-item">
          <div class="left-col">{exp["dates"]}</div>
          <div class="right-col">
            <div class="exp-header">
              <span class="exp-title">{exp["title"]}</span>
              <span class="exp-company"> | <strong>{exp["company"]}</strong>, {exp["location"]}</span>
            </div>
            {b_list_html}
          </div>
        </div>
        """

    edu_html = ""
    for edu in profile["education_de"]:
        details_div = f'<div class="edu-details">{edu["details"]}</div>' if edu.get("details") else ""
        edu_html += f"""
        <div class="row-item edu-row">
          <div class="left-col">{edu["dates"]}</div>
          <div class="right-col">
            <div class="edu-degree"><strong>{edu["degree"]}</strong> | {edu["institution"]}</div>
            {details_div}
          </div>
        </div>
        """

    lang_items = " &nbsp;&bull;&nbsp; ".join(
        f"<strong>{l['language']}:</strong> {l['level']}" for l in profile["languages_de"]
    )

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Lebenslauf - {p["full_name"]}</title>
<style>
  @page {{
    size: A4;
    margin: 11mm 12mm 11mm 12mm;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: "Segoe UI", Calibri, Arial, sans-serif;
    font-size: 8.25pt;
    line-height: 1.22;
    color: #1e293b;
    background: #fff;
  }}
  .header-container {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid #1e3a8a;
    padding-bottom: 5px;
    margin-bottom: 5px;
  }}
  .header-info {{
    flex: 1;
    padding-right: 14px;
  }}
  .header-info h1 {{
    font-size: 16.5pt;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: 0.3px;
    margin-bottom: 2px;
  }}
  .header-info .motto {{
    font-size: 9.2pt;
    font-weight: 700;
    color: #1e3a8a;
    margin-bottom: 2px;
  }}
  .header-info .about-me {{
    font-size: 8.15pt;
    color: #475569;
    margin-bottom: 4px;
    line-height: 1.22;
  }}
  .contact-grid {{
    display: grid;
    grid-template-columns: auto auto;
    gap: 1.5px 16px;
    font-size: 8.2pt;
    color: #334155;
  }}
  .contact-grid a {{
    color: #1e3a8a;
    text-decoration: underline;
  }}
  .photo-box img {{
    width: 76px;
    height: 96px;
    object-fit: cover;
    border-radius: 5px;
    border: 1.5px solid #cbd5e1;
  }}
  .section-block {{
    margin-bottom: 4px;
  }}
  .section-title {{
    font-size: 8.75pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.9px;
    color: #1e3a8a;
    border-bottom: 1.2px solid #cbd5e1;
    padding-bottom: 2px;
    margin-bottom: 4px;
  }}
  .row-item {{
    display: flex;
    margin-bottom: 3.5px;
  }}
  .row-item:last-child {{
    margin-bottom: 0;
  }}
  .left-col {{
    width: 14.5%;
    font-size: 8.1pt;
    font-weight: 600;
    color: #475569;
    padding-right: 8px;
    flex-shrink: 0;
  }}
  .right-col {{
    width: 85.5%;
  }}
  .exp-header {{
    margin-bottom: 1px;
  }}
  .exp-title {{
    font-weight: 700;
    font-size: 8.95pt;
    color: #0f172a;
  }}
  .exp-company {{
    font-size: 8.55pt;
    color: #334155;
  }}
  ul.bullet-list {{
    padding-left: 14px;
    margin-top: 1px;
  }}
  ul.bullet-list li {{
    margin-bottom: 1px;
    font-size: 8.3pt;
  }}
  .edu-row {{
    margin-bottom: 4px;
  }}
  .edu-degree {{
    font-size: 8.7pt;
    color: #0f172a;
  }}
  .edu-details {{
    font-size: 8.15pt;
    color: #475569;
    margin-top: 0.5px;
  }}
  .skills-box p {{
    margin-bottom: 2.5px;
    font-size: 8.25pt;
    line-height: 1.27;
  }}
  .skills-box p:last-child {{
    margin-bottom: 0;
  }}
  .footer-sig {{
    margin-top: 6px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    padding-top: 4px;
    border-top: 1px solid #cbd5e1;
  }}
  .sig-block {{
    text-align: center;
  }}
  .sig-block img {{
    height: 28px;
    display: block;
    margin: 0 auto -2px auto;
  }}
  .sig-line {{
    font-size: 8.15pt;
    color: #475569;
    border-top: 1px solid #94a3b8;
    padding-top: 2px;
    min-width: 165px;
  }}
</style>
</head>
<body>
  <div>
    <div class="header-container">
      <div class="header-info">
        <h1>{p["full_name"]}</h1>
        <div class="motto">{p.get("motto_keywords", headline)}</div>
        <div class="about-me">{p.get("about_me_de", "")}</div>
        <div class="contact-grid">
          <span><strong>Adresse:</strong> {p["address"]}</span>
          <span><strong>Mobil:</strong> {p["phone"]}</span>
          <span><strong>E-Mail:</strong> {p["email"]}</span>
          <span><strong>Geboren:</strong> {p.get("birth_info_de", "17.08.2001 in Berlin")}</span>
          <span style="grid-column: span 2;"><strong>LinkedIn:</strong> <a href="{p['linkedin_url']}" target="_blank">{p['linkedin_label']}</a></span>
        </div>
      </div>
      <div class="photo-box">
        <img src="{photo_uri}" alt="Bewerbungsfoto {p['short_name']}" />
      </div>
    </div>

    <div class="section-block">
      <div class="section-title">Berufserfahrung</div>
      {exp_html}
    </div>

    <div class="section-block">
      <div class="section-title">Bildungsweg</div>
      {edu_html}
    </div>

    <div class="section-block" style="margin-bottom: 0;">
      <div class="section-title">Fachkompetenzen &amp; IT-Kenntnisse</div>
      <div class="skills-box">
        <p><strong>Office &amp; Organisation:</strong> {profile["skills_de"]["office_management"]}</p>
        <p><strong>Software &amp; IT:</strong> {profile["skills_de"]["it_software"]}</p>
        <p><strong>Film &amp; Audio:</strong> {profile["skills_de"].get("film_audio", "DaVinci Resolve · Wondershare Filmora · Adobe Audition CC 2019")}</p>
        <p><strong>Sprachen:</strong> {lang_items}</p>
        <p><strong>Nachweise &amp; Mobilität:</strong> {profile["skills_de"]["certificates"]}</p>
      </div>
    </div>
  </div>


</body>
</html>
"""


def build_nancy_cover_letter_html(
    profile: Dict[str, Any],
    company: str,
    job_title: str,
    location: str,
    paragraphs: List[str],
    date_str: Optional[str] = None,
) -> str:
    p = profile["personal_info"]
    sig_uri = (DATA_DIR / p["signature_path"]).resolve().as_uri()
    if not date_str:
        date_str = datetime.now().strftime("%d.%m.%Y")

    body_html = "\n".join(f"<p>{para}</p>" for para in paragraphs)

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Anschreiben - {p["short_name"]} - {company}</title>
<style>
  @page {{
    size: A4;
    margin: 18mm 20mm 18mm 20mm;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: "Segoe UI", Calibri, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.48;
    color: #1e293b;
    background: #fff;
  }}
  .top-header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    border-bottom: 2px solid #1e3a8a;
    padding-bottom: 8px;
    margin-bottom: 18px;
  }}
  .sender-name {{
    font-size: 15pt;
    font-weight: 700;
    color: #0f172a;
  }}
  .sender-sub {{
    font-size: 9.5pt;
    color: #1e3a8a;
    font-weight: 600;
  }}
  .sender-contact {{
    text-align: right;
    font-size: 9.2pt;
    line-height: 1.35;
    color: #334155;
  }}
  .meta-row {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 22px;
    font-size: 10pt;
  }}
  .subject-line {{
    font-size: 11pt;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 16px;
  }}
  .salutation {{
    margin-bottom: 12px;
  }}
  .letter-body p {{
    margin-bottom: 12px;
    text-align: left;
  }}
  .sign-off {{
    margin-top: 20px;
  }}
  .sign-off img {{
    height: 38px;
    display: block;
    margin: 4px 0;
  }}
</style>
</head>
<body>
  <div class="top-header">
    <div>
      <div class="sender-name">{p["full_name"]}</div>
      <div class="sender-sub">Office Management &amp; Kaufmännische Projektsteuerung</div>
    </div>
    <div class="sender-contact">
      <div>{p["address"]}</div>
      <div>Mobil: {p["phone"]}</div>
      <div>E-Mail: {p["email"]}</div>
    </div>
  </div>

  <div class="meta-row">
    <div>
      <div><strong>{company}</strong></div>
      <div>Personalabteilung / Recruiting-Team</div>
      <div>{location}</div>
    </div>
    <div>Berlin, den {date_str}</div>
  </div>

  <div class="subject-line">Bewerbung als {job_title}</div>

  <div class="salutation">Sehr geehrte Damen und Herren,</div>

  <div class="letter-body">
    {body_html}
  </div>

  <div class="sign-off">
    <p>Mit freundlichen Grüßen</p>
    <img src="{sig_uri}" alt="Unterschrift {p['short_name']}" />
    <p><strong>{p["full_name"]}</strong></p>
  </div>
</body>
</html>
"""


def detect_zoo_proximity(title: str, company: str, location: str, description: str) -> Tuple[str, int]:
    text = f"{title} {company} {location} {description}".lower()

    tier1_zoo = [
        "zoologischer garten", "charlottenburg", "kurfürstendamm", "ku'damm", "kudamm",
        "ernst-reuter-platz", "savignyplatz", "kantstraße", "kantstr", "hardenbergstr",
        "tauentzien", "wittenbergplatz", "city west", "steinplatz", "uhlandstr",
        "10623", "10625", "10627", "10629", "10719", "10787", "10789", "10587",
    ]
    for loc in tier1_zoo:
        if loc in text:
            return ("📍 Top-Lage: Direkt am Zoo / Charlottenburg / City West", +22)

    tier2_near = [
        "tiergarten", "wilmersdorf", "schöneberg", "halensee", "potsdamer platz",
        "mitte", "moabit", "hauptbahnhof", "nollendorfplatz", "spittelmarkt",
        "10785", "10715", "10717", "10117", "10557",
    ]
    for loc in tier2_near:
        if loc in text:
            return ("🚇 Schnell ab Zoo erreichbar (U2/U9/S-Bahn)", +12)

    return ("📍 Berlin (Standort prüfen)", +4)


def score_nancy_job(job: Dict[str, Any]) -> Dict[str, Any]:
    title = str(job.get("title") or "")
    company = str(job.get("company") or "")
    location = str(job.get("location") or "Berlin")
    description = str(job.get("description") or "")

    title_l = title.lower()
    text_l = f"{title} {description}".lower()

    score = 55
    matched = []

    high_value_terms = [
        ("office manage", 18, "Office Management"),
        ("teamassist", 16, "Teamassistenz"),
        ("backoffice", 15, "Backoffice"),
        ("back office", 15, "Back Office"),
        ("kanzlei", 16, "Kanzleiorganisation"),
        ("sekretariat", 15, "Sekretariat"),
        ("empfang", 12, "Empfang & Front Office"),
        ("front office", 12, "Front Office"),
        ("assistenz", 12, "Assistenz"),
        ("verwaltung", 10, "Verwaltung"),
        ("rechnung", 8, "Rechnungserstellung"),
        ("buchhaltung", 8, "Vorbereitende Buchhaltung"),
        ("onboarding", 8, "Onboarding & Personal"),
        ("event", 8, "Event- & Terminplanung"),
    ]
    for term, pts, label in high_value_terms:
        if term in title_l:
            score += pts
            if label not in matched:
                matched.append(label)
        elif term in text_l:
            score += max(4, pts // 3)
            if label not in matched:
                matched.append(label)

    # Boost Working Student / Part-Time
    if any(w in title_l for w in ["werkstudent", "working student", "student", "teilzeit", "part-time", "minijob", "20h", "15-20"]):
        score += 15
        matched.insert(0, "Werkstudent / Teilzeit")
    elif any(w in text_l for w in ["werkstudent", "teilzeit", "working student"]):
        score += 8

    # Proximity to Zoologischer Garten
    prox_label, prox_pts = detect_zoo_proximity(title, company, location, description)
    score += prox_pts

    final_score = max(25, min(99, score))
    kw_str = ", ".join(matched[:5]) if matched else "Office Management, Organisation, Kommunikation"

    return {
        "category_label": "Office Management & Assistenz",
        "match_score": final_score,
        "language_req": prox_label,
        "extracted_pay": job.get("salary") or "Siehe Ausschreibung",
        "why_fits": f"Passt ideal zu SERS Kanzlei- & zett.events Erfahrung ({kw_str}).",
    }


def select_nancy_tailored_content(job: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    company = str(job.get("company") or "Ihrem Unternehmen").strip()
    job_title = str(job.get("title") or "Werkstudentin Office Management (m/w/d)").strip()
    analysis = score_nancy_job(job)

    paragraphs = [
        (
            f"ein reibungslos organisiertes Office bildet das Rückgrat jedes erfolgreichen Teams. "
            f"Da ich bereits als Office Managerin in einer Berliner Rechtsanwaltskanzlei sowie als Junior Projektleiterin "
            f"in einer Eventagentur umfassende Verantwortung für Sekretariat, Backoffice und kaufmännische Abläufe übernommen habe, "
            f"bewerbe ich mich mit großer Begeisterung bei <strong>{company}</strong> als <strong>{job_title}</strong>."
        ),
        (
            f"In meiner letzten Position als Office Managerin bei der SERS Rechtsanwaltsgesellschaft mbH habe ich den gesamten "
            f"Kanzlei- und Sekretariatsbetrieb eigenverantwortlich koordiniert. Dazu gehörten die professionelle Kommunikation "
            f"mit Mandanten und Behörden auf Deutsch (Muttersprache) und Englisch (C2), die strukturierte Dokumenten- und Fristenorganisation "
            f"sowie die vorbereitende Buchhaltung und Rechnungserstellung. Zuvor konnte ich als Junior Projektleiterin bei zett.events "
            f"sowie während meines dualen B.A.-Studiums in Business Administration (mit Accor Hotels) fundierte Erfahrung in der "
            f"Personal- und Einsatzplanung, im Onboarding neuer Mitarbeitender und in der Angebots- und Vertragsverwaltung sammeln."
        ),
        (
            f"Aktuell absolviere ich mein Studium an der Technischen Universität Berlin direkt am Standort Zoologischer Garten / Charlottenburg. "
            f"Dadurch verbinde ich kaufmännische Praxiserfahrung und ausgeprägte Serviceorientierung mit hoher digitaler Affinität "
            f"(MS Office 365, digitale Dokumentenverwaltung, Prozessoptimierung) und bin örtlich sowie zeitlich besonders flexibel einsetzbar. "
            f"Kolleginnen, Kollegen und Vorgesetzte schätzen an mir vor allem meine strukturierte, proaktive Arbeitsweise und mein souveränes Auftreten am Empfang und Telefon."
        ),
        (
            f"Gerne möchte ich Ihr Team bei <strong>{company}</strong> tatkräftig entlasten und für perfekt strukturierte Büroabläufe sorgen. "
            f"Über die Einladung zu einem persönlichen Kennenlernen freue ich mich sehr."
        ),
    ]

    return {
        "analysis": analysis,
        "selected_bullets": [b for exp in profile["experience_de"][:2] for b in exp["bullets"]],
        "cover_letter_paragraphs": paragraphs,
    }


def generate_nancy_master_cv() -> Path:
    from nancy_docx_generator import build_nancy_cv_docx
    profile = load_nancy_profile()
    html = build_nancy_cv_html(profile)
    out_path = OUTPUT_DIR / "Nancy_Schuetze_Lebenslauf_Master.pdf"
    build_nancy_cv_docx(profile, OUTPUT_DIR / "Nancy_Schuetze_Lebenslauf_Master.docx")
    return render_html_to_pdf(html, out_path)


def generate_nancy_application_bundle(job: Dict[str, Any], custom_paragraphs: Optional[List[str]] = None) -> Dict[str, Any]:
    from nancy_docx_generator import build_nancy_cv_docx
    profile = load_nancy_profile()
    tailored = select_nancy_tailored_content(job, profile)
    paragraphs = custom_paragraphs if custom_paragraphs else tailored["cover_letter_paragraphs"]

    company_slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(job.get("company") or "Firma")).strip("_")[:30]
    job_id_slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(job.get("id") or "job")).strip("_")[:20]
    folder_name = f"Nancy_{company_slug}_{job_id_slug}"
    job_dir = OUTPUT_DIR / "applications" / folder_name
    job_dir.mkdir(parents=True, exist_ok=True)

    headline = str(job.get("title") or profile["personal_info"]["role_headline_de"])
    cv_html = build_nancy_cv_html(profile, custom_headline=headline)
    cl_html = build_nancy_cover_letter_html(
        profile,
        company=str(job.get("company") or "Unternehmen"),
        job_title=str(job.get("title") or "Werkstudentin Office Management (m/w/d)"),
        location=str(job.get("location") or "Berlin"),
        paragraphs=paragraphs,
    )

    cv_pdf_path = render_html_to_pdf(cv_html, job_dir / f"Nancy_Schuetze_Lebenslauf_{company_slug}.pdf")
    cl_pdf_path = render_html_to_pdf(cl_html, job_dir / f"Nancy_Schuetze_Anschreiben_{company_slug}.pdf")
    cv_docx_path = build_nancy_cv_docx(profile, job_dir / f"Nancy_Schuetze_Lebenslauf_{company_slug}.docx", custom_headline=headline)

    return {
        "folder": str(job_dir),
        "cv_pdf": str(cv_pdf_path),
        "cv_docx": str(cv_docx_path),
        "cover_letter_pdf": str(cl_pdf_path),
        "cv_url": f"/files/applications/{folder_name}/{cv_pdf_path.name}",
        "cv_docx_url": f"/files/applications/{folder_name}/{cv_docx_path.name}",
        "cover_letter_url": f"/files/applications/{folder_name}/{cl_pdf_path.name}",
        "tailored": tailored,
    }


def scrape_nancy_jobs(
    search_terms: Optional[List[str]] = None,
    location: str = "Berlin, Germany",
    results_wanted: int = 10,
    hours_old: int = 168,
    sites: Optional[List[str]] = None,
) -> Dict[str, Any]:
    from jobspy import scrape_jobs
    from metadata_enricher import enrich_jobs_metadata

    if not sites:
        sites = ["linkedin", "indeed"]

    queries = (
        [{"search_term": q, "location": location} for q in search_terms]
        if search_terms
        else NANCY_DEFAULT_QUERIES[:4]
    )

    existing = load_nancy_jobs_db()
    existing_ids = {j["id"] for j in existing}
    existing_keys = {f"{j.get('company','').lower()}|{j.get('title','').lower()}" for j in existing}
    newly_added = []

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
                title = str(row.get("title") or "").strip()
                company = str(row.get("company") or "").strip()
                if not title or not company or title.lower() == "nan":
                    continue

                job_url = str(row.get("job_url_direct") or row.get("job_url") or "").strip()
                # If there's no direct apply URL/button, discard the job immediately
                if not job_url or job_url.lower() in ["nan", "none", "null", ""] or not (job_url.startswith("http://") or job_url.startswith("https://")) or "google.com/search" in job_url:
                    continue

                loc = str(row.get("location") or "Berlin").strip()
                desc = str(row.get("description") or "").strip()
                site = str(row.get("site") or "indeed").capitalize()
                date_posted = str(row.get("date_posted") or datetime.now().strftime("%Y-%m-%d"))

                dedup_key = f"{company.lower()}|{title.lower()}"
                jid = hashlib.md5(f"{dedup_key}|{job_url}".encode("utf-8")).hexdigest()[:10]
                if jid in existing_ids or dedup_key in existing_keys:
                    continue

                job_obj = {
                    "id": jid,
                    "title": title,
                    "company": company,
                    "location": loc,
                    "job_url": job_url,
                    "source": site,
                    "date_posted": date_posted,
                    "salary": "",
                    "description": desc,
                    "status": "New",
                    "cv_pdf": "",
                    "cover_letter_pdf": "",
                    "cv_url": "",
                    "cover_letter_url": "",
                }
                job_obj.update(score_nancy_job(job_obj))
                existing.append(job_obj)
                existing_ids.add(jid)
                existing_keys.add(dedup_key)
                newly_added.append(job_obj)
        except Exception:
            pass

    enrich_jobs_metadata(existing)
    existing.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    save_nancy_jobs_db(existing)
    return {"added_count": len(newly_added), "total_count": len(existing)}


if __name__ == "__main__":
    p = generate_nancy_master_cv()
    print(f"Generated Nancy Master CV: {p}")
