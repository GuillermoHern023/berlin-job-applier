import re
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from pdf_generator import (
    load_master_profile,
    build_cv_html,
    build_cover_letter_html,
    render_html_to_pdf,
    OUTPUT_DIR,
)


ROLE_CATEGORIES = {
    "ai_automation": {
        "label": "AI Operations & Automation",
        "keywords": [
            "ai", "artificial intelligence", "automation", "chatbot", "voicebot", "voice bot",
            "llm", "prompt", "knowledge base", "vector", "vector database", "evaluation",
            "workflow", "apps script", "low-code", "rest api", "api", "git", "github", "cloud",
            "bot", "genai", "agent", "automatisierung", "tooling",
        ],
    },
    "product_management": {
        "label": "Product Management",
        "keywords": [
            "product manager", "product management", "product owner", "product team", "digital product",
            "roadmap", "feature", "user story", "ux", "figma", "backlog", "mvp",
            "product operations", "produktmanagement", "erp", "saas", "evaluation",
        ],
    },
    "project_management": {
        "label": "Project Management",
        "keywords": [
            "project manager", "project management", "program manager", "pmo", "stakeholder",
            "coordination", "rollout", "agile", "scrum", "documentation", "cross-functional",
            "projektmanagement", "implementation", "initiative",
        ],
    },
    "cx_operations": {
        "label": "Business & Data Operations",
        "keywords": [
            "operations", "customer experience", "cx", "customer service", "quality assurance",
            "qa", "kpi", "reporting", "dashboard", "sql", "redash", "quantitative", "complex data",
            "data analysis", "looker", "tableau", "process improvement", "business operations",
            "bizops", "freshdesk", "support",
        ],
    },
}


def detect_language_requirement(title: str, description: str) -> Tuple[str, int]:
    """
    Returns (label, score_adjustment)
    """
    title_l = title.lower()
    text = f"{title} {description}".lower()

    # Check if title explicitly requires a language Guillermo doesn't speak
    other_langs = [
        "nordic", "swedish", "danish", "norwegian", "finnish", "arabic", "dutch",
        "polish", "italian", "turkish", "russian", "japanese", "chinese", "mandarin",
        "korean", "portuguese", "czech", "hungarian", "greek",
    ]
    for ol in other_langs:
        if ol in title_l:
            return (f"Requires {ol.capitalize()}", -40)

    if "spanish" in title_l or "spanisch" in title_l:
        return ("Spanish + English (Native Fit!)", +18)

    strict_german_patterns = [
        r"c1\s*(?:or\s*c2\s*)?german",
        r"german\s*\(?c1",
        r"german\s*\(?c2",
        r"fluent\s+in\s+german",
        r"fluent\s+german",
        r"native\s+german",
        r"verhandlungssicher(?:es)?\s+deutsch",
        r"fließend(?:es)?\s+deutsch",
        r"deutsch\s+auf\s+muttersprach",
        r"deutschkenntnisse\s+auf\s+c1",
        r"excellent\s+german",
    ]
    for pat in strict_german_patterns:
        if re.search(pat, text):
            return ("German C1/Fluent Required", -25)

    # Check if the entire job description is written in German without mentioning English
    german_stop_words = len(re.findall(r"\b(und|oder|für|mit|deine|aufgaben|wir|suchen|arbeit|studium)\b", text))
    english_stop_words = len(re.findall(r"\b(and|with|your|tasks|we|looking|working|student|experience|team)\b", text))

    if german_stop_words > 12 and english_stop_words < 4:
        return ("German Job Post (Check B1 Fit)", -15)

    if re.search(r"english\s*(?:and|&|/)\s*german", text) or re.search(r"german\s*(?:is\s+a\s+plus|b1|b2|basic|beneficial)", text):
        return ("English + Basic/B1 German OK", +8)

    return ("English Friendly", +10)


