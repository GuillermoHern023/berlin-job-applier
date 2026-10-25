import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


import shutil

def find_browser_executable() -> str:
    # 1. Check PATH (for Linux / Ubuntu GitHub Actions and system installs)
    for name in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge", "chrome"]:
        p = shutil.which(name)
        if p and os.path.exists(p):
            return p

    # 2. Windows default installation paths
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError("Neither Google Chrome nor Microsoft Edge nor Chromium was found for PDF generation.")


def load_master_profile() -> Dict[str, Any]:
    profile_path = DATA_DIR / "master_profile.json"
    with open(profile_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_cv_html(
    profile: Dict[str, Any],
    selected_auto1_bullets: Optional[List[str]] = None,
    custom_core_skills: Optional[List[str]] = None,
    role_subtitle: Optional[str] = None,
) -> str:
    p = profile["personal_info"]
    if not selected_auto1_bullets:
        # Default top 6 bullets including the best new projects + core metrics
        selected_auto1_bullets = [b["html"] for b in profile["auto1_bullet_pool"][:6]]

    core_skills = custom_core_skills if custom_core_skills else profile["skills"]["core"]
    core_skills_str = " | ".join(core_skills)

    exp_blocks_html = ""
    for exp in profile["experience"]:
        bullets = selected_auto1_bullets if exp.get("is_dynamic_auto1") else exp.get("bullets", [])
        bullets_html = "\n".join(f"<li>{b}</li>" for b in bullets)
        subtitle_html = f'<div class="exp-subtitle">{exp["subtitle"]}</div>' if exp.get("subtitle") else ""
        exp_blocks_html += f"""
        <div class="row-item">
          <div class="left-col">{exp["dates"]}</div>
          <div class="right-col">
            <div class="exp-title">{exp["title"]}</div>
            <div class="exp-company"><strong>{exp["company"]}</strong> &nbsp;{exp["location"]}</div>
            {subtitle_html}
            <ul class="bullet-list">
              {bullets_html}
            </ul>
          </div>
        </div>
        """

    edu_blocks_html = ""
    for edu in profile["education"]:
        edu_blocks_html += f"""
        <div class="row-item edu-row">
          <div class="left-col">{edu["dates"]}</div>
          <div class="right-col">
            <div class="edu-degree"><strong>{edu["degree"]} | {edu["institution"]}</strong></div>
            <div class="edu-loc">{edu["location"]}</div>
          </div>
        </div>
        """

    lang_blocks_html = ""
    for lang in profile["languages"]:
        lang_blocks_html += f'<div class="lang-item"><strong>{lang["language"]}</strong> {lang["level"]}</div>\n'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{p["full_name"]} - CV</title>
<style>
  @page {{
    size: A4;
    margin: 5.5mm 9mm 5.5mm 9mm;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: Georgia, "Times New Roman", serif;
    font-size: 8.35pt;
    line-height: 1.20;
    color: #1a1a1a;
    background: #fff;
  }}
  .header-box {{
    border: 1px solid #333;
    padding: 6px 11px;
    margin-bottom: 5px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }}
  .header-left h1 {{
    font-size: 14pt;
    font-weight: bold;
    margin-bottom: 1.5px;
    color: #111;
  }}
  .header-left p {{
    font-size: 8.2pt;
    color: #333;
    margin-bottom: 0.5px;
  }}
  .header-right a {{
    font-size: 8.3pt;
    color: #111;
    text-decoration: underline;
  }}
  fieldset.section-box {{
    border: 1px solid #333;
    padding: 4px 11px 5.5px 11px;
    margin-bottom: 5px;
  }}
  fieldset.section-box legend {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 7.8pt;
    font-weight: bold;
    letter-spacing: 0.7px;
    padding: 0 5px;
    margin-left: 4px;
    color: #111;
    text-transform: uppercase;
  }}
  .row-item {{
    display: flex;
    margin-bottom: 4.5px;
  }}
  .row-item:last-child {{
    margin-bottom: 0;
  }}
  .left-col {{
    width: 18%;
    font-size: 8pt;
    color: #333;
    padding-right: 8px;
    flex-shrink: 0;
  }}
  .right-col {{
    width: 82%;
  }}
  .exp-title {{
    font-weight: bold;
    font-size: 8.75pt;
    color: #111;
  }}
  .exp-company {{
    font-size: 8.3pt;
    color: #222;
    margin-bottom: 0.5px;
  }}
  .exp-subtitle {{
    font-size: 8pt;
    color: #444;
    margin-bottom: 1.5px;
  }}
  ul.bullet-list {{
    margin-top: 1.5px;
    padding-left: 14px;
  }}
  ul.bullet-list li {{
    margin-bottom: 1px;
    font-size: 8.15pt;
  }}
  .edu-row {{
    margin-bottom: 3px;
  }}
  .edu-degree {{
    font-size: 8.3pt;
  }}
  .edu-loc {{
    font-size: 7.9pt;
    color: #333;
  }}
  .skills-content p {{
    margin-bottom: 1.5px;
    font-size: 8.1pt;
  }}
  .skills-content p:last-child {{
    margin-bottom: 0;
  }}
  .lang-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    gap: 2px 10px;
    font-size: 8.05pt;
  }}
