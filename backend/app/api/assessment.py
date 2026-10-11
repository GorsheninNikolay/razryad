"""Authenticated one-at-a-time adaptive assessment API."""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, Union, List
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import require_candidate
from app.core.config import settings
from app.models.models import (CandidateProfile, Specialization, Grade, Blueprint, AssessmentSession,
    SessionItem, SessionResponse, ItemVersion, Item, AbilityEstimate, CategoryAssignment, GradeHistory)
from app.services import assessment as engine, items, grading

router=APIRouter()
class StartRequest(BaseModel):
    # Public contract uses stable codes; UUID aliases remain accepted for API
    # compatibility with existing clients.
    specialization: Optional[str] = None
    target_grade: Optional[str] = None
    specialization_id: Optional[UUID] = None
    target_grade_id: Optional[UUID] = None

    # Missing values are resolved from the saved onboarding profile by start().
class AnswerRequest(BaseModel):
    item_id: UUID
    # Frontend sends scalar/list `answer`; response_data dict is legacy API form.
    answer: Optional[Union[int, float, str, List[Any], dict]] = None
    response_data: Optional[Union[dict, int, float, str, List[Any]]] = None

    def normalized_response(self):
        if self.answer is not None:
            return self.answer
        if self.response_data is not None:
            return self.response_data
        raise ValueError('Укажите answer (число, строку или список) либо response_data')
class RetakeRequest(BaseModel):
    specialization_id: UUID
    target_grade_id: UUID
    decline_lower: bool = False

def owned(db,sid,user):
    obj=db.get(AssessmentSession,sid)
    profile=db.query(CandidateProfile).filter_by(user_id=user['id']).first()
    if not obj or not profile or obj.candidate_id != profile.id: raise HTTPException(404,'Сессия не найдена')
    return obj

def profile_for(db,user):
    profile=db.query(CandidateProfile).filter_by(user_id=user['id']).first()
    if not profile: raise HTTPException(403,'Создайте профиль кандидата')
    return profile

@router.post('/sessions',status_code=201)
def start(body:StartRequest,db:Session=Depends(get_db),user:dict=Depends(require_candidate)):
    profile=profile_for(db,user)
    if not body.specialization and not body.specialization_id:
        # Onboarding profile is the canonical source before the first test;
        # CategoryAssignment exists only after an assessment and is a fallback
        # for retakes of legacy profiles.
        if profile.specialization_id:
            body.specialization_id=profile.specialization_id
        else:
            existing=db.query(CategoryAssignment).filter_by(candidate_id=profile.id).first()
            if existing: body.specialization_id=existing.specialization_id
            else: raise HTTPException(422,'Сначала заполните профиль: укажите специализацию')
    if not body.target_grade and not body.target_grade_id:
        if profile.claimed_grade:
            body.target_grade=profile.claimed_grade
        else:
            raise HTTPException(422,'Сначала заполните профиль: укажите заявленный грейд')
    grade=(db.query(Grade).filter_by(code=body.target_grade).first() if body.target_grade
           else db.get(Grade,body.target_grade_id))
    spec=(db.query(Specialization).filter_by(code=body.specialization).first() if body.specialization
          else db.get(Specialization,body.specialization_id))
    if not grade:
        valid=', '.join(g.code for g in db.query(Grade).order_by(Grade.level).all())
        raise HTTPException(422,f'Неизвестный грейд; допустимые значения: {valid}')
    if not spec:
        valid=', '.join(s.code for s in db.query(Specialization).order_by(Specialization.code).all())
        raise HTTPException(422,f'Неизвестная специализация; допустимые значения: {valid}')
    until=engine.cooldown_until(db,profile.id,grade)
    if until: raise HTTPException(409,f'Пересдача доступна после {until.isoformat()}')
    blueprint=db.query(Blueprint).filter_by(specialization_id=spec.id,is_active=True).first()
    if not blueprint: raise HTTPException(409,'Нет активного блюпринта для специализации')
    if not items.load_items(db,spec.id): raise HTTPException(409,'Нет активных заданий для специализации')
    now=datetime.now(timezone.utc)
    obj=AssessmentSession(candidate_id=profile.id,specialization_id=spec.id,target_grade_id=grade.id,
        blueprint_id=blueprint.id,status='active',started_at=now,expires_at=now+timedelta(seconds=settings.CAT_TIME_LIMIT),
        current_theta=engine.PRIORS.get(grade.code,0),current_se=1.,current_item_index=0)
    db.add(obj);db.commit();db.refresh(obj)
    return {'session_id':str(obj.id),'expires_at':obj.expires_at.isoformat()}