def score_and_classify_job(job: Dict[str, Any]) -> Dict[str, Any]:
    title = str(job.get("title") or "")
    company = str(job.get("company") or "")
    description = str(job.get("description") or "")
    location = str(job.get("location") or "Berlin, Germany")

    text_lower = f"{title} {description}".lower()
    title_lower = title.lower()

    # 1. Detect primary role category
    cat_scores = {}
    matched_keywords = []
    for cat_id, cat_info in ROLE_CATEGORIES.items():
        score = 0
        for kw in cat_info["keywords"]:
            if kw in title_lower:
                score += 12
                if kw not in matched_keywords:
                    matched_keywords.append(kw)
            elif kw in text_lower:
                score += 4
                if kw not in matched_keywords:
                    matched_keywords.append(kw)
        cat_scores[cat_id] = score

    best_cat_id = max(cat_scores, key=cat_scores.get) if any(cat_scores.values()) else "project_management"
    best_cat_label = ROLE_CATEGORIES[best_cat_id]["label"]

    # 2. Base Match Score calculation
    base_score = 52
    # Working student / Intern / Junior bonus
    if any(k in title_lower for k in ["working student", "werkstudent", "student", "studentische"]):
        base_score += 18
    elif any(k in title_lower for k in ["junior", "intern", "associate", "coordinator"]):
        base_score += 10
    elif any(k in title_lower for k in ["senior", "lead", "head of", "director", "principal", "vp"]):
        base_score -= 30

    # Add keyword points (capped)
    keyword_bonus = min(25, sum(cat_scores.values()) // 3)
    base_score += keyword_bonus

    # Language check
    lang_label, lang_adj = detect_language_requirement(title, description)
    base_score += lang_adj

    # Location check
    loc_lower = location.lower()
    if any(k in loc_lower for k in ["berlin", "remote", "potsdam"]):
        base_score += 5

    final_score = max(10, min(99, base_score))

    # Extract hourly rate / salary if mentioned
    salary_match = re.search(
        r"(\d{2}(?:[.,]\d{1,2})?\s*€\s*(?:/|\s*per\s*|\s*pro\s*)?(?:h|hour|std|stunde)|€\s*\d{2}(?:[.,]\d{1,2})?\s*(?:/h|per hour))",
        description,
        re.IGNORECASE,
    )
    extracted_pay = salary_match.group(0) if salary_match else (job.get("salary") or "Not listed")

    # Why it fits summary
    top_kws = ", ".join(matched_keywords[:6]) if matched_keywords else "Product team, SQL (Redash), quantitative analysis, AI evaluation tools"
    why_fits = f"Strong {best_cat_label} fit. Matches keywords: {top_kws}."

    return {
        "category_id": best_cat_id,
        "category_label": best_cat_label,
        "match_score": final_score,
        "language_req": lang_label,
        "extracted_pay": extracted_pay,
        "matched_keywords": matched_keywords[:8],
        "why_fits": why_fits,
    }


def select_tailored_content(job: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Selects the best 6 Auto1 Group bullets, orders core skills, and crafts a tailored 4-paragraph
    Cover Letter based on Guillermo's Xentral cover letter style + his technical & product skills.
    """
    analysis = score_and_classify_job(job)
    cat_id = analysis["category_id"]
    company = str(job.get("company") or "your company").strip()
    job_title = str(job.get("title") or "Working Student Project Management (m/f/d)").strip()
    location = str(job.get("location") or "Berlin, Germany").strip()

    # Score each Auto1 bullet for this job
    desc_lower = f"{job_title} {job.get('description', '')}".lower()
    scored_bullets = []
    for b in profile["auto1_bullet_pool"]:
        b_score = b["priority"]
        if cat_id in b["tags"]:
            b_score += 25
        if "new_project" in b["tags"]:
            b_score += 10
        # Extra boost if specific words match
        if b["id"] == "qa_review_platform" and any(w in desc_lower for w in ["qa", "quality", "audit", "review", "evaluation", "ai", "product", "tool"]):
            b_score += 25
        if b["id"] == "chatbot_kb_maintenance" and any(w in desc_lower for w in ["vector", "database", "knowledge", "rag", "chatbot", "llm"]):
            b_score += 25
        if b["id"] == "kpi_reporting" and any(w in desc_lower for w in ["sql", "redash", "quantitative", "complex", "data", "kpi", "reporting", "analytics"]):
            b_score += 25
        if b["id"] == "cross_country_kb" and any(w in desc_lower for w in ["knowledge", "documentation", "international", "cross", "operations", "support"]):
            b_score += 20
        if b["id"] == "price_lead_email_tool" and any(w in desc_lower for w in ["automation", "api", "rest", "low-code", "email", "crm", "lead", "workflow"]):
            b_score += 25
        if b["id"] == "reviews_portal" and any(w in desc_lower for w in ["customer", "review", "trustpilot", "git", "github", "portal"]):
            b_score += 20
        scored_bullets.append((b_score, b))

    scored_bullets.sort(key=lambda x: x[0], reverse=True)
    # Keep top 6 bullets so CV fits cleanly on 1 A4 page
    chosen_bullets = [b["html"] for _, b in scored_bullets[:6]]

    # Tailor core skills order
    all_skills = list(profile["skills"]["core"])
    if cat_id == "ai_automation":
        all_skills.sort(key=lambda s: 0 if ("AI" in s or "Automation" in s or "Vector" in s) else 1)
    elif cat_id == "product_management":
        all_skills.sort(key=lambda s: 0 if ("Product" in s or "Quantitative" in s) else 1)

    # Build tailored Cover Letter paragraphs
    if cat_id == "ai_automation":
        hook_focus = "AI-driven workflow automation, evaluation tooling, vector/knowledge databases, and quantitative data analysis"
        project_highlight = (
            "Working embedded in a cross-functional product and operations team, I helped roll out an AI voice bot across 9 markets (routing 700,000+ calls and boosting inbound answer rates by 20%) "
            "and structured AI knowledge/vector databases for a chatbot handling 30,000+ monthly conversations. Furthermore, I built an internal AI Conversation QA & Evaluation web tool with bulk-review pipelines, "
            "an automated Price-Lead Offer Email generator integrating internal admin systems and REST APIs, and a real-time cross-country knowledge base."
        )
    elif cat_id == "product_management":
        hook_focus = "agile product team execution, quantitative analysis on complex datasets, and AI evaluation tooling"
        project_highlight = (
            "Collaborating closely within our cross-functional Product, Tech, and Analytics team, I helped scale an AI voice bot (boosting inbound answer rates by 20% across 9 markets) and maintained knowledge/vector databases for a chatbot handling 30,000+ monthly conversations. "
            "I also designed and shipped internal product & evaluation tools—including an AI Conversation QA & Evaluation web platform with bulk-review workflows, a Google Reviews & Trustpilot portal (versioned via Git/GitHub), and REST API / low-code workflow automations."
        )
    elif cat_id == "cx_operations":
        hook_focus = "quantitative analysis on complex datasets, SQL reporting, and intelligent workflow automation"
        project_highlight = (
            "Among my key contributions was scaling an AI voice bot across 9 markets (improving inbound answer rates from 65% to 85%) and structuring knowledge/vector databases for a chatbot handling 30,000+ monthly conversations. "
            "To empower our international teams, I built an AI Conversation QA & Evaluation platform, a real-time cross-country collaboration knowledge base, and an automated Price-Lead Offer Email tool using REST APIs and low-code automation."
        )
    else:  # project_management default
        hook_focus = "cross-functional product & project execution, quantitative analysis on complex datasets, and AI evaluation tooling"
        project_highlight = (
            "Working closely with our Product, Tech, and Analytics teams across nine international markets, I supported the rollout of an AI voice bot (routing 700,000+ calls and boosting inbound answer rates by 20%) and structured knowledge/vector databases for a chatbot managing 30,000+ monthly conversations. "
            "I also built practical internal tools—including an AI Conversation QA & Evaluation platform with bulk-review pipelines, a real-time cross-country knowledge base, and an automated customer offer tool integrating internal admin systems and REST APIs."
        )

    paragraphs = [
        (
            f"After prompting more AIs, querying more messy databases, and automating more workflows than I’d like to admit, I’ve learned that real impact happens where "
            f"product thinking, clean data, and smart technology meet. That is why I am excited to apply for the {job_title} role at {company}. "
            f"With hands-on experience in {hook_focus}, combined with my Bachelor’s in Digital Product Management and current Master’s studies in "
            f"International Business Management in Berlin, I am eager to help your team turn complex problems into scalable solutions."
        ),
        (
            f"In my current role as a Junior Project Manager (Working Student) at Auto1 Group in Berlin, I work embedded in a cross-functional product and operations environment "
            f"across nine markets. {project_highlight}"
        ),
        (
            f"On the analytical and technical side, I perform quantitative analysis on complex, disorganized datasets daily—using SQL in Redash, Advanced Excel, Looker Studio, and Tableau to build reliable company-wide KPI reporting. "
            f"I am comfortable working with Git/GitHub, REST APIs, cloud platforms, low-code automation tools (such as Google Apps Script), and custom evaluation/vector databases. "
            f"Working in an international Berlin environment has also strengthened my German (B1) alongside my fluent English and native Spanish."
        ),
        (
            f"What draws me most to {company} is the opportunity to contribute to a dynamic, product-driven team where quantitative rigor and practical builder execution make a tangible difference. "
            f"Thank you for considering my application—I would welcome the opportunity to discuss how I can support {company} in this role."
        ),
    ]

    return {
        "analysis": analysis,
        "selected_bullets": chosen_bullets,
        "selected_skills": all_skills,
        "cover_letter_paragraphs": paragraphs,
    }


def generate_job_application_bundle(job: Dict[str, Any], custom_bullets: List[str] = None, custom_paragraphs: List[str] = None) -> Dict[str, str]:
    profile = load_master_profile()
    tailored = select_tailored_content(job, profile)

    bullets = custom_bullets if custom_bullets else tailored["selected_bullets"]
    paragraphs = custom_paragraphs if custom_paragraphs else tailored["cover_letter_paragraphs"]

    company_slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(job.get("company") or "Company")).strip("_")[:30]
    job_id_slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(job.get("id") or "job")).strip("_")[:20]
    folder_name = f"{company_slug}_{job_id_slug}"
    job_dir = OUTPUT_DIR / "applications" / folder_name
    job_dir.mkdir(parents=True, exist_ok=True)

    cv_html = build_cv_html(profile, selected_auto1_bullets=bullets, custom_core_skills=tailored["selected_skills"])
    cl_html = build_cover_letter_html(
        profile,
        company=str(job.get("company") or "Hiring Company"),
        job_title=str(job.get("title") or "Working Student Project Management"),
        location=str(job.get("location") or "Berlin, Germany"),
        paragraphs=paragraphs,
    )

    cv_pdf_path = render_html_to_pdf(cv_html, job_dir / f"Guillermo_Hernandez_CV_{company_slug}.pdf")
    cl_pdf_path = render_html_to_pdf(cl_html, job_dir / f"Guillermo_Hernandez_Cover_Letter_{company_slug}.pdf")

    return {
        "folder": str(job_dir),
        "cv_pdf": str(cv_pdf_path),
        "cover_letter_pdf": str(cl_pdf_path),
        "cv_url": f"/files/applications/{folder_name}/{cv_pdf_path.name}",
        "cover_letter_url": f"/files/applications/{folder_name}/{cl_pdf_path.name}",
        "tailored": tailored,
    }
