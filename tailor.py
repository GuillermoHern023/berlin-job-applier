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


def detect_language_requirement(title: str, description: str) -> Tuple[str, int, bool]:
    """
    Evaluates whether a job is realistically accessible for Guillermo
    (Native Spanish, C1/C2 Fluent English, B1 Working German).
    Returns (label, score_adjustment, is_english_b1_friendly)
    """
    title_l = title.lower()
    text = f"{title} {description}".lower()

    # 1. Foreign languages Guillermo doesn't speak
    other_langs = [
        "nordic", "swedish", "danish", "norwegian", "finnish", "arabic", "dutch",
        "polish", "italian", "turkish", "russian", "japanese", "chinese", "mandarin",
        "korean", "portuguese", "czech", "hungarian", "greek",
    ]
    for ol in other_langs:
        if ol in title_l:
            return (f"Requires {ol.capitalize()}", -40, False)

    if "spanish" in title_l or "spanisch" in title_l:
        return ("Spanish + English (Native Fit!)", +20, True)

    # 2. Strict C1 / C2 / Fluent / Verhandlungssicher German requirement (German and English phrasings)
    strict_c1_patterns = [
        r"verhandlungssicher",
        r"c1[- ]?(?:level|niveau)?",
        r"c2[- ]?(?:level|niveau)?",
        r"mindestens\s+c1",
        r"sehr\s+gute[sn]?\s+deutsch",
        r"deutsch[^\.\n;]{0,40}sehr\s+gut",
        r"sehr\s+gut[^\.\n;]{0,40}deutsch",
        r"flie[ßss]end[^\.\n;]{0,30}deutsch",
        r"deutsch[^\.\n;]{0,30}flie[ßss]end",
        r"deutsch\s+auf\s+muttersprach",
        r"native\s+german",
        r"fluent\s+(?:in\s+)?german",
        r"excellent\s+german",
        r"business\s+fluent\s+german",
        r"very\s+good\s+german",
        r"proficient\s+(?:in\s+)?german",
        r"strong\s+german",
        r"solid\s+german",
        r"german\s+language\s+skills",
        r"german\s*(?:skills|kenntnisse)?[^\.\n;]{0,35}(?:very\s+good|fluent|c1|c2|excellent|strong|required|essential|mandatory|a\s+must)",
        r"(?:very\s+good|fluent|c1|c2|excellent|strong|solid)\s+german",
        r"good\s+command\s+of\s+german",
        r"german\s+is\s+(?:required|mandatory|essential|a\s+must)",
        r"deutschkenntnisse\s+in\s+wort\s+und\s+schrift",
        r"gute\s+deutschkenntnisse",
        r"fundierte\s+deutschkenntnisse",
        r"sichere\s+deutschkenntnisse",
        r"flie[ßss]ende\s+deutschkenntnisse",
    ]
    for pat in strict_c1_patterns:
        if re.search(pat, text):
            return ("Requires C1/Fluent German (B1 Risk)", -35, False)

    # 3. German-only domain roles (construction, legal, taxes, bookkeeping, traditional customer care)
    german_domain_roles = [
        "bauprojektmanagement", "bauingenieur", "bauleitung", "tiefbau", "hochbau",
        "immobilien", "buchhaltung", "rechnungswesen", "finanzbuchhaltung", "steuern",
        "steuerberatung", "sachbearbeiter", "jurist", "rechtsberatung", "kundenservice",
        "kundenbetreuung", "vertrieb", "einkauf", "lohnabrechnung", "gehaltsabrechnung",
        "arbeitsrecht", "verwaltungsangestellt"
    ]
    if any(dr in title_l for dr in german_domain_roles):
        return ("German Domain (Construction/Admin/Legal - B1 Risk)", -35, False)

    # 4. Handle sparse or missing descriptions
    if not description or len(description.strip()) < 60:
        de_title_indicators = ["werkstudent", "praktikant", "bau-", "management", "berater", "sachbearbeiter", "assistenz", "leiter", "betreuung", "vertrieb", "projekt"]
        en_title_indicators = ["working student", "intern", "internship", "product manager", "engineer", "software", "ai", "developer", "designer", "international", "english"]
        has_de_title = any(k in title_l for k in de_title_indicators)
        has_en_title = any(k in title_l for k in en_title_indicators)
        if has_de_title and not has_en_title:
            return ("Requires German (Title in German / No Desc)", -35, False)
        elif has_en_title:
            return ("English Title (Pending Full Text)", +5, True)
        else:
            return ("German Working Language (B1 Risk)", -20, False)

    # 5. Analyze language density
    de_words = len(re.findall(r"\b(und|oder|für|mit|deine|aufgaben|wir|suchen|arbeit|studium|über|uns|dich|bei|von|nach|zu|im|in|ein|eine|einen|einem|einer|als|wirst|du|bist|hast|kannst|dein|profil|anforderungen|kenntnisse|erfahrung|bereich|unternehmen)\b", text))
    en_words = len(re.findall(r"\b(and|with|your|tasks|we|looking|working|student|experience|team|about|you|the|for|our|will|are|have|role|skills|work|opportunity|join|who|what|offer)\b", text))

    # If explicitly English friendly or German optional
    if re.search(r"german\s*(?:is\s+a\s+plus|is\s+beneficial|is\s+optional|not\s+required|b1|basic)", text) or re.search(r"working\s+language\s+(?:is\s+)?english", text):
        return ("English + Basic/B1 German OK", +15, True)

    if en_words > de_words * 1.5 or (en_words >= 15 and de_words < 5):
        return ("English Friendly (B1 OK)", +15, True)

    if de_words > en_words:
        return ("German Working Language (B1 Challenging)", -25, False)

    return ("Requires German (B1 Challenging)", -20, False)


