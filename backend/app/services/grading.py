"""Deterministic scoring for the assessment item bank."""
import re
from typing import Any


def _norm(value: Any) -> str:
    text = str(value if value is not None else '').strip().lower()
    return re.sub(r'\s+', ' ', text).strip(' ;\n\t')


def _value(response: Any) -> Any:
    if isinstance(response, dict):
        return response.get('answer', response.get('value', response.get('response', '')))
    return response


def _contains_term(text: str, term: Any) -> bool:
    term = _norm(term)
    return bool(term) and re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text) is not None


def grade_item(item: dict, response: Any) -> tuple[bool, float]:
    value = _value(response)
    if value is None or value == [] or value == {} or not _norm(value):
        return False, 0.0
    fmt = item.get('format', item.get('item_type', 'mcq'))
    payload = item.get('payload') if isinstance(item.get('payload'), dict) else {}
    expected = item.get('answer', item.get('correct_answer', payload.get('correct_answer')))
    text = _norm(value)
    if fmt == 'mcq':
        correct = expected is not None and text == _norm(expected)
        return correct, float(correct)
    if fmt == 'short_answer' and expected is None:
        keywords = item.get('keywords', payload.get('accepted_keywords', [])) or []
        if keywords:
            terms = [term for term in keywords if _norm(term)]
            correct = bool(terms) and all(_contains_term(text, term) for term in terms)
            return correct, float(correct)
    if fmt in ('code_output', 'short_answer', 'sql'):
        options = item.get('acceptable_answers', payload.get('acceptable_answers', [])) or []
        correct = any(_norm(answer) and text == _norm(answer) for answer in [expected, *options])
        return bool(correct), float(correct)
    if fmt in ('open_rubric', 'essay'):
        rubric = item.get('rubric') or payload.get('rubric', [])
        if isinstance(rubric, dict):
            rubric = rubric.get('criteria', [])
        total = sum(float(criterion.get('weight', 1)) for criterion in rubric) or 1.0
        earned = 0.0
        for criterion in rubric:
            terms = criterion.get('synonyms', criterion.get('keywords', [criterion.get('name', '')]))
            terms = terms if isinstance(terms, list) else [terms]
            terms = [term for term in terms if _norm(term)]
            hits = sum(_contains_term(text, term) for term in terms)
            coverage = float(hits > 0) if 'synonyms' in criterion else hits / max(1, len(terms))
            earned += float(criterion.get('weight', 1)) * coverage
        score = earned / total
        return score >= float(item.get('pass_score', .5)), score
    correct = expected is not None and text == _norm(expected)
    return correct, float(correct)


def score_mcq(response, answer):
    return grade_item({'format': 'mcq', 'answer': answer}, response)


def score_code_output(response, answer):
    return grade_item({'format': 'code_output', 'answer': answer}, response)


def score_short_answer(response, answer, acceptable_answers=None):
    return grade_item({'format': 'short_answer', 'answer': answer, 'acceptable_answers': acceptable_answers or []}, response)


def score_open_rubric(response, rubric):
    return grade_item({'format': 'open_rubric', 'rubric': rubric}, response)
