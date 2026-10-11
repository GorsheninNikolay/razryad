#!/usr/bin/env python3
"""Deterministic synthetic fixture generator for РАЗРЯД (E1/E4)."""
from __future__ import annotations
import argparse, json, math, random
from datetime import date, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TAX=ROOT/'content/taxonomy.json'; SKILLS=ROOT/'content/skills.json'
GRADES=['intern','junior','middle','senior','lead']; FORMATS=['mcq','code_output','short_answer','open_response']
CITIES=['Москва','Санкт-Петербург','Казань','Новосибирск','Екатеринбург','Самара','Томск','Удалённо']

def load_tax(): return json.loads(TAX.read_text(encoding='utf-8'))
def item_bank(tax):
    prompts={'algorithms':'Реализуйте поиск кратчайшего пути в графе с отрицательными рёбрами без отрицательных циклов; объясните сложность.', 'language':'В Python замыкание захватывает переменную цикла. Исправьте функцию и объясните область видимости.', 'databases':'Напишите SQL с оконной функцией для топ-3 платежей каждого клиента за месяц.', 'api_networks':'Клиент повторяет POST после таймаута. Как сделать endpoint идемпотентным и защитить от дублей?', 'javascript':'Почему microtask queue меняет порядок вывода Promise и setTimeout? Укажите точный порядок.', 'sql':'Даны users и orders. Напишите запрос доли активных пользователей с заказом за 30 дней.', 'networks':'Сравните TCP и QUIC при потере пакетов; назовите механизм восстановления.', 'linux':'Процесс в контейнере получает SIGTERM. Опишите корректное graceful shutdown и timeout.', 'containers':'Спроектируйте healthcheck и readiness для сервиса в Kubernetes.', 'testing':'Составьте pairwise-набор тестов для формы регистрации с 5 полями и 3 значениями.', 'statistics':'Для A/B-теста вычислите доверительный интервал разницы конверсий и условия остановки.', 'cpp':'Объясните dangling pointer после realloc и предложите безопасное управление памятью.'}
    out=[]; idx=0
    comps=[(s['id'],c['id'],c['name']) for s in tax['specializations'] for c in s['competencies']]
    for si,(sid,cid,cname) in enumerate(comps):
      for j in range(10):
        fmt=FORMATS[j%4]; idx+=1; grade=GRADES[j%5]; b=-3+(j%7); a=round(0.8 + ((idx * 37) % 120) / 100,2)
        base=prompts.get(cid, f'Компетенция «{cname}»: разберите практический инцидент в production и предложите проверяемое решение.')
        if fmt=='mcq': payload={'stem':base+' Выберите наиболее корректный вариант.', 'options':['Изменить таймаут без диагностики','Воспроизвести, измерить и покрыть тестом','Игнорировать редкий случай','Отключить проверку'], 'correct_index':1}
        elif fmt=='code_output': payload={'stem':base+' Приведите результат выполнения и причину.', 'code':'x = [1, 2, 3]\nprint(sum(v*v for v in x))','expected':'14'}
        elif fmt=='short_answer': payload={'stem':base+' Ответьте кратко с ключевыми шагами.','accepted_keywords':[cid, 'тест']}
        else: payload={'stem':base+' Предложите подход с компромиссами, мониторингом и планом отката.','rubric':['корректность','безопасность','проверяемость','компромиссы']}
        out.append({'id':f'item-{idx:04d}','code':f'ITEM-{idx:04d}','specialization_id':sid,'competency_id':cid,'format':fmt,'item_type':fmt,'difficulty_b':b,'difficulty':b,'discrimination_a':a,'discrimination':a,'target_grade':grade,'payload':payload,'content':payload,'answer':payload.get('expected',payload.get('correct_index')), 'rubric':payload.get('rubric'), 'is_anchor':idx<=20,'status':'active','exposure_limit':0.15})
    return out

