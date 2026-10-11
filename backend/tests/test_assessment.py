"""Grade-policy regressions; use shared conftest DB, never application engine."""
from types import SimpleNamespace
from app.services.assessment import decide_grade, CHANGE_GRADE_CONFIDENCE, INITIAL_GRADE_CONFIDENCE, posterior, probabilities

GRADES=[SimpleNamespace(code=c,level=i) for i,c in enumerate(('intern','junior','middle','senior','lead'))]

def test_hysteresis_preserves_confirmed_grade_on_noisy_retake():
    assert INITIAL_GRADE_CONFIDENCE == .70 and CHANGE_GRADE_CONFIDENCE == .85
    probs={'intern':1.,'junior':.99,'middle':.79,'senior':.3,'lead':.01}
    selected,confirmed,reason,*_=decide_grade(GRADES,probs,GRADES[1],True)
    assert selected.code=='junior' and confirmed and reason.startswith('Без изменений')
    selected,_,_,_,_=decide_grade(GRADES,probs)
    assert selected.code=='middle'  # first attempt still uses .70

def test_hysteresis_requires_strong_evidence_for_upgrade():
    probs={'intern':1.,'junior':.99,'middle':.86,'senior':.3,'lead':.01}
    selected,*_=decide_grade(GRADES,probs,GRADES[1],True)
    assert selected.code=='middle'

def test_hysteresis_blocks_unsupported_downgrade():
    probs={'intern':.99,'junior':.67,'middle':.18,'senior':.01,'lead':0.}
    grade,confirmed,reason,*_=decide_grade(GRADES,probs,GRADES[2],True)
    assert grade.code=='middle' and confirmed and 'Без изменений' in reason
    probs['middle']=.14
    grade,confirmed,reason,borderline,offered=decide_grade(GRADES,probs,GRADES[2],True)
    assert grade.code=='middle' and confirmed and offered=='intern'
    assert 'добровольно' in reason

def test_confirmed_middle_is_not_downgraded_but_explicit_junior_test_can(test_db, monkeypatch):
    """Actual complete() persists a lower grade only after a chosen lower target."""
    import uuid
    from datetime import datetime, timedelta, timezone
    from app.models.models import (User, CandidateProfile, Specialization, Grade, Blueprint,
                                   CategoryAssignment, AssessmentSession, GradeHistory)
    from app.services import assessment
    suffix=uuid.uuid4().hex[:8]
    user=User(email=f'grade-{suffix}@test.com',password_hash='unused',role='candidate',email_confirmed=True)
    spec=Specialization(code=f'grade-spec-{suffix}',name='Grade regression',competency_blueprint={})
    middle=test_db.query(Grade).filter_by(code='middle').first()
    junior=test_db.query(Grade).filter_by(code='junior').first()
    if not middle:
        middle=Grade(code='middle',name='Middle',level=2,theta_threshold=.3)
        test_db.add(middle)
    if not junior:
        junior=Grade(code='junior',name='Junior',level=1,theta_threshold=-.4)
        test_db.add(junior)
    test_db.add_all([user,spec]);test_db.flush()
    profile=CandidateProfile(user_id=user.id)
    bp=Blueprint(name='Grade test',specialization_id=spec.id)
    test_db.add_all([profile,bp]);test_db.flush()
    assignment=CategoryAssignment(candidate_id=profile.id,specialization_id=spec.id,
                                  grade_id=middle.id,is_confirmed=True)
    test_db.add(assignment);test_db.flush()
    # Keep complete() transactional inside this shared test fixture: its normal
    # commits are replaced by flush and all inserted rows roll back afterward.
    monkeypatch.setattr(test_db,'commit',test_db.flush)
    monkeypatch.setattr(assessment,'current_posterior',lambda db,s:(-.5,.3,[]))
    monkeypatch.setattr(assessment,'probabilities',lambda ws:{'intern':.99,'junior':.95,'middle':.01,'senior':0.,'lead':0.})
    def session(target):
        s=AssessmentSession(candidate_id=profile.id,specialization_id=spec.id,
                            target_grade_id=target.id,blueprint_id=bp.id,status='active',
                            expires_at=datetime.now(timezone.utc)+timedelta(minutes=45))
        test_db.add(s);test_db.flush();return s
    ordinary=assessment.complete(test_db,session(middle))
    assert ordinary['assigned_grade_id']==str(middle.id)
    assert ordinary['offered_lower_grade']=='junior'
    assert ordinary['is_confirmed'] is True
    assert test_db.query(GradeHistory).filter_by(candidate_id=profile.id,change_type='downgrade').count()==0
    voluntary=assessment.complete(test_db,session(junior))
    assert voluntary['assigned_grade_id']==str(junior.id)
    assert voluntary['offered_lower_grade'] is None
    assert test_db.query(GradeHistory).filter_by(candidate_id=profile.id,change_type='downgrade').count()==1
    print('ordinary:',ordinary,'voluntary:',voluntary)

