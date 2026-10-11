"""Deterministic scorers for assessment item formats (no external API required)."""
import os, re
from typing import Any

def _norm(v: Any) -> str:
    s = str(v if v is not None else '').strip().lower()
    return re.sub(r'\s+', ' ', s).strip(' ;\n\t')

def _value(response: Any) -> Any:
    if isinstance(response, dict):
        return response.get('answer', response.get('value', response.get('response', '')))
    return response

def _empty(value: Any) -> bool:
    """Empty submissions are always incorrect; numeric zero remains valid."""
    if value is None: return True
    if isinstance(value, dict): return not value or _empty(_value(value))
    if isinstance(value, (str, list, tuple, set)): return len(value) == 0
    return False

def grade_item(item: dict, response: Any) -> tuple[bool, float]:
    """Return (is_correct, score 0..1), with a deterministic rubric fallback."""
    fmt = item.get('format', item.get('item_type', 'mcq'))
    value = _value(response)
    if _empty(value):
        return False, 0.0
    expected = item.get('answer', item.get('correct_answer', item.get('payload', {}).get('correct_answer') if isinstance(item.get('payload'), dict) else None))
    if fmt == 'mcq':
        ok = _norm(value) == _norm(expected)
        return ok, float(ok)
    if fmt in ('code_output', 'short_answer', 'sql'):
        options = item.get('acceptable_answers', item.get('payload', {}).get('acceptable_answers', []) if isinstance(item.get('payload'), dict) else [])
        expected_values = [expected] + list(options or [])
        ok = any(_norm(value) == _norm(x) for x in expected_values)
        return ok, float(ok)
    if fmt in ('open_rubric', 'essay'):
        text = _norm(value)
        rubric = item.get('rubric') or item.get('payload', {}).get('rubric', []) if isinstance(item.get('payload'), dict) else item.get('rubric', [])
        if isinstance(rubric, dict): rubric = rubric.get('criteria', [])
        total = sum(float(c.get('weight', 1)) for c in rubric) or 1.0
        got = 0.0
        for c in rubric:
            terms = c.get('synonyms', c.get('keywords', [c.get('name', '')]))
            terms = terms if isinstance(terms, list) else [terms]
            hits = sum(1 for t in terms if _norm(t) and _norm(t) in text)
            level = min(4, hits)
            got += float(c.get('weight', 1)) * level / 4
        score = got / total
        return score >= float(item.get('pass_score', .5)), score
    return _norm(value) == _norm(expected), float(_norm(value) == _norm(expected))

# Public aliases useful for unit tests and integrations.
def score_mcq(response, answer): return grade_item({'format':'mcq','answer':answer}, response)
def score_code_output(response, answer): return grade_item({'format':'code_output','answer':answer}, response)
def score_short_answer(response, answer, acceptable_answers=None): return grade_item({'format':'short_answer','answer':answer,'acceptable_answers':acceptable_answers or []}, response)
def score_open_rubric(response, rubric): return grade_item({'format':'open_rubric','rubric':rubric}, response)
