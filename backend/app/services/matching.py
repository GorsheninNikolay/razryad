import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Путь к справочнику навыков.
#
# ВАЖНО: путь нельзя задавать относительно текущего каталога. Приложение и тесты
# запускаются из `backend/` (см. Makefile), и `Path("content/skills.json")` там не
# существует — парсер молча возвращал пустой список, то есть разбор потребности
# переставал работать незаметно. Ищем файл в порядке приоритета:
#   1) переменная окружения RAZRYAD_CONTENT_DIR
#   2) корень репозитория относительно самого модуля (backend/app/services/ -> ../../..)
#   3) текущий каталог (на случай нестандартного запуска)
def _resolve_skills_file() -> Path:
    candidates: List[Path] = []
    env_dir = os.environ.get("RAZRYAD_CONTENT_DIR")
    if env_dir:
        candidates.append(Path(env_dir) / "skills.json")
    repo_root = Path(__file__).resolve().parents[3]
    candidates.append(repo_root / "content" / "skills.json")
    candidates.append(Path("content/skills.json"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    logger.warning(
        "Справочник навыков не найден, разбор потребности вернёт пустой стек. "
        "Проверены пути: %s", ", ".join(str(c) for c in candidates)
    )
    return candidates[1]


SKILLS_FILE = _resolve_skills_file()

def _load_skills() -> Dict[str, dict]:
    if not SKILLS_FILE.exists():
        return {}
    try:
        with open(SKILLS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # The dictionary has 'skills' list
            skills_list = data.get("skills", [])
            return {s["id"]: s for s in skills_list}
    except Exception:
        return {}

SKILLS_DB = _load_skills()

def normalize_text(text: str) -> str:
    """Normalize text: lower, replace ё->е, pad punctuation with spaces for word boundaries."""
    if not text:
        return ""
    text = text.lower().replace("ё", "е")
    # preserve important chars, but pad around them so regex \b works or we can split
    # actually, \b works well if we just do standard regex search.
    # To support things like c++, c# - we should not replace them.
    return text

def build_skill_patterns():
    patterns = []
    for skill_id, skill in SKILLS_DB.items():
        aliases = skill.get("aliases", [])
        name = skill.get("name", "")
        # base names
        terms = [name] + aliases
        # clean terms
        terms = [t.lower().replace("ё", "е") for t in terms if t]
        # remove duplicates
        terms = list(set(terms))
        
        # Build regex for each term
        # If term has len > 4, allow up to 4 chars ending match
        skill_patterns = []
        for term in terms:
            escaped = re.escape(term)
            if len(term) > 4:
                if re.search(r'[а-я]', term):
                    base = term[:-2] if len(term) > 5 else term[:-1]
                    p = r'\b' + re.escape(base) + r'[а-яa-z]{0,4}\b'
                    skill_patterns.append(p)
                else:
                    skill_patterns.append(r'\b' + escaped + r'\b')
            else:
                if term in ("c++", "c#", "f#"):
                    # \b doesn't work after non-word chars
                    skill_patterns.append(r'(?<!\w)' + escaped + r'(?!\w)')
                else:
                    skill_patterns.append(r'\b' + escaped + r'\b')
                    
        patterns.append((skill_id, skill_patterns))
    return patterns

SKILL_PATTERNS = build_skill_patterns()

def parse_need_text(text: str) -> Dict[str, Any]:
    """Parse text and extract skills from dictionary."""
    text_norm = normalize_text(text)
    
    found_skills = []
    for skill_id, patterns in SKILL_PATTERNS:
        matched = False
        for p in patterns:
            if re.search(p, text_norm):
                matched = True
                break
        if matched:
            found_skills.append(skill_id)
            
    # Remove duplicates
    found_skills = list(set(found_skills))
    
    return {
        "must_have_skills": found_skills,
        "nice_to_have_skills": [],
        "confidence": 0.8
    }

def calculate_rank(candidate, fsp_index: float, fresh_days: int, activity_score: float = 0.5) -> float:
    """
    Rank(c) = 0.55·θ̂_norm + 0.25·FSP + 0.10·fresh + 0.10·activity
    """
    import math
    
    theta_norm = getattr(candidate, 'theta_norm', 0.5)
    
    fresh = math.exp(-fresh_days / 45.0)
    
    rank = 0.55 * theta_norm + 0.25 * fsp_index + 0.10 * fresh + 0.10 * activity_score
    return rank

def calculate_match(candidate, need_profile: dict, fsp_pool_percentile: float = 0.0, fsp_pool_variance_zero: bool = False) -> dict:
    """
    Match(c,n) = 100·(0.10·A_grade + 0.50·A_skills + 0.15·A_fsp + 0.10·A_fresh + 0.10·A_context + 0.05·A_avail)
    """
    import math
    
    # 1. A_grade
    # candidate grade vs need grade
    c_grade = getattr(candidate, 'grade', 1)
    n_grade_min = need_profile.get('grade_min', 1)
    n_grade_max = need_profile.get('grade_max', 5)
    is_confirmed = getattr(candidate, 'is_confirmed', False)
    
    a_grade = 0.0
    if n_grade_min <= c_grade <= n_grade_max:
        a_grade = 1.0 if is_confirmed else 0.7
    elif c_grade > n_grade_max:
        a_grade = 0.8 if is_confirmed else 0.5
    else:
        a_grade = 0.2
        
    # 2. A_skills
    must_have = need_profile.get('must_have_skills', [])
    nice_to_have = need_profile.get('nice_to_have_skills', [])
    c_skills = getattr(candidate, 'skills', [])
    
    sum_w_covered = 0.0
    sum_w_all = 0.0
    
    uncovered_must = 0
    
    for s in must_have:
        # demand lookup
        demand = 0.5
        if s in SKILLS_DB:
            demand = SKILLS_DB[s].get('demand', 0.5)
        rarity = 1.0 - 0.35 * demand
        w = 1.0 * rarity
        sum_w_all += w
        if s in c_skills:
            sum_w_covered += w
        else:
            uncovered_must += 1
            
    for s in nice_to_have:
        demand = 0.5
        if s in SKILLS_DB:
            demand = SKILLS_DB[s].get('demand', 0.5)
        rarity = 1.0 - 0.35 * demand
        w = 0.5 * rarity
        sum_w_all += w
        if s in c_skills:
            sum_w_covered += w
            
    penalty = 1.0
    if uncovered_must > 0:
        penalty = max(0.4, 1.0 - 0.15 * uncovered_must)
        
    a_skills = (sum_w_covered / sum_w_all * penalty) if sum_w_all > 0 else 1.0
    
    # 3. A_fsp
    # fsp_pool_percentile from 0 to 1
    # §5.4: if pool variance is 0, redistribute weight
    weight_grade = 0.10
    weight_skills = 0.50
    weight_fsp = 0.15
    
    a_fsp = fsp_pool_percentile
    
    if fsp_pool_variance_zero:
        weight_grade += 0.10
        weight_skills += 0.05
        weight_fsp = 0.0
        
    # 4. A_fresh
    fresh_days = getattr(candidate, 'fresh_days', 10)
    a_fresh = math.exp(-fresh_days / 45.0)
    
    # 5. A_context
    a_context = getattr(candidate, 'context_score', 0.8)
    
    # 6. A_avail
    a_avail = getattr(candidate, 'avail_score', 1.0)
    
    score = 100.0 * (weight_grade * a_grade + weight_skills * a_skills + weight_fsp * a_fsp + 0.10 * a_fresh + 0.10 * a_context + 0.05 * a_avail)
    
    explain = {
        "priority_match": "skills",  # Show what gave the most points
        "grade_qualifier": "Подтвержденный грейд" if a_grade == 1.0 else ("Предварительный грейд" if a_grade == 0.7 else "Не в диапазоне"),
        "grade_match": a_grade,
        "skills_matched": [s for s in must_have + nice_to_have if s in c_skills],
        "skills_missing": [s for s in must_have if s not in c_skills],
        "fsp_highlights": [],
        "freshness": fresh_days
    }
    
    return {
        "score": score,
        "explain": explain
    }
