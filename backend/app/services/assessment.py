"""2PL EAP posterior and auditable assessment grade decisions."""
import math
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.models import (AssessmentSession, SessionResponse, SessionItem, Item, Grade,
    AbilityEstimate, CategoryAssignment, GradeHistory)
from app.services.items import probability

GRID = tuple(-4 + .05*i for i in range(161))
# Symmetric cuts separate five levels approximately 0.7 theta apart; these are
# policy thresholds, not empirical calibration, and should be validated in cohorts.
CUTS = {'intern':-1.2, 'junior':-.4, 'middle':.3, 'senior':1.1, 'lead':1.9}
PRIORS = {'intern':-1.5, 'junior':-.75, 'middle':0., 'senior':.8, 'lead':1.6}
# Hysteresis is deliberately stricter than initial assignment: a noisy retake
# must provide 85% posterior evidence before changing an already confirmed grade.
# Keep these overridable by Settings when deployed (defaults preserve the brief).
INITIAL_GRADE_CONFIDENCE = float(os.getenv('INITIAL_GRADE_CONFIDENCE', '0.70'))
CHANGE_GRADE_CONFIDENCE = float(os.getenv('CHANGE_GRADE_CONFIDENCE', '0.85'))

def decide_grade(grades, probs, prior=None, prior_confirmed=False):
    """Return (grade, confirmed, reason, borderline, offered_lower).

    Primary assignment uses P(theta > cut) >= .70. A confirmed prior grade is
    sticky: upgrades require .85 evidence for the new cut. A lower result never
    automatically downgrades a confirmed grade: the prior grade is retained and
    a lower-grade assessment is offered explicitly, per the brief's §2.3 rule.
    """
    ordered = sorted(grades, key=lambda g:g.level)
    verified=max((g for g in ordered if probs.get(g.code,0) >= INITIAL_GRADE_CONFIDENCE),
                 key=lambda g:g.level, default=ordered[0])
    borderline=any(.60 <= probs.get(g.code,0) < INITIAL_GRADE_CONFIDENCE for g in ordered)
    if not prior or not prior_confirmed:
        return verified, True, 'Подтверждено адаптивным тестом', borderline, (verified.code if prior and verified.level < prior.level else None)
    if verified.level > prior.level:
        if probs.get(verified.code, 0) >= CHANGE_GRADE_CONFIDENCE:
            return verified, True, 'Повышение подтверждено с гистерезисом (P≥0.85)', borderline, None
        return prior, True, 'Без изменений: для повышения требуется P≥0.85', borderline, None
    if verified.level < prior.level:
        return prior, True, ('Без изменений: подтверждённый грейд сохраняется; '
                             'можно добровольно пройти тест на грейд ниже'), borderline, verified.code
    return prior, True, 'Без изменений: грейд подтверждён повторно', borderline, None

def posterior(observations, prior_mean=0.):
    """Numerically normalized EAP posterior on [-4,4], step .05."""
    logs = []
    for t in GRID:
        ll = -.5*(t-prior_mean)**2
        for a,b,x in observations:
            p = max(1e-12, min(1-1e-12, probability(t,a,b)))
            ll += math.log(p if x else 1-p)
        logs.append(ll)
    peak = max(logs)
    ws = [math.exp(x-peak) for x in logs]
    norm = sum(ws)
    ws = [x/norm for x in ws]
    theta = sum(t*w for t,w in zip(GRID,ws))
    se = math.sqrt(sum((t-theta)**2*w for t,w in zip(GRID,ws)))
    return theta,se,ws

def probabilities(weights):
    return {g:sum(w for t,w in zip(GRID, weights) if t > cut) for g,cut in CUTS.items()}

def observations_for(db: Session, session):
    obs=[]
    for r in db.query(SessionResponse).filter_by(session_id=session.id).order_by(SessionResponse.created_at):
        item=db.get(Item,r.item_id)
        obs.append((item.discrimination,item.difficulty,bool(r.is_correct)))
    return obs

def current_posterior(db, session):
    grade=db.get(Grade,session.target_grade_id)
    return posterior(observations_for(db,session), PRIORS.get(grade.code,0))

def should_stop(session, answered, now=None):
    now=now or datetime.now(timezone.utc)
    expiry=session.expires_at
    if expiry.tzinfo is None: expiry=expiry.replace(tzinfo=timezone.utc)
    return now >= expiry or answered >= settings.CAT_MAX_ITEMS or (answered >= settings.CAT_MIN_ITEMS and session.current_se < settings.CAT_SE_THRESHOLD)