</style>
</head>
<body>
  <div class="header-box">
    <div class="header-left">
      <h1>{p["full_name"]}</h1>
      <p>{p["address"]}</p>
      <p>{p["email"]}</p>
      <p>{p["phone"]}</p>
    </div>
    <div class="header-right">
      <a href="{p["linkedin_url"]}">{p["linkedin_label"]}</a>
    </div>
  </div>

  <fieldset class="section-box">
    <legend>EXPERIENCE</legend>
    {exp_blocks_html}
  </fieldset>

  <fieldset class="section-box">
    <legend>EDUCATION</legend>
    {edu_blocks_html}
  </fieldset>

  <fieldset class="section-box">
    <legend>SKILLS</legend>
    <div class="skills-content">
      <p><strong>Core Competencies:</strong> {core_skills_str}</p>
      <p><strong>Technical Skills:</strong> {profile["skills"]["technical"]}</p>
      <p><strong>Software Proficiency:</strong> {profile["skills"]["software"]}</p>
    </div>
  </fieldset>

  <fieldset class="section-box" style="margin-bottom: 0;">
    <legend>LANGUAGES</legend>
    <div class="lang-grid">
      {lang_blocks_html}
    </div>
  </fieldset>
</body>
</html>
"""


def build_cover_letter_html(
    profile: Dict[str, Any],
    company: str,
    job_title: str,
    location: str,
    paragraphs: List[str],
    recipient: str = "Hiring Team",
    date_str: Optional[str] = None,
) -> str:
    p = profile["personal_info"]
    if not date_str:
        date_str = datetime.now().strftime("%d/%m/%Y")

    body_paragraphs_html = "\n".join(f"<p>{para}</p>" for para in paragraphs)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{p["short_name"]} - Cover Letter - {company}</title>
<style>
  @page {{
    size: A4;
    margin: 18mm 22mm 18mm 22mm;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.55;
    color: #1e293b;
    background: #fff;
  }}
  .top-header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    border-bottom: 2px solid #0f172a;
    padding-bottom: 8px;
    margin-bottom: 18px;
  }}
  .sender-name {{
    font-size: 16.5pt;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.2px;
  }}
  .sender-contact {{
    text-align: right;
    font-size: 9.5pt;
    line-height: 1.4;
    color: #475569;
  }}
  .meta-row {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 18px;
    font-size: 10pt;
    color: #334155;
  }}
  .recipient-info div {{
    margin-bottom: 2px;
  }}
  .job-subject {{
    font-weight: 700;
    font-size: 11pt;
    color: #0f172a;
    margin-top: 6px;
  }}
  .date-col {{
    font-size: 9.5pt;
    color: #64748b;
  }}
  .salutation {{
    font-weight: 600;
    color: #0f172a;
    margin-bottom: 12px;
  }}
  .letter-body p {{
    margin-bottom: 12px;
    text-align: left;
    color: #334155;
  }}
  .sign-off {{
    margin-top: 20px;
    color: #334155;
  }}
  .sign-off p {{
    margin-bottom: 3px;
  }}
</style>
</head>
<body>
  <div class="top-header">
    <div class="sender-name">{p["full_name"]}</div>
    <div class="sender-contact">
      <div>{p["phone"]}</div>
      <div>{p["email"]}</div>
      <div>{p["address"]}</div>
    </div>
  </div>

  <div class="meta-row">
    <div class="recipient-info">
      <div><strong>{company}</strong></div>
      <div>{recipient}</div>
      <div>{location}</div>
      <div class="job-subject">{job_title}</div>
    </div>
    <div class="date-col">{date_str}</div>
  </div>

  <div class="salutation">Dear {recipient},</div>

  <div class="letter-body">
    {body_paragraphs_html}
  </div>

  <div class="sign-off">
    <p>Sincerely,</p>
    <p><strong>{p["short_name"]}</strong></p>
  </div>
</body>
</html>
"""


def render_html_to_pdf(html_content: str, output_pdf_path: Path) -> Path:
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    temp_html_path = output_pdf_path.with_suffix(".html")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    browser_exe = find_browser_executable()
    cmd = [
        browser_exe,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--no-pdf-header-footer",
        f"--print-to-pdf={str(output_pdf_path.resolve())}",
        temp_html_path.resolve().as_uri(),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_pdf_path


def generate_master_cv() -> Path:
    profile = load_master_profile()
    # Select the 6 strongest bullets combining core metrics + new internal tools built
    bullets = [
        b["html"]
        for b in profile["auto1_bullet_pool"]
        if b["id"] in [
            "voicebot_rollout",
            "chatbot_kb_maintenance",
            "qa_review_platform",
            "cross_country_kb",
            "price_lead_email_tool",
            "reviews_portal",
            "kpi_reporting",
        ]
    ]
    html = build_cv_html(profile, selected_auto1_bullets=bullets)
    out_path = OUTPUT_DIR / "Guillermo_Hernandez_CV_Master.pdf"
    return render_html_to_pdf(html, out_path)


if __name__ == "__main__":
    pdf_path = generate_master_cv()
    print(f"Generated Master CV at: {pdf_path}")