def generate(seed=42):
 r=random.Random(seed); tax=load_tax(); skills=json.loads(SKILLS.read_text(encoding='utf-8'))['skills']; skill_ids=[x['id'] for x in skills]
 by_spec={sid:[x['id'] for x in skills if sid in x.get('specializations',[])] for sid in [s['id'] for s in tax['specializations']]}
 cross=['git','linux','docker','sql','ci-cd']; cross=[x for x in cross if x in skill_ids]
 # Every specialization receives 75% taxonomy-mapped skills and 25% cross-functional skills.
 def realistic_stack(sid,grade):
  n={'intern':6,'junior':8,'middle':11,'senior':14,'lead':17}[grade]; pool=by_spec.get(sid,[]); local_n=max(1,round(n*.75))
  cores={'backend':['python','fastapi','postgresql','sql','docker','linux','django','redis','java','go'],'frontend':['javascript','react','html','css','typescript'],'data-eng':['python','sql','spark','kafka','airflow'],'devops':['docker','kubernetes','linux','terraform','ansible'],'mobile':['kotlin','swift','flutter'],'ml':['python','pytorch','tensorflow'],'qa':['pytest','selenium','playwright'],'analytics':['sql','python','pandas'],'infosec':['linux','wireshark'],'embedded':['c','cpp','linux']}
  core=[x for x in cores.get(sid,[]) if x in pool]
  preferred=[x for x in core if r.random() < (.90 if sid=='backend' and x in ['python','docker'] else .70)]
  chosen=preferred[:local_n]
  remaining_local=[x for x in pool if x not in chosen]
  chosen+=r.sample(remaining_local,min(local_n-len(chosen),len(remaining_local)))
  remaining=[x for x in cross if x not in chosen]; chosen += r.sample(remaining,min(n-len(chosen),len(remaining)))
  if len(chosen)<n: chosen += r.sample([x for x in pool if x not in chosen],min(n-len(chosen),len(pool)-len(chosen)))
  return chosen
 candidates=[]
 # grade skew: junior/middle dominant, 10x5 coverage
 for i in range(500):
  sid=tax['specializations'][i%10]['id']; grade=GRADES[min(4,int(r.triangular(0,4,2.1)))]
  theta=(GRADES.index(grade)-2)*1.5+r.gauss(0,.45); self_grade=GRADES[min(4,max(0,GRADES.index(grade)+(1 if r.random()<.55 else 0)))]
  candidates.append({'id':f'cand-{i+1:04d}','email':f'candidate{i+1}@fixture.razryad.ru','full_name':f'{"Алексей" if i%2 else "Мария"} {"Иванов" if i%3 else "Петрова"} {i+1}','specialization_id':sid,'true_grade':grade,'theta':round(theta,4),'self_assessed_grade':self_grade,'years_experience':max(0,min(15,round(GRADES.index(grade)*1.7+r.gauss(0,.8)))),'work_format':r.choice(['remote','hybrid','office']),'city':r.choice(CITIES),'domain':r.choice(['fintech','ecommerce','edtech','healthtech','telecom','logistics']),'skills':realistic_stack(sid,grade),'fsp':i>=200,'fsp_index':round(r.uniform(.25,.98),3) if i>=200 else 0.0,'freshness_days':r.randint(0,180),'profile_visible':True})
 achievements=[]
 for j in range(300):
  cid=f'cand-{j+201:04d}'; achievements.append({'id':f'ach-{j+1:04d}','candidate_id':cid,'event_name':r.choice(['Кубок алгоритмов ФСП','Региональный хакатон','Олимпиада по программированию','Командный чемпионат']), 'event_level':r.choice(['national','regional','university','international']),'discipline':r.choice(['algorithms','backend','data','security','analytics']),'event_date':str(date(2026,1,1)-timedelta(days=r.randint(0,2200))),'place':r.randint(1,30),'role':r.choice(['participant','captain','coach']),'verification_status':'self_declared' if j%7==0 else 'verified','weight':0.0 if j%7==0 else 1.0})
 companies=[{'id':f'company-{i+1:03d}','name':f'{r.choice(["Техно","Север","Вектор","Квант"])} {i+1}','industry':r.choice(['fintech','ecommerce','edtech','telecom']),'size':r.choice(['startup','small','medium','large'])} for i in range(40)]
 needs=[]
 for i in range(60):
  sid=tax['specializations'][i%10]['id']; lo=r.randint(0,3); hi=min(4,lo+r.randint(1,2)); must=r.sample(skill_ids,3)
  needs.append({'id':f'need-{i+1:03d}','company_id':companies[i%40]['id'],'specialization_id':sid,'grade_min':GRADES[lo],'grade_max':GRADES[hi],'must_have_skills':must,'nice_to_have_skills':r.sample(skill_ids,2),'text':f'Ищем специалиста в команду {companies[i%40]["name"]}: нужен опыт в {", ".join(must)}. Предстоит развивать сервисы, писать тесты и участвовать в ревью. Формат {r.choice(CITIES)}, зарплата от {120000+i*1000} до {220000+i*1500} рублей.'})
 vacancies=[{'id':f'vacancy-{i+1:03d}','company_id':companies[i%40]['id'],'need_id':needs[i%60]['id'],'title':f'{GRADES[i%5].title()} {tax["specializations"][i%10]["name"]}','description':needs[i%60]['text'],'salary_min':100000+i*1000,'salary_max':180000+i*1500,'published':True} for i in range(100)]
 interactions=[{'id':f'interaction-{i+1:04d}','candidate_id':f'cand-{i%500+1:04d}','company_id':companies[i%40]['id'],'type':r.choice(['view','invite','accept','decline','save']),'created_at':str(date(2026,1,1)-timedelta(days=r.randint(0,180)))} for i in range(1200)]
 return {'meta':{'seed':seed,'generated_at':'2026-01-01','counts':{'candidates':500,'achievements':300,'fsp_candidates':300,'no_fsp_candidates':200,'companies':40,'needs':60,'vacancies':100,'interactions':1200,'items':600}},'candidates':candidates,'achievements':achievements,'companies':companies,'needs':needs,'vacancies':vacancies,'interactions':interactions,'items':item_bank(tax)}

def check(data):
 assert len(data['candidates'])==500 and sum(bool(x['fsp']) for x in data['candidates'])==300
 assert len(data['achievements'])==300 and len(data['companies'])==40 and len(data['needs'])==60 and len(data['vacancies'])==100 and len(data['interactions'])==1200
 assert len(data['items'])>=300 and len({x['id'] for x in data['items']})==len(data['items'])
 assert all(.6<=x['discrimination_a']<=2.5 and -3<=x['difficulty_b']<=3 and x['target_grade'] in GRADES for x in data['items'])
 assert sum(x['is_anchor'] for x in data['items'])==20
 skills={x['id'] for x in json.loads(SKILLS.read_text(encoding='utf-8'))['skills']}; assert all(set(c['skills'])<=skills for c in data['candidates'])
 assert all(v['salary_min']>0 and v['salary_max']>=v['salary_min'] for v in data['vacancies'])
 return True

def main():
 p=argparse.ArgumentParser(); p.add_argument('--seed',type=int,default=42); p.add_argument('--out',default='backend/seed/data/fixtures.json'); p.add_argument('--check',action='store_true'); a=p.parse_args(); d=generate(a.seed); check(d); Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(d['meta']['counts'],ensure_ascii=False)); print('CHECK: PASS')
if __name__=='__main__': main()
