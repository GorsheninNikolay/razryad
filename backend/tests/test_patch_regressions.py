from datetime import datetime, timedelta, timezone
import uuid
import pytest
from app.core.security import decode_token
from app.models.models import AssessmentSession, Blueprint, CandidateProfile, Competency, Grade, Item, ItemVersion, SessionItem, SessionResponse, Specialization
from app.services.grading import grade_item

@pytest.mark.parametrize('fmt,content,response,correct', [
    ('mcq', {'correct_index': 0, 'options': ['yes', 'no']}, 0, True),
    ('mcq', {'correct_answer': None, 'correct_index': 1}, 1, True),
    ('mcq', {'correct_answer': 1, 'correct_index': 0}, 0, False),
    ('mcq', {'correct_index': 1}, {'answer': 1}, True),
    ('mcq', {'correct_index': 1}, 0, False),
    ('code_output', {'expected': '14'}, '14', True),
    ('code_output', {'expected': '14'}, '13', False),
    ('code_output', {'correct_answer': '14', 'acceptable_answers': ['fourteen']}, 'fourteen', True),
    ('short_answer', {'accepted_keywords': ['oop', 'тест']}, 'OOP,  тест!', True),
    ('short_answer', {'accepted_keywords': ['oop', 'тест']}, 'oop', False),
    ('short_answer', {'accepted_keywords': ['oop', 'тест']}, 'loop тест', False),
    ('short_answer', {'correct_answer': 'closure', 'acceptable_answers': ['замыкание']}, 'замыкание', True),
    ('short_answer', {'accepted_keywords': ['unit test']}, 'A unit   test.', True),
    ('essay', {'rubric': ['корректность', 'безопасность', 'проверяемость', 'компромиссы']}, 'корректность безопасность проверяемость компромиссы', True),
    ('essay', {'rubric': ['корректность', 'безопасность', 'проверяемость', 'компромиссы']}, 'корректность', False),
    ('essay', {'rubric': {'criteria': [{'keywords': ['unit test', 'rollback'], 'weight': 1}]}, 'pass_score': .75}, 'unit test', False),
    ('mcq', {'correct_index': 0}, '', False),
    ('code_output', {'expected': ''}, '  ', False),
    ('short_answer', {'accepted_keywords': ['oop']}, [], False),
    ('essay', {'rubric': ['корректность']}, {}, False),
])
def test_bank_answer_endpoint(client, test_db, auth_candidate, fmt, content, response, correct):
    profile = test_db.query(CandidateProfile).filter_by(user_id=decode_token(auth_candidate)['user_id']).first()
    if profile is None:
        profile = CandidateProfile(user_id=decode_token(auth_candidate)['user_id'])
        test_db.add(profile)
    spec = test_db.query(Specialization).filter_by(code='backend').first()
    grade = test_db.query(Grade).filter_by(code='middle').first()
    blueprint = test_db.query(Blueprint).filter_by(specialization_id=spec.id).first()
    competency = test_db.query(Competency).filter_by(specialization_id=spec.id).first()
    item = Item(code='regression-' + uuid.uuid4().hex, specialization_id=spec.id,
                competency_id=competency.id, item_type=fmt, status='active', discrimination=1., difficulty=0., estimated_time_seconds=120)
    test_db.add(item); test_db.flush()
    version = ItemVersion(item_id=item.id, version=1, content=content, is_current=True)
    session = AssessmentSession(candidate_id=profile.id, specialization_id=spec.id,
                                target_grade_id=grade.id, blueprint_id=blueprint.id, status='active',
                                expires_at=datetime.now(timezone.utc) + timedelta(minutes=45),
                                current_theta=0., current_se=1., current_item_index=1)
    test_db.add_all([version, session]); test_db.flush()
    pending = SessionItem(session_id=session.id, item_id=item.id, item_version_id=version.id, sequence=1, theta_when_selected=0., information_value=.25)
    test_db.add(pending); test_db.commit()
    headers = {'Authorization': f'Bearer {auth_candidate}'}
    public = client.get(f'/api/v1/assessment/sessions/{session.id}/next-item', headers=headers)
    assert public.status_code == 200
    assert not {'correct_answer', 'correct_index', 'expected', 'accepted_keywords', 'rubric'} & public.json()['content'].keys()
    result = client.post(f'/api/v1/assessment/sessions/{session.id}/answers', headers=headers,
                         json={'item_id': str(item.id), 'answer': response})
    assert result.status_code == 200, result.text
    assert result.json()['is_correct'] is correct
    stored = test_db.query(SessionResponse).filter_by(session_item_id=pending.id).one()
    assert stored.is_correct is correct
    if content.get("pass_score") == .75:
        assert stored.score == .5
    elif correct:
        assert stored.score > 0
    else:
        assert stored.score < .5

def test_weighted_rubric_and_synonym_alternatives():
    item = {'format': 'essay', 'pass_score': .6, 'rubric': [
        {'weight': 3, 'keywords': ['unit test', 'rollback', '']},
        {'weight': 1, 'synonyms': ['monitoring', 'наблюдаемость']},
    ]}
    assert grade_item(item, 'unit test rollback наблюдаемость') == (True, 1.)
    assert grade_item(item, 'unit test') == (False, .375)
    assert grade_item(item, 'untested and rollbacker') == (False, 0.)

def test_empty_keywords_do_not_manufacture_correct_answers():
    assert grade_item({'format': 'short_answer', 'keywords': [' ', '']}, 'anything') == (False, 0.)

def test_serializer_confirmation_and_hired_contacts():
    from app.services.invitations import serialize_candidate_for_employer
    candidate = {'id': 'abc', 'grade': 3, 'is_confirmed': True, 'fio': 'Candidate',
                 'contacts': {'email': 'candidate@example.com'}, 'workplace': {'company': 'Private'}}
    for status in ['sent', 'viewed', 'declined', 'expired', 'withdrawn']:
        result = serialize_candidate_for_employer(candidate, status)
        assert result['is_confirmed'] is True
        assert not {'fio', 'contacts', 'workplace'} & result.keys()
    for status in ['accepted', 'hired']:
        result = serialize_candidate_for_employer(candidate, status)
        assert result['fio'] == 'Candidate'
        assert result['contacts'] == {'email': 'candidate@example.com'}
        assert 'pseudonym' not in result
