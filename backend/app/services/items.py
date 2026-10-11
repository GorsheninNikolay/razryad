"""Calibrated pool, taxonomy blueprint and bounded randomesque CAT selection."""
import json, math, random
from pathlib import Path
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import Item, ItemVersion, Competency, Specialization, AssessmentSession, SessionItem, ItemExposure

# services/items.py -> app -> backend; taxonomy is in repository root/content.
TAXONOMY = Path(__file__).resolve().parents[3] / 'content' / 'taxonomy.json'
R_MAX = .15

def blueprint(code: str) -> dict[str, float]:
    with TAXONOMY.open(encoding='utf8') as f: data = json.load(f)
    spec = next((s for s in data['specializations'] if s['id'] == code), None)
    if not spec: raise ValueError('Unknown specialization: ' + code)
    return {c['id']: float(c['weight']) for c in spec['competencies']}

def probability(theta: float, a: float, b: float) -> float:
    z = max(-40., min(40., a * (theta-b)))
    return 1 / (1 + math.exp(-z))

def information(theta: float, a: float, b: float) -> float:
    p = probability(theta, a, b)
    return a*a*p*(1-p)

def load_items(db: Session, specialization_id):
    """Load active calibrated ORM items and their current versions, never serialize answers to clients."""
    return [(i, v) for i in db.query(Item).filter_by(specialization_id=specialization_id, status='active').all()
            if i.discrimination is not None and i.difficulty is not None and i.discrimination >= .5
            for v in i.versions if v.is_current]

def public_content(content: dict) -> dict:
    """Whitelist public presentation fields; unknown content is never implicitly disclosed."""
    return {k: content[k] for k in ('stem', 'question', 'options', 'code', 'language', 'instructions', 'format') if k in content}

def choose_item(db: Session, session: AssessmentSession, *, rng=None):
    """Select available item by Fisher info within taxonomy shares; anchor first.

    Strict exposure cap: for N sessions in the rolling 30-day window, an item's
    count after selection may not exceed ceil(.15*N). An empty eligible bank fails
    closed instead of relaxing either content coverage or exposure constraints.
    """
    from datetime import datetime, timedelta, timezone
    rng = rng or random
    spec = db.get(Specialization, session.specialization_id)
    weights = blueprint(spec.code)
    comps = {c.id: c.code.removeprefix(spec.code + '-') for c in db.query(Competency).filter_by(specialization_id=spec.id)}
    selected = db.query(SessionItem).filter_by(session_id=session.id).order_by(SessionItem.sequence).all()
    used = {x.item_id for x in selected}
    counts = Counter(comps.get(db.get(Item, x.item_id).competency_id) for x in selected)
    seq = len(selected)
    max_items = 18
    # A session reserves two anchor slots; at least one if the bank has one.
    anchor_pool = [(i,v) for i,v in load_items(db, session.specialization_id) if i.is_anchor and i.id not in used]
    anchors_first = seq < min(2, len(anchor_pool) + sum(db.get(Item, x.item_id).is_anchor for x in selected))
    now = datetime.now(timezone.utc)
    window = now - timedelta(days=30)
    sessions = db.query(AssessmentSession).filter(AssessmentSession.specialization_id == session.specialization_id,
                AssessmentSession.started_at >= window).count()
    capacity = max(1, math.ceil(R_MAX * max(1, sessions)))
    eligible = []
    for item, version in load_items(db, session.specialization_id):
        code = comps.get(item.competency_id)
        if code not in weights or item.id in used or bool(item.is_anchor) != anchors_first: continue
        shown = db.query(func.count(SessionItem.id)).join(AssessmentSession, SessionItem.session_id == AssessmentSession.id).filter(
            SessionItem.item_id == item.id, AssessmentSession.started_at >= window).scalar() or 0
        exposure = db.query(ItemExposure).filter_by(item_id=item.id).order_by(ItemExposure.window_end.desc()).first()
        explicit_limit = version.content.get('exposure_limit') if isinstance(version.content, dict) else None
        if shown >= capacity or (explicit_limit is not None and shown >= int(explicit_limit)): continue
        # Select the most underrepresented weighted competence first, allowing
        # higher-information random choice among that competence's candidates.
        remaining = max_items - seq
        deficit = weights[code] * max_items - counts[code]
        if counts[code] >= math.ceil(weights[code]*max_items): continue
        eligible.append((deficit, information(session.current_theta, item.discrimination, item.difficulty), item, version))
    if not eligible: return None
    largest = max(x[0] for x in eligible)
    eligible = sorted((x for x in eligible if x[0] >= largest - .01), key=lambda x:x[1], reverse=True)
    _, info, item, version = rng.choice(eligible[:5])
    return item, version, info