def test_start_request_accepts_stable_codes_and_profile_fallback():
    from app.api.assessment import StartRequest
    req=StartRequest(specialization='backend',target_grade='middle')
    assert req.specialization=='backend' and req.target_grade=='middle'
    assert StartRequest().target_grade is None  # resolved from saved profile

def test_answer_request_preserves_scalar_text_list_and_legacy_dict():
    import uuid
    from app.api.assessment import AnswerRequest
    item_id=uuid.uuid4()
    for value in (2,'замыкание',[1,2]):
        assert AnswerRequest(item_id=item_id,answer=value).normalized_response()==value
    assert AnswerRequest(item_id=item_id,response_data={'answer':'SQL'}).normalized_response()=={'answer':'SQL'}
    import pytest
    with pytest.raises(ValueError,match='число, строку или список'):
        AnswerRequest(item_id=item_id).normalized_response()

def test_empty_responses_never_score_correct_for_all_formats():
    from app.services.grading import grade_item
    for fmt in ('mcq','code_output','short_answer','essay'):
        item={'format':fmt,'answer':'','correct_answer':'','rubric':[{'name':'criterion','weight':1}]}
        assert grade_item(item,{})[0] is False
        assert grade_item(item,{'answer':''})[0] is False
        assert grade_item(item,[])[0] is False
        assert grade_item(item,None)[0] is False

def test_answer_forms_have_identical_scoring():
    from app.services.grading import grade_item
    item={'format':'mcq','answer':2}
    assert grade_item(item,2)==grade_item(item,{'answer':2})
    assert grade_item(item,{'answer':2})==grade_item(item,{'value':2})

def test_session_state_contract_and_owner(client, auth_candidate, test_db):
    from app.core.security import decode_token
    from app.models.models import CandidateProfile
    token=decode_token(auth_candidate)
    profile=test_db.query(CandidateProfile).filter_by(user_id=token['user_id']).first()
    if profile is None:
        profile=CandidateProfile(user_id=token['user_id']);test_db.add(profile)
    profile.specialization_id=test_db.query(__import__('app.models.models',fromlist=['Specialization']).Specialization).filter_by(code='backend').first().id
    profile.claimed_grade='middle';test_db.commit()
    # E2E fixture seeds the active blueprint and item bank.
    r=client.post('/api/v1/assessment/sessions',headers={'Authorization':f'Bearer {auth_candidate}'},json={'target_grade':'middle'});assert r.status_code==201
    sid=r.json()['session_id'];state=client.get('/api/v1/assessment/sessions/'+sid,headers={'Authorization':f'Bearer {auth_candidate}'})
    assert state.status_code==200 and state.headers['content-type'].startswith('application/json')
    data=state.json();assert data['current_item']==0 and 12 <= data['total_items'] <= 18
    assert not ({'correct_index','expected','rubric','correct_answer'} & set(data))
    import uuid
    from app.models.models import User, CandidateProfile
    outsider=User(email='outsider-'+uuid.uuid4().hex[:8]+'@example.com',password_hash='unused',role='candidate',email_confirmed=True)
    test_db.add(outsider);test_db.flush();test_db.add(CandidateProfile(user_id=outsider.id));test_db.commit()
    from app.core.security import create_access_token
    other_token=create_access_token(outsider.email,outsider.id,'candidate')
    forbidden=client.get('/api/v1/assessment/sessions/'+sid,headers={'Authorization':f'Bearer {other_token}'})
    assert forbidden.status_code==404
    print('SESSION',state.status_code,state.headers['content-type'],data,'FOREIGN',forbidden.status_code)

def test_eap_probabilities_are_normalized():
    theta,se,weights=posterior([(1.8,0,1)]*8,0)
    assert abs(sum(weights)-1)<1e-12
    assert theta>0 and 0<se<1
    p=probabilities(weights)
    assert p['junior']>=p['middle']>=p['senior']
