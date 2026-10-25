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

    # Build tailored Cover Letter paragraphs without emdashes or rigid keyword copying
    if cat_id == "ai_automation":
        project_highlight = (
            "A core focus of my work has been conversational AI, where I supported the rollout and continuous tuning of our AI voice bot across 9 markets, routing millions of calls and increasing answer rates from 65% to 85%. "
            "I also manage the knowledge architecture and retrieval datasets for an AI chatbot handling over 30,000 monthly inquiries, and built an internal bulk-review QA platform to streamline how agents evaluate model quality."
        )
    elif cat_id == "product_management":
        project_highlight = (
            "Embedded in an agile cross-functional product environment, I helped scale our conversational AI tooling across 9 international markets, routing millions of calls while improving answer rates by 20%. "
            "To support our operational workflows, I have designed and deployed internal evaluation tools, including an AI conversation QA web platform with bulk review pipelines, a centralized review management portal versioned via GitHub, and automated dispatch workflows."
        )
    elif cat_id == "cx_operations":
        project_highlight = (
            "My key initiatives include optimizing an international AI voice bot that scaled to route millions of calls (raising inbound answer rates from 65% to 85%), as well as structuring retrieval knowledge bases for an AI chatbot handling 30,000+ monthly customer chats. "
            "To empower operational teams, I built an automated multi-market knowledge base, an AI QA review web application, and API-driven customer communication tools."
        )
    else:  # project_management default
        project_highlight = (
            "Working closely with product, engineering, and regional operations teams across 9 markets, I supported the rollout of an AI voice bot that scaled to route millions of calls, lifting answer rates by 20%. "
            "I also maintain knowledge bases for a customer-facing chatbot handling 30,000+ monthly conversations, and built internal web utilities, including an AI conversation evaluation platform and an automated customer offer generator connecting internal systems."
        )

    paragraphs = [
        (
            f"I am writing to express my strong interest in the {job_title} role at {company}. "
            f"Through my experience helping scale conversational AI tools, optimizing operational workflows, and building data-driven internal products at Auto1 Group, "
            f"I have learned that the greatest value comes from combining analytical rigor with practical builder execution. "
            f"With a Bachelor's degree in Digital Product Management and my ongoing Master's studies in International Business Management in Berlin, "
            f"I am eager to contribute this hands-on, problem-solving mindset to your team."
        ),
        (
            f"In my current role as a Junior Project Manager at Auto1 Group in Berlin, I work closely with product managers, developers, and regional operations leads across nine European markets. "
            f"{project_highlight}"
        ),
        (
            f"Beyond day-to-day operations, I genuinely enjoy untangling disorganized datasets and creating solutions that make teams more efficient. "
            f"In my analytics and reporting work, I frequently write SQL queries in Redash and build dashboards across Excel, Tableau, and Looker Studio so stakeholders have dependable, real-time metrics. "
            f"When off-the-shelf software falls short, I roll up my sleeves to build lightweight internal tools, whether that means connecting internal systems through REST APIs, automating multi-step workflows, or testing and structuring custom evaluation data. "
            f"Collaborating in an international Berlin environment has also allowed me to work comfortably across languages, using my native Spanish, fluent English, and working German (B1)."
        ),
        (
            f"What particularly excites me about {company} is the opportunity to bring this mix of analytical curiosity and builder execution to your team. "
            f"Thank you very much for taking the time to review my application. I would welcome the chance to speak with you and discuss how my background can support {company} in this role."
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