@router.get('/sessions/{session_id}')
def get_session(session_id:UUID,db:Session=Depends(get_db),user:dict=Depends(require_candidate)):
    """Return frontend session state without item content or answer keys."""
    obj=owned(db,session_id,user)
    now=datetime.now(timezone.utc)
    expires=obj.expires_at if obj.expires_at.tzinfo else obj.expires_at.replace(tzinfo=timezone.utc)
    if obj.status=='active' and now >= expires:
        obj.status='expired'; db.commit()
    answered=db.query(SessionResponse).filter_by(session_id=obj.id).count()
    target=db.get(Grade,obj.target_grade_id)
    return {'session_id':str(obj.id),'status':obj.status,'expires_at':expires.isoformat(),
            'target_grade':target.code if target else None,'current_item':answered,
            'total_items':settings.CAT_MAX_ITEMS,'created_at':obj.created_at.isoformat() if obj.created_at else None,
            'completed_at':obj.completed_at.isoformat() if obj.completed_at else None}

@router.get('/sessions/{session_id}/next-item')
def next_item(session_id:UUID,db:Session=Depends(get_db),user:dict=Depends(require_candidate)):
    obj=owned(db,session_id,user)
    if obj.status!='active': raise HTTPException(404,'Сессия завершена')
    if engine.should_stop(obj,db.query(SessionResponse).filter_by(session_id=obj.id).count()):
        engine.complete(db,obj);raise HTTPException(404,'Сессия завершена или истекла')
    pending=db.query(SessionItem).filter_by(session_id=obj.id).order_by(SessionItem.sequence.desc()).first()
    if pending and not db.query(SessionResponse).filter_by(session_item_id=pending.id).first():
        item=db.get(Item,pending.item_id); version=db.get(ItemVersion,pending.item_version_id)
        return {'item_id':str(item.id),'item_version_id':str(version.id),'content':items.public_content(version.content),'sequence':pending.sequence}
    selected=items.choose_item(db,obj)
    if not selected:
        # Подходящих заданий не осталось: блюпринт закрыт и/или упёрлись в лимит
        # экспозиции. Раньше здесь всегда отдавался 409 — и сессия зависала:
        # заданий больше нет, условие остановки не достигнуто, а `complete`
        # отвечает «Сессия ещё не завершена». Кандидат проходил 17 заданий из 18
        # и не мог получить грейд (воспроизводилось примерно в каждом третьем
        # прогоне).
        #
        # Если минимальный объём доказательств уже набран, классификация
        # корректна — завершаем сессию и отдаём результат. 409 остаётся только
        # для случая, когда заданий не хватило для достоверного решения.
        answered=db.query(SessionResponse).filter_by(session_id=obj.id).count()
        if answered >= settings.CAT_MIN_ITEMS:
            engine.complete(db,obj)
            raise HTTPException(404,'Сессия завершена: подходящих заданий больше нет')
        raise HTTPException(409,'Недостаточно заданий в блюпринте с учётом лимита экспозиции')
    item,version,info=selected
    row=SessionItem(session_id=obj.id,item_id=item.id,item_version_id=version.id,
        sequence=obj.current_item_index+1,theta_when_selected=obj.current_theta,information_value=info)
    db.add(row);obj.current_item_index+=1;db.commit()
    return {'item_id':str(item.id),'item_version_id':str(version.id),'content':items.public_content(version.content),'sequence':row.sequence}

