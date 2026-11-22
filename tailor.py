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


def calculate_commute_from_sohtstrasse(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates estimated public transit commute time from Guillermo's home at:
    Söhtstraße 16, 12203 Berlin (S-Bahn Lichterfelde West, S1).
    Target limit: max 1 hour 10 minutes (70 minutes).
    """
    title = str(job.get("title") or "").strip()
    loc = str(job.get("location") or "").strip()
    desc = str(job.get("description") or "").strip()
    work_model = str(job.get("work_model") or "").strip()

    loc_lower = loc.lower()
    title_lower = title.lower()
    desc_lower = desc.lower()

    # 1. 100% Remote / Home Office
    if "100% remote" in work_model.lower() or "fully remote" in desc_lower or "remote first" in desc_lower or "100% remote" in title_lower:
        return {
            "commute_minutes": 0,
            "within_limit": True,
            "badge": "🏡 Remote (0 min)",
            "summary": "100% Remote / Home Office",
            "transit_route": "Remote / Home Office",
        }

    # 2. Distant cities outside Berlin/Brandenburg
    distant_cities = ["münchen", "munich", "frankfurt", "bonn", "hamburg", "stuttgart", "köln", "cologne", "düsseldorf", "leipzig", "nürnberg", "dresden"]
    is_distant = False
    for dc in distant_cities:
        if re.search(r'\b' + dc + r'\b', loc_lower) and "berlin" not in loc_lower:
            is_distant = True
            break
        if re.search(r'\b' + dc + r'\b', title_lower) and "berlin" not in title_lower and "remote" not in title_lower and "deutschlandweit" not in title_lower:
            is_distant = True
            break

    if is_distant and "remote" not in desc_lower and "hybrid" not in desc_lower:
        return {
            "commute_minutes": 180,
            "within_limit": False,
            "badge": "⚠️ >3h (Distant City)",
            "summary": "Located outside Berlin-Brandenburg metropolitan region",
            "transit_route": "ICE / Long-distance",
        }

    # 3. Outer Brandenburg outside 70-min ring
    if any(k in loc_lower or k in desc_lower for k in ["fürstenwalde", "fuerstenwalde"]):
        return {
            "commute_minutes": 90,
            "within_limit": False,
            "badge": "⚠️ ~90 min (>1h 10m)",
            "summary": "Fürstenwalde (Spree): ~90 min from Söhtstr. 16 via S1 + RE1",
            "transit_route": "S1 -> Potsdamer Platz -> RE1 Fürstenwalde",
        }

    if any(k in loc_lower or k in desc_lower for k in ["grünheide", "gruenheide", "gigafactory"]):
        return {
            "commute_minutes": 85,
            "within_limit": False,
            "badge": "⚠️ ~85 min (>1h 10m)",
            "summary": "Grünheide (Mark) / Gigafactory: ~85 min from Söhtstr. 16 via S1 + RE1 + Bus",
            "transit_route": "S1 -> Potsdamer Platz -> RE1 Fangschleuse + Shuttle",
        }

    outer_bb = ["frankfurt (oder)", "frankfurt oder", "cottbus", "brandenburg an der havel", "eberswalde", "neuruppin"]
    for ob in outer_bb:
        if ob in loc_lower:
            return {
                "commute_minutes": 85,
                "within_limit": False,
                "badge": "⚠️ ~85 min (>1h 10m)",
                "summary": f"{ob.title()}: >70 min from Söhtstr. 16",
                "transit_route": "Regionalbahn (>70 min)",
            }

    # 4. Commutable Brandenburg locations (Potsdam, Schönefeld, Teltow)
    if "potsdam" in loc_lower or "potsdam" in title_lower:
        return {
            "commute_minutes": 40,
            "within_limit": True,
            "badge": "🚇 ~40 min (S1/S7)",
            "summary": "Potsdam: ~40 min from Söhtstr. 16 (S1 Wannsee + S7/RB)",
            "transit_route": "S1 -> Wannsee -> S7/RB Potsdam Hbf",
        }

    if "schönefeld" in loc_lower or "schoenefeld" in loc_lower:
        return {
            "commute_minutes": 45,
            "within_limit": True,
            "badge": "🚇 ~45 min (S1/S45)",
            "summary": "Schönefeld: ~45 min from Söhtstr. 16 (S1 Südkreuz + S45)",
            "transit_route": "S1 -> Südkreuz -> S45 Schönefeld",
        }

    if "blankenfelde" in loc_lower or "mahlow" in loc_lower or "teltow" in loc_lower:
        return {
            "commute_minutes": 30,
            "within_limit": True,
            "badge": "🚇 ~30 min (S1/Bus)",
            "summary": "Teltow/Blankenfelde: ~30 min from Söhtstr. 16",
            "transit_route": "S1 / Bus X01/184",
        }

    # 5. Berlin Districts
    district_times = {
        ("lichterfelde", "steglitz", "zehlendorf", "dahlem"): (15, "🚇 ~15 min (S1/Local)"),
        ("schöneberg", "schoeneberg", "innsbrucker platz", "südkreuz", "suedkreuz", "tempelhof"): (18, "🚇 ~18 min (S1 Direct)"),
        ("potsdamer platz", "mitte", "friedrichstraße", "friedrichstrasse", "tiergarten", "brandenburger tor"): (22, "🚇 ~22 min (S1 Direct)"),
        ("charlottenburg", "wilmersdorf", "kudamm", "kurfürstendamm", "zoologischer garten", "zoo"): (25, "🚇 ~25 min (S1/Ring)"),
        ("kreuzberg", "neukölln", "neukoelln", "gleisdreieck", "hermannstraße"): (25, "🚇 ~25 min (S1/U-Bahn)"),
        ("moabit", "wedding", "gesundbrunnen", "hauptbahnhof"): (28, "🚇 ~28 min (S1/U9)"),
        ("friedrichshain", "ostkreuz", "warschau", "alexanderplatz"): (32, "🚇 ~32 min (S1/S-Bahn)"),
        ("prenzlauer berg", "pankow"): (35, "🚇 ~35 min (S1/Ring)"),
        ("adlershof", "treptow", "köpenick", "koepenick"): (45, "🚇 ~45 min (S1/S-Bahn)"),
        ("spandau", "reinickendorf", "tegel"): (45, "🚇 ~45 min (S1/U-Bahn)"),
        ("marzahn", "hellersdorf", "lichtenberg"): (50, "🚇 ~50 min (S1/S-Bahn)"),
    }
    combined_text = f"{loc_lower} {title_lower} {desc_lower}"
    for keys, (minutes, badge) in district_times.items():
        if any(k in combined_text for k in keys):
            return {
                "commute_minutes": minutes,
                "within_limit": True,
                "badge": badge,
                "summary": f"Estimated transit: ~{minutes} min from Söhtstr. 16 via BVG/S-Bahn",
                "transit_route": f"S1 Lichterfelde West -> BVG (~{minutes} min)",
            }

    # Default Berlin
    return {
        "commute_minutes": 25,
        "within_limit": True,
        "badge": "🚇 ~25 min (S1)",
        "summary": "Central Berlin: ~25 min from Söhtstr. 16 via S1 direct",
        "transit_route": "S1 Lichterfelde West -> Berlin City (~25 min)",
    }


def estimate_job_compensation(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns structured compensation details for a job:
    - If explicit salary is in job metadata or description, cleans and formats it.
    - Otherwise calculates a realistic Berlin benchmark estimate based on role, company, seniority, and domain.
    """
    raw_salary = str(job.get("salary") or "").strip()
    title = str(job.get("title") or "").strip()
    company = str(job.get("company") or "").strip()
    desc = str(job.get("description") or "").strip()

    title_l = title.lower()
    desc_l = desc.lower()
    company_l = company.lower()

    # 1. Check if explicit salary is in job metadata
    if raw_salary and raw_salary.lower() not in ["none", "nan", "not listed", "null", ""]:
        nums = re.findall(r"(\d+(?:\.\d+)?)", raw_salary)
        if nums:
            low = float(nums[0])
            high = float(nums[1]) if len(nums) > 1 else low
            if "hour" in raw_salary.lower() or low < 100:
                badge = f"💰 €{low:.0f}/h" if low == high else f"💰 €{low:.0f}–{high:.0f}/h"
                monthly_low = int(low * 86.6)
                monthly_high = int(high * 86.6)
                return {
                    "is_estimated": False,
                    "badge": badge,
                    "display": f"{badge} (Listed)",
                    "range_text": f"€{low:.2f} – €{high:.2f} / hour",
                    "monthly_estimate": f"~€{monthly_low:,} – €{monthly_high:,}/mo (20h)".replace(",", "."),
                    "source": "Employer Listed",
                }
            elif "month" in raw_salary.lower() or (low >= 1000 and low <= 8000):
                badge = f"💰 €{int(low):,}–€{int(high):,}/mo".replace(",", ".")
                return {
                    "is_estimated": False,
                    "badge": badge,
                    "display": f"{badge} (Listed)",
                    "range_text": f"€{int(low):,} – €{int(high):,} / month".replace(",", "."),
                    "monthly_estimate": f"€{int(low):,} – €{int(high):,}/mo".replace(",", "."),
                    "source": "Employer Listed",
                }
            elif low > 20000:
                badge = f"💰 €{int(low/1000)}k–{int(high/1000)}k/yr"
                return {
                    "is_estimated": False,
                    "badge": badge,
                    "display": f"{badge} (Listed)",
                    "range_text": f"€{int(low):,} – €{int(high):,} / year".replace(",", "."),
                    "monthly_estimate": f"~€{int(low/12):,} – €{int(high/12):,}/mo".replace(",", "."),
                    "source": "Employer Listed",
                }

    # 2. Check if hourly rate is written in the job description text
    desc_salary = re.search(
        r"(\d{2}(?:[.,]\d{1,2})?)\s*(?:€|euro)\s*(?:/|\s*per\s*|\s*pro\s*)?(?:h|hour|std|stunde)",
        desc,
        re.IGNORECASE,
    )
    if desc_salary:
        val = desc_salary.group(1).replace(",", ".")
        try:
            rate = float(val)
            badge = f"💰 €{rate:.0f}/h"
            return {
                "is_estimated": False,
                "badge": badge,
                "display": f"{badge} (Listed in text)",
                "range_text": f"€{rate:.2f}/h",
                "monthly_estimate": f"~€{int(rate * 86.6):,}/mo (20h)".replace(",", "."),
                "source": "Job Description",
            }
        except Exception:
            pass

    # 3. Calculate Realistic Berlin Benchmark Estimate
    is_enterprise = any(k in company_l for k in ["sap", "amazon", "google", "microsoft", "deloitte", "pwc", "kpmg", "mckinsey", "zalando", "check24", "universal music"])
    is_scaleup = any(k in company_l for k in ["auto1", "delivery hero", "n26", "contentful", "personio", "hellofresh", "jobbird", "tier", "flink", "trade republic"])
    is_tech_ai = any(k in title_l or k in desc_l for k in ["ai", "machine learning", "data analytics", "sql", "sap", "cloud", "software", "infrastructure", "python"])

    # Role seniority:
    # A) Working Student
    if any(k in title_l for k in ["working student", "werkstudent", "student", "studentische", "hilfskraft"]):
        base_low = 14.50
        base_high = 16.50
        if is_enterprise:
            base_low += 3.50
            base_high += 5.50
        elif is_scaleup or is_tech_ai:
            base_low += 1.50
            base_high += 2.50

        low_h = round(base_low)
        high_h = round(base_high)
        monthly_low = int(low_h * 86.6)
        monthly_high = int(high_h * 86.6)
        badge = f"💰 ~€{low_h}–{high_h}/h"
        return {
            "is_estimated": True,
            "badge": badge,
            "display": f"{badge} (~€{monthly_low}–€{monthly_high}/mo)",
            "range_text": f"~€{low_h} – €{high_h} / hour (Berlin Tech Benchmark)",
            "monthly_estimate": f"~€{monthly_low} – €{monthly_high} / month (at 20h/wk)",
            "source": "Berlin Benchmark Estimate",
            "tier": "Enterprise (+premium)" if is_enterprise else ("Tech / Scale-up" if (is_scaleup or is_tech_ai) else "Standard Berlin"),
        }

    # B) Intern / Praktikum
    if any(k in title_l for k in ["intern", "praktikant", "praktikum", "internship"]):
        monthly_low = 1300 if not is_enterprise else 1700
        monthly_high = 1800 if not is_enterprise else 2200
        badge = f"💰 ~€{monthly_low}–{monthly_high}/mo"
        return {
            "is_estimated": True,
            "badge": badge,
            "display": f"{badge} (Internship)",
            "range_text": f"~€{monthly_low} – €{monthly_high} / month",
            "monthly_estimate": f"~€{monthly_low} – €{monthly_high} / month",
            "source": "Berlin Benchmark Estimate",
            "tier": "Enterprise" if is_enterprise else "Berlin Startup/Tech",
        }

    # C) Junior / Associate
    if any(k in title_l for k in ["junior", "associate", "trainee", "entry", "coordinator", "assistant"]):
        annual_low = 42
        annual_high = 50
        if is_enterprise:
            annual_low += 8
            annual_high += 12
        elif is_tech_ai:
            annual_low += 3
            annual_high += 5
        badge = f"💰 ~€{annual_low}k–{annual_high}k/yr"
        return {
            "is_estimated": True,
            "badge": badge,
            "display": f"{badge} (Junior/Associate)",
            "range_text": f"~€{annual_low}.000 – €{annual_high}.000 / year",
            "monthly_estimate": f"~€{int(annual_low*1000/12):,} – €{int(annual_high*1000/12):,}/mo".replace(",", "."),
            "source": "Berlin Benchmark Estimate",
            "tier": "Junior Tech/Operations",
        }

    # D) Mid-level Specialist / Manager / Consultant
    annual_low = 52
    annual_high = 68
    if is_enterprise:
        annual_low += 10
        annual_high += 15
    badge = f"💰 ~€{annual_low}k–{annual_high}k/yr"
    return {
        "is_estimated": True,
        "badge": badge,
        "display": f"{badge} (Mid-level)",
        "range_text": f"~€{annual_low}.000 – €{annual_high}.000 / year",
        "monthly_estimate": f"~€{int(annual_low*1000/12):,} – €{int(annual_high*1000/12):,}/mo".replace(",", "."),
        "source": "Berlin Benchmark Estimate",
        "tier": "Professional/Manager",
    }


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

    # Commute check from Söhtstraße 16, 12203 Berlin
    commute_info = calculate_commute_from_sohtstrasse(job)

    # Compensation check (listed or Berlin benchmark estimate)
    compensation_info = estimate_job_compensation(job)

    return {
        "category_id": best_cat_id,
        "category_label": best_cat_label,
        "match_score": final_score,
        "language_req": lang_label,
        "extracted_pay": compensation_info["display"],
        "matched_keywords": matched_keywords[:8],
        "why_fits": why_fits,
        "commute": commute_info,
        "compensation": compensation_info,
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
    # Keep top 5 bullets so CV fits cleanly on strict 1 A4 page
    chosen_bullets = [b["html"] for _, b in scored_bullets[:5]]

    # Tailor core skills order
    all_skills = list(profile["skills"]["core"])
    if cat_id == "ai_automation":
        all_skills.sort(key=lambda s: 0 if ("AI" in s or "Automation" in s or "Vector" in s) else 1)
    elif cat_id == "product_management":
        all_skills.sort(key=lambda s: 0 if ("Product" in s or "Quantitative" in s) else 1)

    # Build concise, high-impact Cover Letter paragraphs (Strict 1-Page A4 Guarantee ~220 words)
    if cat_id == "ai_automation":
        project_highlight = (
            "I drive the rollout and tuning of our AI voice bot across 9 markets (routing millions of calls and lifting answer rates to 85%), while managing knowledge bases for a chatbot handling 30,000+ monthly conversations. "
            "To streamline model evaluation, I built an internal AI QA web tool with bulk-review pipelines and REST API automations."
        )
    elif cat_id == "product_management":
        project_highlight = (
            "I helped scale our conversational AI products across 9 international markets, routing millions of calls while improving answer rates by 20% and booking conversion to 57.8%. "
            "To support our operational workflows, I designed and shipped an internal AI QA evaluation web tool with bulk-review pipelines and a centralized customer review portal."
        )
    elif cat_id == "cx_operations":
        project_highlight = (
            "I supported scaling our AI voice bot across 9 markets to route millions of calls (raising inbound answer rates from 65% to 85%), while maintaining retrieval knowledge bases for an AI chatbot handling 30,000+ monthly inquiries. "
            "To empower operational teams, I built an automated multi-market knowledge base and custom REST API communication utilities."
        )
    else:  # project_management default
        project_highlight = (
            "I supported the rollout of an AI voice bot across 9 markets routing millions of calls and lifting answer rates by 20%. "
            "I also oversee knowledge architecture for an AI chatbot handling 30,000+ monthly inquiries, and built internal web tools—including an AI QA evaluation platform and automated REST API offer engines—to standardize team delivery."
        )

    paragraphs = [
        (
            f"I am writing to apply for the {job_title} role at {company}. "
            f"With a Bachelor’s in Digital Product Management, ongoing Master’s studies in International Business Management in Berlin, and hands-on experience at Auto1 Group scaling AI tools and data workflows, "
            f"I combine analytical rigor with proactive builder execution to deliver immediate value to your team."
        ),
        (
            f"In my current role as a Junior Project Manager at Auto1 Group in Berlin, I collaborate closely with product managers, engineers, and regional leads across nine European markets. "
            f"{project_highlight}"
        ),
        (
            f"Beyond daily operations, I thrive on untangling disorganized data and turning operational friction into clean, repeatable processes. "
            f"I write SQL queries in Redash and build dashboards in Looker Studio, Tableau, and Excel to provide reliable metrics. When off-the-shelf software falls short, I prototype lightweight internal tools using JavaScript and REST APIs. "
            f"Working in an international Berlin environment, I communicate fluently in English (C1/C2) and Spanish (native), with working German (B1)."
        ),
        (
            f"What particularly excites me about {company} is the opportunity to bring this blend of product operations discipline, SQL analytics, and builder execution to your team in the {job_title} role. "
            f"Thank you for your time and consideration—I look forward to discussing how I can contribute in an interview."
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
