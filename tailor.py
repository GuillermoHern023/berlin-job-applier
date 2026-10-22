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
            "llm", "prompt", "knowledge base", "workflow", "apps script", "bot", "genai",
            "agent", "automatisierung", "tooling",
        ],
    },
    "product_management": {
        "label": "Product Management",
        "keywords": [
            "product manager", "product management", "product owner", "digital product",
            "roadmap", "feature", "user story", "ux", "figma", "backlog", "mvp",
            "product operations", "produktmanagement", "erp", "saas",
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
        "label": "Business & CX Operations",
        "keywords": [
            "operations", "customer experience", "cx", "customer service", "quality assurance",
            "qa", "kpi", "reporting", "dashboard", "looker", "tableau", "process improvement",
            "business operations", "bizops", "freshdesk", "support",
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
    top_kws = ", ".join(matched_keywords[:6]) if matched_keywords else "Project coordination, workflows, stakeholder alignment"
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
    Cover Letter based on Guillermo's Xentral cover letter style + his 4 new Auto1 projects.
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
        if b["id"] == "qa_review_platform" and any(w in desc_lower for w in ["qa", "quality", "audit", "review", "ai", "product", "tool"]):
            b_score += 20
        if b["id"] == "cross_country_kb" and any(w in desc_lower for w in ["knowledge", "documentation", "international", "cross", "operations", "support"]):
            b_score += 20
        if b["id"] == "price_lead_email_tool" and any(w in desc_lower for w in ["automation", "email", "crm", "lead", "process", "admin", "workflow"]):
            b_score += 20
        if b["id"] == "reviews_portal" and any(w in desc_lower for w in ["customer", "review", "trustpilot", "experience", "cx", "template", "portal"]):
            b_score += 20
        scored_bullets.append((b_score, b))

    scored_bullets.sort(key=lambda x: x[0], reverse=True)
    # Keep top 6 bullets so CV fits cleanly on 1 A4 page
    chosen_bullets = [b["html"] for _, b in scored_bullets[:6]]

    # Tailor core skills order
    all_skills = list(profile["skills"]["core"])
    if cat_id == "ai_automation":
        all_skills.sort(key=lambda s: 0 if ("AI" in s or "Automation" in s) else 1)
    elif cat_id == "product_management":
        all_skills.sort(key=lambda s: 0 if ("Product" in s or "Tooling" in s) else 1)

    # Build tailored Cover Letter paragraphs (inspired by Guillermo's Xentral cover letter)
    if cat_id == "ai_automation":
        hook_focus = "AI-driven workflow automation, internal tooling, and scalable process design"
        project_highlight = (
            "Beyond rolling out an AI voice bot across 9 markets (routing 700,000+ calls and boosting inbound answer rates by 20%) "
            "and maintaining AI knowledge bases for a chatbot handling 30,000+ monthly conversations, I proactively built several internal tools. "
            "These include an AI Conversation QA web platform with bulk-review features, an automated Price-Lead Offer Email generator integrated with our admin system, "
            "and a real-time cross-country knowledge base for live multi-market support."
        )
    elif cat_id == "product_management":
        hook_focus = "digital product management, internal tool building, and AI-driven workflow improvements"
        project_highlight = (
            "Alongside helping roll out an AI voice bot (boosting inbound answer rates by 20% across 9 markets) and optimizing a chatbot handling 30,000+ monthly conversations, "
            "I identified operational bottlenecks and built internal web tools to solve them. Specifically, I created an AI Conversation QA web platform with bulk-review capabilities, "
            "a centralized Google Reviews & Trustpilot portal with one-click template approvals, and a real-time cross-country knowledge base for live agent collaboration."
        )
    elif cat_id == "cx_operations":
        hook_focus = "operational excellence, customer experience optimization, and intelligent workflow automation"
        project_highlight = (
            "Among my key contributions was scaling an AI voice bot across 9 markets (improving inbound answer rates from 65% to 85%) and maintaining a chatbot handling 30,000+ monthly conversations. "
            "To further empower our agents, I built a real-time cross-country collaboration knowledge base (enabling markets like NL and BE to support each other live on calls), "
            "a centralized Google Reviews & Trustpilot reply portal, and an automated Price-Lead Offer Email tool."
        )
    else:  # project_management default
        hook_focus = "international project coordination, process documentation, and AI-driven operational improvements"
        project_highlight = (
            "I have taken responsibility for project documentation, KPI reporting, and stakeholder alignment across nine international markets. "
            "Alongside supporting the rollout of an AI voice bot (routing 700,000+ calls and boosting inbound answer rates by 20%) and a chatbot managing 30,000+ monthly conversations, "
            "I delivered practical internal tools—including a real-time cross-country knowledge base, an AI Conversation QA platform with bulk-review workflows, and an automated customer offer email tool."
        )

    paragraphs = [
        (
            f"After prompting more AIs and automating more workflows than I’d like to admit, I’ve learned that real operational impact happens where "
            f"people, clear processes, and smart technology meet. That is why I am excited to apply for the {job_title} role at {company}. "
            f"With hands-on experience in {hook_focus}, combined with my Bachelor’s in Digital Product Management and current Master’s studies in "
            f"International Business Management in Berlin, I am eager to help your team streamline workflows and deliver measurable results."
        ),
        (
            f"In my current role as a Junior Project Manager (Working Student) at Auto1 Group in Berlin, I coordinate across business, tech, product, and customer service teams "
            f"to drive efficiency across nine markets. {project_highlight}"
        ),
        (
            f"I bring strong analytical and organizational skills, hands-on proficiency in Google Workspace, Google Apps Script (JavaScript automation), Looker Studio, Tableau, and Advanced Excel, "
            f"and a proactive builder mindset. I enjoy creating clarity in fast-paced environments, turning repetitive manual tasks into clean tools, and ensuring projects stay organized and on track. "
            f"Working in an international Berlin environment has also strengthened my German (B1) alongside my fluent English and native Spanish."
        ),
        (
            f"What draws me most to {company} is the opportunity to contribute to a dynamic, forward-thinking team where structured execution and practical innovation make a tangible difference. "
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