@router.post('/sessions/{session_id}/answers')
def answer(session_id:UUID,body:AnswerRequest,db:Session=Depends(get_db),user:dict=Depends(require_candidate)):
    obj=owned(db,session_id,user)
    if obj.status!='active': raise HTTPException(409,'Сессия завершена')
    if datetime.now(timezone.utc)>=obj.expires_at.replace(tzinfo=timezone.utc):
        engine.complete(db,obj);raise HTTPException(409,'Время сессии истекло')
    pending=db.query(SessionItem).filter_by(session_id=obj.id).order_by(SessionItem.sequence.desc()).first()
    if not pending or pending.item_id!=body.item_id or db.query(SessionResponse).filter_by(session_item_id=pending.id).first():
        raise HTTPException(409,'Ответ ожидается только на текущее задание')
    item=db.get(Item,pending.item_id);version=db.get(ItemVersion,pending.item_version_id)
    raw_rubric=version.content.get('rubric')
    if isinstance(raw_rubric,dict) and isinstance(raw_rubric.get('criteria'),list):
        raw_rubric=raw_rubric['criteria']
    # Seed rubrics may be a mapping; grading service consumes criterion rows.
    rubric=([{'name':k,'weight':v if isinstance(v,(int,float)) else 1} for k,v in raw_rubric.items()]
            if isinstance(raw_rubric,dict) else
            [{'name':criterion,'weight':1} if isinstance(criterion,str) else criterion
             for criterion in raw_rubric] if isinstance(raw_rubric,list) else [])
    c=version.content
    key=c.get('correct_answer')
    if key is None:
        key=c.get('correct_index') if item.item_type == 'mcq' else c.get('expected')
    spec={'format':item.item_type,'payload':c,'answer':key,
          'rubric':rubric,'acceptable_answers':c.get('acceptable_answers',[]),
          'keywords':c.get('accepted_keywords',[]),'pass_score':c.get('pass_score',.5)}
    try:
        response_value=body.normalized_response()
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    correct,score=grading.grade_item(spec,response_value)
    observations=engine.observations_for(db,obj)+[(item.discrimination,item.difficulty,correct)]
    grade=db.get(Grade,obj.target_grade_id)
    theta,se,_=engine.posterior(observations,engine.PRIORS.get(grade.code,0))
    db.add(SessionResponse(session_id=obj.id,item_id=item.id,session_item_id=pending.id,
        response_data={'answer': response_value} if not isinstance(response_value, dict) else response_value,is_correct=correct,score=score,time_spent_seconds=0,theta_after=theta,se_after=se))
    obj.current_theta=theta;obj.current_se=se
    db.commit()
    count=db.query(SessionResponse).filter_by(session_id=obj.id).count()
    if engine.should_stop(obj,count): engine.complete(db,obj)
    return {'is_correct':correct,'current_theta':theta,'current_se':se,'session_status':obj.status}

@router.post('/sessions/{session_id}/complete')
def complete(session_id:UUID,db:Session=Depends(get_db),user:dict=Depends(require_candidate)):
    obj=owned(db,session_id,user)
    answered=db.query(SessionResponse).filter_by(session_id=obj.id).count()
    if obj.status=='active' and not engine.should_stop(obj,answered): raise HTTPException(409,'Сессия ещё не завершена')
    return engine.complete(db,obj)

@router.get('/sessions/{session_id}/result')
def get_result(session_id:UUID,db:Session=Depends(get_db),user:dict=Depends(require_candidate)):
    obj=owned(db,session_id,user)
    if obj.status!='completed': raise HTTPException(409,'Результат ещё не готов')
    return engine.complete(db,obj)

@router.get('/history')
def history(db:Session=Depends(get_db),user:dict=Depends(require_candidate)):
    profile=profile_for(db,user)
    rows=db.query(AssessmentSession).filter_by(candidate_id=profile.id).order_by(AssessmentSession.created_at.desc()).all()
    return {'sessions':[{'session_id':str(s.id),'target_grade_id':str(s.target_grade_id),'status':s.status,
                         'final_theta':s.final_theta,'final_se':s.final_se,'assigned_grade_id':str(s.assigned_grade_id) if s.assigned_grade_id else None} for s in rows],
            'decisions':[{'session_id':str(h.assessment_session_id),'change_type':h.change_type,'reason':h.reason} for h in db.query(GradeHistory).filter_by(candidate_id=profile.id).all()]}

@router.post('/retake')
def retake(body:RetakeRequest,db:Session=Depends(get_db),user:dict=Depends(require_candidate)):
    profile=profile_for(db,user)
    grade=db.get(Grade,body.target_grade_id)
    if not grade: raise HTTPException(404,'Грейд не найден')
    if body.decline_lower:
        assignment=db.query(CategoryAssignment).filter_by(candidate_id=profile.id).first()
        if assignment:
            assignment.is_confirmed=False;assignment.confirmed_at=None;db.commit()
        return {'is_confirmed':False,'message':'Предварительная категория: тест на грейд ниже отклонён'}
    return start(StartRequest(specialization_id=body.specialization_id,target_grade_id=body.target_grade_id),db,user)