BENEFIT_TAXONOMY = [
    {
        "category": "transit",
        "icon": "🚆",
        "label": "Deutschlandticket / BVG Subsidy",
        "patterns": [r"deutschlandticket", r"jobticket", r"bvg", r"firmenticket", r"fahrtkosten", r"mobilität", r"transit pass", r"subsidized transport", r"jobrad", r"swapfiets", r"bike leasing"],
    },
    {
        "category": "remote",
        "icon": "🏠",
        "label": "Home Office / Hybrid",
        "patterns": [r"home[\s-]?office", r"mobiles arbeiten", r"remote", r"hybrid", r"work from home", r"telearbeit"],
    },
    {
        "category": "flexibility",
        "icon": "⏰",
        "label": "Flexible Working Hours",
        "patterns": [r"flexible\s+arbeitszeiten", r"gleitzeit", r"flexible\s+hours", r"flexitime", r"vertrauensarbeitszeit"],
    },
    {
        "category": "hardware",
        "icon": "💻",
        "label": "MacBook / Tech Equipment",
        "patterns": [r"macbook", r"apple", r"modernes? equipment", r"laptop", r"choose your (?:own )?device"],
    },
    {
        "category": "wellness",
        "icon": "🏋️",
        "label": "Urban Sports Club / Wellpass",
        "patterns": [r"urban sports club", r"wellpass", r"gympass", r"fitness", r"gesundheitsförderung", r"sportangebote", r"egym"],
    },
    {
        "category": "growth",
        "icon": "🎓",
        "label": "Learning & Training Budget",
        "patterns": [r"weiterbildung", r"learning budget", r"entwicklungsmöglichkeiten", r"schulungen", r"training budget", r"mentoring", r"buddy"],
    },
    {
        "category": "food",
        "icon": "🍕",
        "label": "Free Drinks, Coffee & Snacks",
        "patterns": [r"obstkorb", r"free drinks", r"kaffee", r"snacks", r"barista", r"getränke", r"müsli", r"lunch", r"essenszuschuss"],
    },
    {
        "category": "discounts",
        "icon": "🛍️",
        "label": "Corporate Benefits & Discounts",
        "patterns": [r"corporate benefits", r"mitarbeiterrabatt", r"employee discounts", r"vergünstigungen"],
    },
    {
        "category": "vacation",
        "icon": "🌴",
        "label": "28–30 Days Paid Vacation",
        "patterns": [r"(?:28|29|30)\s+tage\s+urlaub", r"urlaubstage", r"paid time off", r"pto"],
    },
    {
        "category": "pension",
        "icon": "💰",
        "label": "Company Pension (bAV)",
        "patterns": [r"betriebliche altersvorsorge", r"\bbav\b", r"vermögenswirksame leistungen"],
    },
    {
        "category": "events",
        "icon": "🎉",
        "label": "Team Events & Offsites",
        "patterns": [r"teamevents?", r"sommerfest", r"weihnachtsfeier", r"after[\s-]?work", r"team offsite"],
    },
]


