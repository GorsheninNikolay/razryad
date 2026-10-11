"""Idempotent ORM loader: stable UUID5, one transaction, no deletion."""
import sys,json,uuid,math
from pathlib import Path
from datetime import datetime,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.db import Base,engine,SessionLocal
from app.models import *
from app.models.models import ContactRevealLog
from app.core.security import hash_password
from generate import generate,check,load_tax,GRADES,ROOT
NS=uuid.UUID('0450d5e8-bd43-47f3-b781-8d4454454111')
def uid(s): return uuid.uuid5(NS,s)
def main():
 path=Path(__file__).parent/'data/fixtures.json'; data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else generate();check(data)
 Base.metadata.create_all(engine); engine.echo=False; now=datetime(2026,1,1)
 with SessionLocal() as db:
  def put(cls,key,**kw):
   ident=uid(key)
   obj=db.get(cls,ident)
   if obj is None:
    db.add(cls(id=ident,**kw))
   else:
    # UPSERT. Без обновления существующих строк повторный сид не применял
    # изменённые значения фикстур: именно поэтому новые параметры заданий
    # (a = 0.8..1.99) не попадали в уже засеянную базу.
    for field,value in kw.items():
     setattr(obj,field,value)
   db.flush();return ident
  specs={}; grades={}; skills={}; comps={};bps={}
  for i,g in enumerate(GRADES): grades[g]=put(Grade,'grade-'+g,code=g,name=g.title(),level=i,theta_threshold=[-3,-1.5,0,1.5,2.5][i])
  for s in load_tax()['specializations']:
   sid=s['id'];specs[sid]=put(Specialization,'spec-'+sid,code=sid,name=s['name'],description=s['description'],competency_blueprint={c['id']:c['weight'] for c in s['competencies']})
   bps[sid]=put(Blueprint,'bp-'+sid,name=s['name'],specialization_id=specs[sid])
   for c in s['competencies']:
    comps[sid,c['id']]=put(Competency,sid+'-'+c['id'],code=sid+'-'+c['id'],name=c['name'],specialization_id=specs[sid])
    put(BlueprintWeight,'weight-'+sid+'-'+c['id'],blueprint_id=bps[sid],competency_id=comps[sid,c['id']],weight=c['weight'])
  aliases=set()
  for s in json.loads((ROOT/'content/skills.json').read_text(encoding='utf-8'))['skills']:
   skills[s['id']]=put(Skill,'skill-'+s['id'],name=s['name'],normalized_name=s['id'],category=s.get('category','tool'))
   for a in s.get('aliases',[]):
    if a in aliases:continue
    aliases.add(a)
    if db.query(SkillAlias).filter_by(alias=a).first() is None:put(SkillAlias,'alias-'+a,alias=a,skill_id=skills[s['id']])
  pw=hash_password('DemoRazryad42!')
  for i,c in enumerate(data['candidates']):
   email={0:'novice@razryad.demo',200:'middle@razryad.demo',1:'provisional@razryad.demo'}.get(i,c['email']);user=put(User,'user-'+c['id'],email=email,password_hash=pw,role='candidate',email_confirmed=True,email_confirmed_at=now)
   grade='intern' if i==0 else 'middle' if i in [1,200] else c['true_grade'];spec=c['specialization_id']
   put(CandidateProfile,c['id'],user_id=user,full_name=c['full_name'],city=c['city'],timezone='Europe/Moscow',years_of_experience=c['years_experience'],work_format=c['work_format'],team_role='team_member',availability='two_weeks',bio='Синтетический профиль. Опыт в '+c['domain'],onboarding_completed=True,profile_visible=True,last_active_at=now-timedelta(days=c['freshness_days']),freshness_score=math.exp(-c['freshness_days']/45))
   for consent in ['personal_data','profile_publication']:
    put(Consent,'consent-'+c['id']+consent,user_id=user,consent_type=consent,version='1.0',text_snapshot='Синтетическое согласие для демонстрации',granted=True)
   put(CategoryAssignment,'cat-'+c['id'],candidate_id=uid(c['id']),specialization_id=specs[spec],grade_id=grades[grade],is_confirmed=i!=1,confirmed_at=None if i==1 else now,category_rank=i//10+1,rank_score=50+c['theta']*10)
   # Reconcile only fixture-owned profiles so old random skills do not accumulate.
   wanted={skills[s] for s in c['skills']}
   for old in db.query(CandidateSkill).filter_by(candidate_id=uid(c['id'])).all():
    if old.skill_id not in wanted: db.delete(old)
   for skill in c['skills']:put(CandidateSkill,c['id']+'-'+skill,candidate_id=uid(c['id']),skill_id=skills[skill],proficiency='expert' if grade in ('senior','lead') else 'beginner' if grade=='intern' else 'intermediate',years_of_experience=c['years_experience'])
   if c['fsp']:put(FspIdentity,'fsp-'+c['id'],candidate_id=uid(c['id']),fsp_id='DEMO-'+c['id'],verified=True,verified_at=now)
  for a in data['achievements']:
   put(FspAchievement,a['id'],fsp_identity_id=uid('fsp-'+a['candidate_id']),event_name=a['event_name'],event_level=a['event_level'],discipline=a['discipline'],event_date=datetime.fromisoformat(a['event_date']),place=a['place'],participants_count=100,role=a['role'],verification_status=a['verification_status'])
  for i,c in enumerate(data['companies']):
   co=put(Company,c['id'],name=c['name'],industry=c['industry'],size=c['size'],description='Демонстрационная технологическая компания')
   u=put(User,'employer-user-'+c['id'],email=f'employer{i+1}@razryad.demo',password_hash=pw,role='employer',email_confirmed=True,email_confirmed_at=now)
   put(EmployerProfile,'employer-'+c['id'],user_id=u,company_id=co,full_name='Демо рекрутер',position='HR')
   put(TrustScore,'trust-'+c['id'],company_id=co,score=75)
  needs={n['id']:n for n in data['needs']}
  for n in data['needs']:
   put(Need,n['id'],employer_id=uid('employer-'+n['company_id']),specialization_id=specs[n['specialization_id']],title='Нужен '+n['specialization_id'],description=n['text'],grade_min_id=grades[n['grade_min']],grade_max_id=grades[n['grade_max']],must_have_skills=n['must_have_skills'],nice_to_have_skills=n['nice_to_have_skills'],salary_min=120000,salary_max=240000,work_format='remote')
  for v in data['vacancies']:
   n=needs[v['need_id']]
   put(Vacancy,v['id'],company_id=uid(v['company_id']),employer_id=uid('employer-'+v['company_id']),need_id=uid(n['id']),specialization_id=specs[n['specialization_id']],grade_min_id=grades[n['grade_min']],grade_max_id=grades[n['grade_max']],title=v['title'],description=v['description'],salary_min=v['salary_min'],salary_max=v['salary_max'],requirements={'must_have_skills':n['must_have_skills']},published=True,published_at=now,status='published',work_format='remote')
  for it in data['items']:
   sid=it['specialization_id'];iid=put(Item,it['id'],code=it['code'],specialization_id=specs[sid],competency_id=comps[sid,it['competency_id']],item_type='essay' if it['format']=='open_response' else it['format'],status='active',discrimination=it['discrimination_a'],difficulty=it['difficulty_b'],is_anchor=it['is_anchor'],estimated_time_seconds=120)
   put(ItemVersion,'version-'+it['id'],item_id=iid,version=1,content={**it['payload'],'target_grade':it['target_grade']},is_current=True)
  for i,c in enumerate(data['candidates']):
   sid=c['specialization_id']; grade='intern' if i==0 else 'middle' if i in [1,200] else c['true_grade']
   sess=put(AssessmentSession,'assessment-'+c['id'],candidate_id=uid(c['id']),specialization_id=specs[sid],target_grade_id=grades[grade],blueprint_id=bps[sid],status='completed',expires_at=now,final_theta=c['theta'],final_se=round(.22+(i%7)*.015,3))
   put(AbilityEstimate,'ability-'+c['id'],candidate_id=uid(c['id']),specialization_id=specs[sid],assessment_session_id=sess,theta=c['theta'],se=round(.22+(i%7)*.015,3),grade_probabilities={g:(1.0 if GRADES.index(g)<=GRADES.index(grade) else .25) for g in GRADES})
  statuses=['sent','viewed','accepted','declined','expired','hired']
  for j,status in enumerate(statuses):
   c=data['candidates'][j]; n=data['needs'][j]; inv=put(Invitation,'inv-demo-'+status,employer_id=uid('employer-'+n['company_id']),candidate_id=uid(c['id']),vacancy_id=uid('vacancy-'+f'{j+1:03d}'),need_id=uid(n['id']),subject='Демо-предложение',message='Задачи и вилка зарплаты',salary_min=140000,salary_max=220000,company_name='Демо-компания',contact_person='Демо рекрутер',contact_method='email',status=status,sent_at=now,expires_at=now+timedelta(days=30),slots_available=1)
   put(InvitationStatusEvent,'inv-event-'+status,invitation_id=inv,from_status='sent',to_status=status,actor='system',note='Synthetic lifecycle')
   if status in ('accepted','hired'): put(ContactRevealLog,'reveal-'+status,invitation_id=inv,candidate_id=uid(c['id']),employer_id=uid('employer-'+n['company_id']),trigger='invitation_accepted',candidate_data_revealed={'email':c['email']},employer_data_revealed={'company':'Демо-компания'})
  for j,status in enumerate(['pending','viewed','shortlisted','rejected','hired']):
   c=data['candidates'][j+10];v=data['vacancies'][j+1]; app=put(Application,'app-demo-'+status,vacancy_id=uid(v['id']),candidate_id=uid(c['id']),cover_letter='Готов применить опыт.',status=status)
   put(ApplicationStatusEvent,'app-event-'+status,application_id=app,from_status='pending',to_status=status,note='Synthetic lifecycle')
  for j,s in enumerate(load_tax()['specializations'][:5]):
   cid=s['competencies'][0]['id']; put(MicroChallenge,'micro-'+s['id'],specialization_id=specs[s['id']],competency_id=comps[s['id'],cid],title='Микро-задача '+s['name'],description='Production кейс на 15 минут',content={'prompt':'Опишите решение и проверку'},published_at=now,deadline=now+timedelta(days=14),estimated_time_minutes=15,rubric={'correctness':1},is_active=True)
  db.commit()
  for cls in [User,CandidateProfile,FspAchievement,Company,Need,Vacancy,Item,ItemVersion,AbilityEstimate]:print(f'{cls.__tablename__}: {db.query(cls).count()}')
 print('ORM seed committed; repeated load preserves existing rows.')
if __name__=='__main__':main()