def cooldown_until(db, candidate_id, grade):
    history=db.query(GradeHistory).filter_by(candidate_id=candidate_id).order_by(GradeHistory.created_at.desc()).first()
    if history is None or history.change_type not in ('initial','upgrade','downgrade'): return None
    days=settings.GRADE_CHANGE_COOLDOWN_MIDDLE_PLUS if grade.level >= 2 else settings.GRADE_CHANGE_COOLDOWN_JUNIOR
    start=history.created_at
    if start.tzinfo is None: start=start.replace(tzinfo=timezone.utc)
    until=start+timedelta(days=days)
    return until if until > datetime.now(timezone.utc) else None

def complete(db: Session, session, *, decline_lower=False):
    if session.status == 'completed':
        estimate=db.query(AbilityEstimate).filter_by(assessment_session_id=session.id).first()
        assignment=db.query(CategoryAssignment).filter_by(candidate_id=session.candidate_id).first()
        return result(session,estimate,assignment)
    theta,se,weights=current_posterior(db,session)
    probs=probabilities(weights)
    grades=db.query(Grade).order_by(Grade.level).all()
    verified=max((g for g in grades if probs.get(g.code,0)>=.70), key=lambda g:g.level, default=grades[0])
    target=db.get(Grade,session.target_grade_id)
    existing=db.query(CategoryAssignment).filter_by(candidate_id=session.candidate_id).first()
    prior=db.get(Grade,existing.grade_id) if existing else None
    failed=verified.level < target.level
    # Existing confirmed categories use hysteresis; unconfirmed initial tests
    # retain the brief's lower-grade offer and preliminary-category behavior.
    if prior and existing.is_confirmed and target.level < prior.level and verified.level >= target.level:
        # Deliberate lower-grade attempt is the ONLY downgrade path. Passing the
        # explicitly chosen threshold confirms that level; a failed attempt keeps
        # the existing confirmed category.
        chosen=target; confirmed=True
        reason='Добровольный тест на грейд ниже пройден; грейд изменён по выбору кандидата'
        borderline=any(.60 <= probs.get(g.code,0) < .70 for g in grades); offered=None
    elif prior and existing.is_confirmed:
        chosen, confirmed, reason, borderline, offered = decide_grade(
            grades, probs, prior=prior, prior_confirmed=True)
    elif failed and decline_lower:
        chosen=target if not prior else prior; confirmed=False
        reason='Отказ от теста на грейд ниже; категория предварительная'
        borderline=any(.60 <= probs.get(g.code,0) < .70 for g in grades); offered=None
    elif failed:
        chosen=target if not prior else prior
        confirmed=False
        reason='Заявленный грейд не подтверждён; предложен тест на грейд ниже'
        borderline=any(.60 <= probs.get(g.code,0) < .70 for g in grades); offered=verified.code
    else:
        chosen, confirmed, reason, borderline, offered = decide_grade(grades, probs)
    estimate=AbilityEstimate(candidate_id=session.candidate_id,specialization_id=session.specialization_id,
        assessment_session_id=session.id,theta=theta,se=se,grade_probabilities=probs)
    db.add(estimate)
    if existing:
        old_id=existing.grade_id
        existing.grade_id=chosen.id; existing.specialization_id=session.specialization_id
        existing.is_confirmed=confirmed; existing.confirmed_at=datetime.now(timezone.utc) if confirmed else None
        assignment=existing
    else:
        old_id=None
        assignment=CategoryAssignment(candidate_id=session.candidate_id,specialization_id=session.specialization_id,
            grade_id=chosen.id,is_confirmed=confirmed, confirmed_at=datetime.now(timezone.utc) if confirmed else None)
        db.add(assignment)
    kind='initial' if not old_id else ('upgrade' if prior.level < chosen.level else 'downgrade' if prior.level > chosen.level else 'reconfirm')
    db.add(GradeHistory(candidate_id=session.candidate_id,specialization_id=session.specialization_id,
        old_grade_id=old_id,new_grade_id=chosen.id,change_type=kind,trigger='assessment',assessment_session_id=session.id,reason=reason))
    session.status='completed';session.completed_at=datetime.now(timezone.utc)
    session.final_theta=theta;session.final_se=se;session.assigned_grade_id=chosen.id
    db.flush()
    # ORM relationships may still reference the previous category until expired.
    db.expire(assignment, ['grade', 'specialization'])
    db.commit()
    return result(session,estimate,assignment, reason, borderline, offered)

def result(session,estimate,assignment,reason=None,borderline=None,offered=None):
    p=estimate.grade_probabilities if estimate else {}
    return {'session_id':str(session.id),'final_theta':session.final_theta,'final_se':session.final_se,
        'assigned_grade_id':str(session.assigned_grade_id),'assigned_grade':assignment.grade.code,
        'category':{'specialization':assignment.specialization.code,'grade':assignment.grade.code},
        'is_confirmed':assignment.is_confirmed,
        'grade_probabilities':p,'borderline':borderline if borderline is not None else any(.60<=v<.70 for v in p.values()),
        'reason':reason,'offered_lower_grade':offered}
