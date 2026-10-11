"""Deterministic resume extraction and branded profile PDF generation."""
from __future__ import annotations
import io, json, re
from pathlib import Path
from typing import Any

try:
 import fitz
except ImportError: fitz = None
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

ROOT=Path(__file__).resolve().parents[3]
SKILLS_PATH=ROOT/'content'/'skills.json'

def _skills():
 try: return json.loads(SKILLS_PATH.read_text(encoding='utf-8')).get('skills',[])
 except Exception:return []

def _norm(s:str)->str:
 return re.sub(r'[^a-zа-яё0-9+#.]','',s.lower().replace('ё','е'))

def extract_text(pdf_bytes:bytes)->str:
 if not pdf_bytes or not pdf_bytes.startswith(b'%PDF'):
  raise ValueError('Ожидается непустой PDF-файл')
 if fitz is None: raise RuntimeError('PyMuPDF недоступен')
 try:
  doc=fitz.open(stream=pdf_bytes,filetype='pdf')
  return '\n'.join(page.get_text() for page in doc).strip()
 except Exception as e: raise ValueError('Не удалось прочитать PDF') from e

def _find_skills(text):
 low=_norm(text); result=[]
 for s in _skills():
  terms={s.get('id',''),s.get('name',''),*s.get('aliases',[])}
  if any(_norm(t) and _norm(t) in low for t in terms):
   result.append(s['id'])
 return list(dict.fromkeys(result))

def parse_resume(text:str)->dict[str,Any]:
 text=text or ''; clean=' '.join(text.split())
 email=re.search(r'[\w.+-]+@[\w.-]+\.[a-zа-я]{2,}',text,re.I)
 phone=re.search(r'(?:\+7|8)\s*\(?\d{3}\)?[\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}',text)
 years=re.search(r'(?:опыт|стаж)[^\d]{0,15}(\d+(?:[.,]\d+)?)\s*(?:лет|года|год)',text,re.I)
 grade=re.search(r'\b(intern|junior|middle|senior|lead|стажер|джуниор|мидл|сеньор|лид)\b',text,re.I)
 # First non-heading line is a conservative name candidate.
 lines=[x.strip() for x in text.splitlines() if x.strip()]
 name=lines[0] if lines and not re.search(r'@|резюме|cv',lines[0],re.I) else None
 skills=_find_skills(text)
 return {'source_text':text,'fields':{
  'full_name':{'value':name,'confidence':0.9 if name else 0.0},
  'email':{'value':email.group(0) if email else None,'confidence':0.99 if email else 0.0},
  'phone':{'value':phone.group(0) if phone else None,'confidence':0.95 if phone else 0.0},
  'skills':{'value':skills,'confidence':0.9 if skills else 0.1},
  'experience_years':{'value':float(years.group(1).replace(',','.')) if years else None,'confidence':0.9 if years else 0.0},
  'grade_hint':{'value':grade.group(1).lower() if grade else None,'confidence':0.75 if grade else 0.0},
  'roles':{'value':re.findall(r'\b(?:backend|frontend|devops|qa|аналитик|разработчик|инженер|тестировщик)\w*',text,re.I),'confidence':0.7},
  'soft_skills':{'value':[x for x in ('коммуникация','лидерство','командная работа','ответственность') if x in text.lower()],'confidence':0.6}
 },'confirmed_fields':{}}

def generate_profile_pdf(profile:dict[str,Any])->bytes:
 out=io.BytesIO(); c=Canvas(out,pagesize=A4); W,H=A4
 c.setFillColor(colors.HexColor('#310F53')); c.rect(0,H-90,W,90,fill=1,stroke=0)
 c.setFillColor(colors.HexColor('#FFFFFF')); c.setFont('Helvetica-Bold',24); c.drawString(42,H-55,'РАЗРЯД')
 c.setFont('Helvetica',10); c.drawRightString(W-42,H-55,'профиль специалиста')
 def row(label,val,y):
  c.setFillColor(colors.HexColor('#520978'));c.setFont('Helvetica-Bold',10);c.drawString(42,y,label)
  c.setFillColor(colors.HexColor('#1C1D22'));c.setFont('Helvetica',11);c.drawString(170,y,str(val or '—'))
 y=H-125; row('ФИО',profile.get('full_name'),y);y-=22;row('Контакты',profile.get('email'),y);y-=22
 grade=profile.get('grade','—'); status='подтверждён' if profile.get('grade_confirmed',False) else 'предварительно'
 row('Категория',f"{profile.get('specialization','—')} · {grade} ({status})",y);y-=22;row('Стаж',f"{profile.get('experience_years','—')} лет",y);y-=34
 c.setFillColor(colors.HexColor('#FF0053'));c.rect(42,y,W-84,2,fill=1,stroke=0);y-=26
 for title,val in [('Стек',', '.join(profile.get('skills',[]))),('Роли',', '.join(profile.get('roles',[]))),('Достижения ФСП',', '.join(profile.get('fsp_achievements',[]) or ['Не привязаны']))]:
  c.setFillColor(colors.HexColor('#520978'));c.setFont('Helvetica-Bold',12);c.drawString(42,y,title);y-=18;c.setFillColor(colors.HexColor('#1C1D22'));c.setFont('Helvetica',10)
  for line in [val[i:i+90] for i in range(0,max(1,len(val)),90)]: c.drawString(42,y,line);y-=15
  y-=12
 c.setFillColor(colors.HexColor('#8A83D1'));c.setFont('Helvetica',8);c.drawString(42,30,'Сформировано платформой РАЗРЯД · подтверждение уровня указано явно')
 c.save();return out.getvalue()