def extract_job_benefits(description: str, title: str = "", company: str = "") -> List[Dict[str, str]]:
    text = f"{title} {description}".lower()
    comp_l = company.lower()
    detected = []

    for b in BENEFIT_TAXONOMY:
        for pat in b["patterns"]:
            if re.search(pat, text):
                detected.append({
                    "category": b["category"],
                    "icon": b["icon"],
                    "label": b["label"]
                })
                break

    # Enterprise perks fallback (SAP, Amazon, etc. famously provide Deutschlandticket & hardware)
    if "sap" in comp_l:
        cats = [d["category"] for d in detected]
        if "transit" not in cats:
            detected.append({"category": "transit", "icon": "🚆", "label": "Deutschlandticket (SAP Perk)"})
        if "hardware" not in cats:
            detected.append({"category": "hardware", "icon": "💻", "label": "High-End Laptop & Tech"})

    return detected


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
    - Also evaluates 'pays_min_16': whether the wage meets or exceeds Guillermo's €16/hour target.
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
                pays_min_16 = (high >= 16.0)
                return {
                    "is_estimated": False,
                    "badge": badge,
                    "display": f"{badge} (Listed)",
                    "range_text": f"€{low:.2f} – €{high:.2f} / hour",
                    "monthly_estimate": f"~€{monthly_low:,} – €{monthly_high:,}/mo (20h)".replace(",", "."),
                    "source": "Employer Listed",
                    "pays_min_16": pays_min_16,
                }
            elif "month" in raw_salary.lower() or (low >= 1000 and low <= 8000):
                h_low_20 = round(low / 86.67)
                h_high_20 = round(high / 86.67)
                h_low_40 = round(low / 173.33, 1)
                h_high_40 = round(high / 173.33, 1)
                hourly_part = f"~€{h_low_20}/h" if h_low_20 == h_high_20 else f"~€{h_low_20}–{h_high_20}/h"
                badge = f"💰 €{int(low):,}–€{int(high):,}/mo ({hourly_part})".replace(",", ".")
                pays_min_16 = (h_high_20 >= 16)
                return {
                    "is_estimated": False,
                    "badge": badge,
                    "display": f"{badge} (Listed)",
                    "range_text": f"{hourly_part} (at 20h/wk) · €{int(low):,} – €{int(high):,} / month".replace(",", "."),
                    "monthly_estimate": f"€{int(low):,} – €{int(high):,}/mo (= {hourly_part} @ 20h student | ~€{h_low_40}–{h_high_40}/h @ 40h)".replace(",", "."),
                    "source": "Employer Listed",
                    "pays_min_16": pays_min_16,
                }
            elif low > 20000:
                h_low_ft = round(low / 2080)
                h_high_ft = round(high / 2080)
                hourly_part = f"~€{h_low_ft}/h" if h_low_ft == h_high_ft else f"~€{h_low_ft}–{h_high_ft}/h"
                badge = f"💰 €{int(low/1000)}k–{int(high/1000)}k/yr ({hourly_part})"
                return {
                    "is_estimated": False,
                    "badge": badge,
                    "display": f"{badge} (Listed)",
                    "range_text": f"{hourly_part} (Full-time) · €{int(low):,} – €{int(high):,} / year".replace(",", "."),
                    "monthly_estimate": f"~€{int(low/12):,} – €{int(high/12):,}/mo (= {hourly_part})".replace(",", "."),
                    "source": "Employer Listed",
                    "pays_min_16": True,
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
            pays_min_16 = (rate >= 16.0)
            return {
                "is_estimated": False,
                "badge": badge,
                "display": f"{badge} (Listed in text)",
                "range_text": f"€{rate:.2f}/h",
                "monthly_estimate": f"~€{int(rate * 86.6):,}/mo (20h)".replace(",", "."),
                "source": "Job Description",
                "pays_min_16": pays_min_16,
            }
        except Exception:
            pass

    # 3. Calculate Realistic Berlin Benchmark Estimate
    is_enterprise = any(k in company_l for k in ["sap", "amazon", "google", "microsoft", "deloitte", "pwc", "kpmg", "mckinsey", "zalando", "check24", "universal music", "databricks", "tesla", "siemens"])
    is_scaleup = any(k in company_l for k in ["auto1", "delivery hero", "n26", "contentful", "personio", "hellofresh", "jobbird", "tier", "flink", "trade republic", "tiktok"])
    is_tech_ai = any(k in title_l for k in ["ai", "machine learning", "data analytics", "sql", "sap", "cloud", "software", "infrastructure", "python"]) or \
                 (any(k in desc_l for k in ["machine learning", "sql", "redash", "tableau", "looker", "python", "full-stack"]) and not any(k in title_l for k in ["bau", "immobilien", "handwerk", "reinigung"]))

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
        pays_min_16 = (high_h >= 17) or (low_h >= 16) or (is_enterprise or is_scaleup or is_tech_ai)
        return {
            "is_estimated": True,
            "badge": badge,
            "display": f"{badge} (~€{monthly_low}–€{monthly_high}/mo)",
            "range_text": f"~€{low_h} – €{high_h} / hour (Berlin Tech Benchmark)",
            "monthly_estimate": f"~€{monthly_low} – €{monthly_high} / month (at 20h/wk)",
            "source": "Berlin Benchmark Estimate",
            "tier": "Enterprise (+premium)" if is_enterprise else ("Tech / Scale-up" if (is_scaleup or is_tech_ai) else "Standard Berlin"),
            "pays_min_16": pays_min_16,
        }

    # B) Intern / Praktikum
    if any(k in title_l for k in ["intern", "praktikant", "praktikum", "internship"]):
        monthly_low = 1300 if not is_enterprise else 1700
        monthly_high = 1800 if not is_enterprise else 2200
        h_low_20 = round(monthly_low / 86.67)
        h_high_20 = round(monthly_high / 86.67)
        h_low_40 = round(monthly_low / 173.33, 1)
        h_high_40 = round(monthly_high / 173.33, 1)
        hourly_part = f"~€{h_low_20}/h" if h_low_20 == h_high_20 else f"~€{h_low_20}–{h_high_20}/h"
        badge = f"💰 ~€{monthly_low}–{monthly_high}/mo ({hourly_part})"
        return {
            "is_estimated": True,
            "badge": badge,
            "display": f"{badge} (Internship: ~€{monthly_low}–{monthly_high}/mo)",
            "range_text": f"{hourly_part} (at 20h/wk) · ~€{monthly_low} – €{monthly_high} / month",
            "monthly_estimate": f"~€{monthly_low} – €{monthly_high} / month (= {hourly_part} @ 20h student | ~€{h_low_40}–{h_high_40}/h @ 40h)",
            "source": "Berlin Benchmark Estimate",
            "tier": "Enterprise" if is_enterprise else "Berlin Startup/Tech",
            "pays_min_16": (h_high_20 >= 16),
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
        h_low_ft = round(annual_low * 1000 / 2080)
        h_high_ft = round(annual_high * 1000 / 2080)
        hourly_part = f"~€{h_low_ft}–{h_high_ft}/h"
        badge = f"💰 ~€{annual_low}k–{annual_high}k/yr ({hourly_part})"
        return {
            "is_estimated": True,
            "badge": badge,
            "display": f"{badge} (Junior/Associate)",
            "range_text": f"{hourly_part} (Full-time) · ~€{annual_low}.000 – €{annual_high}.000 / year",
            "monthly_estimate": f"~€{int(annual_low*1000/12):,} – €{int(annual_high*1000/12):,}/mo (= {hourly_part})".replace(",", "."),
            "source": "Berlin Benchmark Estimate",
            "tier": "Junior Tech/Operations",
            "pays_min_16": True,
        }

    # D) Mid-level Specialist / Manager / Consultant
    annual_low = 52
    annual_high = 68
    if is_enterprise:
        annual_low += 10
        annual_high += 15
    h_low_ft = round(annual_low * 1000 / 2080)
    h_high_ft = round(annual_high * 1000 / 2080)
    hourly_part = f"~€{h_low_ft}–{h_high_ft}/h"
    badge = f"💰 ~€{annual_low}k–{annual_high}k/yr ({hourly_part})"
    return {
        "is_estimated": True,
        "badge": badge,
        "display": f"{badge} (Mid-level)",
        "range_text": f"{hourly_part} (Full-time) · ~€{annual_low}.000 – €{annual_high}.000 / year",
        "monthly_estimate": f"~€{int(annual_low*1000/12):,} – €{int(annual_high*1000/12):,}/mo (= {hourly_part})".replace(",", "."),
        "source": "Berlin Benchmark Estimate",
        "tier": "Professional/Manager",
        "pays_min_16": True,
    }


def detect_employment_type(title: str, description: str = "", raw_job_type: str = "") -> Tuple[str, str, bool, int]:
    """
    Classifies the role into student-legal employment contracts vs. full-time:
    - WERKSTUDENT: Working student role (max 20h/wk, student visa legal, tax-advantaged) -> +18 pts
    - INTERNSHIP: Intern / Praktikum (student compatible) -> +12 pts
    - PART_TIME: Teilzeit / Part-time (student compatible if <= 20h) -> +10 pts
    - FULL_TIME: Standard 40h/week Vollzeit contract (NOT legal for full-time enrolled students during semester) -> -25 pts penalty
    Returns: (code, label, is_student_legal, score_adjustment)
    """
    t = (title or "").lower()
    d = (description or "").lower()
    jt = (raw_job_type or "").lower()

    # 1. Explicit Working Student (Werkstudent) in title
    if any(k in t for k in ["werkstudent", "working student", "studentische", "student assistant", "student "]):
        return "WERKSTUDENT", "🎓 Werkstudent (Max 20h/wk)", True, 18
    if "werkstudent" in t or "working student" in t:
        return "WERKSTUDENT", "🎓 Werkstudent (Max 20h/wk)", True, 18

    # 2. Internship / Praktikum in title
    if any(k in t for k in ["intern", "praktikant", "praktikum", "internship", "ixp"]):
        return "INTERNSHIP", "💼 Praktikum / Internship", True, 12

    # 3. Part-Time / Teilzeit
    if any(k in t for k in ["teilzeit", "part-time", "part time"]):
        return "PART_TIME", "⏱️ Teilzeit (Part-Time)", True, 10
    if any(k in jt for k in ["parttime", "part-time", "part_time"]):
        return "PART_TIME", "⏱️ Teilzeit (Part-Time)", True, 10

    # 4. Check description for explicit 20h/week working student contract specifications
    if any(k in d for k in ["werkstudentenvertrag", "working student contract", "bis zu 20 stunden", "bis zu 20h", "max. 20h", "20h/woche", "20 stunden/woche", "während des semesters 20"]):
        return "WERKSTUDENT", "🎓 Werkstudent (Max 20h/wk)", True, 18

    # 5. Full-Time / Vollzeit roles (Junior Manager, Specialist, Associate, Analyst without student qualification)
    return "FULL_TIME", "⚠️ Vollzeit (40h/wk - Not Student-Legal)", False, -25


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

    # 2. Employment Type & Student Legal Check
    contract_code, contract_label, is_student_legal, contract_adj = detect_employment_type(title, description, str(job.get("job_type") or ""))

    # Base score incorporates contract compatibility
    base_score = 52 + contract_adj

    # Add keyword points (capped)
    keyword_bonus = min(25, sum(cat_scores.values()) // 3)
    base_score += keyword_bonus

    # Language check
    lang_label, lang_adj, is_b1_friendly = detect_language_requirement(title, description)
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
    pays_min_16 = compensation_info.get("pays_min_16", True)

    # Sub-€16/h wage penalty: User constraint: "ideally we dont recommend any jobs that pay less than 16 per hour"
    if not pays_min_16:
        base_score -= 30

    final_score = max(10, min(99, base_score))

    # Benefits extraction
    benefits_info = extract_job_benefits(description, title, company)

    return {
        "category_id": best_cat_id,
        "category_label": best_cat_label,
        "match_score": final_score,
        "language_req": lang_label,
        "is_english_friendly": is_b1_friendly,
        "employment_type": contract_code,
        "employment_label": contract_label,
        "is_student_legal": is_student_legal,
        "pays_min_16": pays_min_16,
        "benefits": benefits_info,
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
        if b["id"] == "qa_review_platform" and any(w in desc_lower for w in ["qa", "quality", "audit", "review", "evaluation", "ai", "product", "tool", "n8n"]):
            b_score += 25
        if b["id"] == "faq_voicebot_maintenance" and any(w in desc_lower for w in ["parloa", "elevenlabs", "voice", "speech", "prompt", "faq", "conversational", "stt", "tts"]):
            b_score += 25
        if b["id"] == "kpi_reporting" and any(w in desc_lower for w in ["sql", "redash", "quantitative", "complex", "data", "kpi", "reporting", "analytics"]):
            b_score += 25
        if b["id"] == "contract_amendment_tool" and any(w in desc_lower for w in ["contract", "legal", "document", "form", "pdf", "vertrag", "admin", "process"]):
            b_score += 25
        if b["id"] == "price_lead_email_tool" and any(w in desc_lower for w in ["automation", "api", "rest", "low-code", "email", "crm", "lead", "workflow", "n8n", "freshdesk"]):
            b_score += 25
        if b["id"] == "reviews_portal" and any(w in desc_lower for w in ["customer", "review", "trustpilot", "google", "git", "github", "portal"]):
            b_score += 25
        if b["id"] == "feedback_review_automation" and any(w in desc_lower for w in ["feedback", "branch", "filiale", "nps", "review", "categor", "customer feedback"]):
            b_score += 20
        if b["id"] == "compass_knowledge_base" and any(w in desc_lower for w in ["knowledge", "wiki", "documentation", "confluence", "notion", "search", "assistant"]):
            b_score += 20
        if b["id"] == "overall_impact_summary" and any(w in desc_lower for w in ["impact", "hours", "fte", "efficiency", "initiative", "delivered", "scale"]):
            b_score += 20
        scored_bullets.append((b_score, b))

    scored_bullets.sort(key=lambda x: x[0], reverse=True)
    # Permanently lock voicebot_rollout as #1 and faq_voicebot_maintenance as #2, followed by top 4 tailored concrete project bullets
    b1 = [b["html"] for _, b in scored_bullets if b["id"] == "voicebot_rollout"]
    b2 = [b["html"] for _, b in scored_bullets if b["id"] == "faq_voicebot_maintenance"]
    rest = [b["html"] for _, b in scored_bullets if b["id"] not in ("voicebot_rollout", "faq_voicebot_maintenance")][:4]
    chosen_bullets = b1 + b2 + rest

    # Tailor core skills order
    all_skills = list(profile["skills"]["core"])
    if cat_id == "ai_automation":
        all_skills.sort(key=lambda s: 0 if ("AI" in s or "Automation" in s or "Vector" in s) else 1)
    elif cat_id == "product_management":
        all_skills.sort(key=lambda s: 0 if ("Product" in s or "Quantitative" in s) else 1)

    # Build concise, high-impact Cover Letter paragraphs (Strict 1-Page A4 Guarantee ~220 words)
    if cat_id == "ai_automation":
        project_highlight = (
            "I manage AI chatbot and voicebot prompting, FAQs, and knowledge bases across hundreds of thousands of customer conversations, "
            "and built an internal AI Conversation QA & Evaluation web tool with automated workflows and bulk-review evaluation pipelines."
        )
    elif cat_id == "product_management":
        project_highlight = (
            "I designed and rolled out a centralized Google Reviews & Trustpilot web portal with a one-click approval workflow, "
            "launched a multi-country AI knowledge base with smart search across 9 markets, and built an internal AI Conversation QA evaluation tool."
        )
    elif cat_id == "cx_operations":
        project_highlight = (
            "I built a centralized Google Reviews & Trustpilot web portal with template-based smart reply suggestions and a one-click approval workflow, "
            "automated customer feedback classification across hundreds of European branch locations, and developed automated Price-Lead Offer Email workflows via REST APIs."
        )
    else:  # project_management default
        project_highlight = (
            "I partnered with project managers on SQL (Redash) KPI dashboards, engineered automated contract and document generation tools, "
            "and built an internal AI Conversation QA & Evaluation web platform to standardize cross-market quality."
        )

    paragraphs = [
        (
            f"I am writing to apply for the {job_title} role at {company}. "
            f"With a Bachelor’s in Digital Product Management, ongoing Master’s studies in International Business Management in Berlin, and over two years of hands-on experience at AUTO1 Group scaling AI operations, data reporting, and internal tooling, "
            f"I combine analytical rigor with proactive builder execution to deliver immediate value to your team."
        ),
        (
            f"In my role as Junior Project Manager at AUTO1 Group in Berlin (since 2024, progressing from Intern to Working Student), I collaborate daily across Product, Engineering, and Operations teams in 9 European markets. "
            f"I helped drive the end-to-end rollout and continuous optimization of our AI voice bot (routing millions of calls, increasing inbound answer rates by over 80%, and lifting call-to-booking conversion by over 50%), while shipping a suite of production internal tools and workflow automations. "
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

    # Also sync generated bundles to docs/files/applications and files/applications
    base_dir = OUTPUT_DIR.parent
    for dest_root in [base_dir / "docs" / "files" / "applications", base_dir / "files" / "applications"]:
        target_dir = dest_root / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(cv_pdf_path, target_dir / cv_pdf_path.name)
        shutil.copy2(cl_pdf_path, target_dir / cl_pdf_path.name)

    return {
        "folder": str(job_dir),
        "cv_pdf": str(cv_pdf_path),
        "cover_letter_pdf": str(cl_pdf_path),
        "cv_url": f"files/applications/{folder_name}/{cv_pdf_path.name}",
        "cover_letter_url": f"files/applications/{folder_name}/{cl_pdf_path.name}",
        "tailored": tailored,
    }
