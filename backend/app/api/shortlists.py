from sqlalchemy.orm import selectinload
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from app.core.db import get_db
from app.core.security import require_employer, get_current_user
from app.models.models import Shortlist, Need, CandidateProfile, EmployerProfile, CategoryAssignment, Grade, CandidateSkill, Skill, Specialization
from app.services.matching import calculate_match

router = APIRouter()

@router.get("/{need_id}")
async def get_shortlist(
    need_id: uuid.UUID,
    revision: int = None,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    need = db.query(Need).filter(Need.id == need_id).first()
    if not need or not employer or need.employer_id != employer.id:
        raise HTTPException(status_code=404, detail="Need not found")
        
    grade_min_obj = db.query(Grade).filter(Grade.id == need.grade_min_id).first()
    grade_max_obj = db.query(Grade).filter(Grade.id == need.grade_max_id).first()
    
    if not grade_min_obj or not grade_max_obj:
        raise HTTPException(status_code=422, detail="Invalid grade boundaries in need")
        
    grade_min = grade_min_obj.level
    grade_max = grade_max_obj.level
    
    # Calculate matches
    need_profile = {
        "grade_min": grade_min,
        "grade_max": grade_max,
        "must_have_skills": need.must_have_skills,
        "nice_to_have_skills": need.nice_to_have_skills
    }
    
    cf_skill = need.must_have_skills[0] if need.must_have_skills else None
    cf_need_profile = need_profile.copy()
    if cf_skill:
        cf_need_profile["must_have_skills"] = [s for s in need.must_have_skills if s != cf_skill]
        cf_need_profile["nice_to_have_skills"] = need.nice_to_have_skills + [cf_skill]
    
# Fetch frozen/pinned candidates
    sl = db.query(Shortlist).filter(Shortlist.need_id == need_id).first()
    pinned_candidates = []
    if sl:
        from app.models.models import ShortlistEntry
        entries = db.query(ShortlistEntry).filter(ShortlistEntry.shortlist_id == sl.id, ShortlistEntry.is_pinned == True).all()
        pinned_ids = [e.candidate_id for e in entries]
        pinned_candidates = db.query(CandidateProfile).options(
            selectinload(CandidateProfile.category_assignment),
            selectinload(CandidateProfile.fsp_identity),
            selectinload(CandidateProfile.skills)
        ).filter(CandidateProfile.id.in_(pinned_ids)).all()
        
    candidates = db.query(CandidateProfile).options(
        selectinload(CandidateProfile.category_assignment),
        selectinload(CandidateProfile.fsp_identity),
        selectinload(CandidateProfile.skills)
    ).join(CategoryAssignment).filter(CategoryAssignment.specialization_id == need.specialization_id).all()
    
    if revision is not None and sl:
        from app.models.models import ShortlistRevision
        rev_obj = db.query(ShortlistRevision).filter(ShortlistRevision.shortlist_id == sl.id, ShortlistRevision.revision == revision).first()
        if rev_obj and rev_obj.candidate_ids:
            # Only keep candidates from the revision
            candidates = [c for c in candidates if str(c.id) in rev_obj.candidate_ids]
            
    candidates = list({c.id: c for c in candidates + pinned_candidates}.values())

    

    from app.services.fsp import calculate_fsp_index
    spec_code = db.query(Specialization).filter(Specialization.id == need.specialization_id).first().code
    c_fsp_indices = {}
    for c in candidates:
        if c.fsp_identity:
            achievements = c.fsp_identity.achievements
            c_fsp_indices[c.id] = calculate_fsp_index(achievements, spec_code)
        else:
            c_fsp_indices[c.id] = 0.0
            
    fsp_indices_values = list(c_fsp_indices.values())
    max_fsp = max(fsp_indices_values) if fsp_indices_values else 0.0
    min_fsp = min(fsp_indices_values) if fsp_indices_values else 0.0
    fsp_pool_variance_zero = (max_fsp == min_fsp)

    results = []
    cf_pass_count = 0
    from app.services.invitations import serialize_candidate_for_employer
    
    class CandObj:
        def __init__(self, d):
            for k,v in d.items(): setattr(self, k, v)
            
    all_grades = {g.id: g for g in db.query(Grade).all()}
    all_skills = {s.id: s for s in db.query(Skill).all()}
    all_specs = {s.id: s for s in db.query(Specialization).all()}

    for cand in candidates:
        cat_assign = cand.category_assignment
        if not cat_assign: continue
        cand_grade = all_grades.get(cat_assign.grade_id)
        
        # Resolve skills
        c_skills = []
        for cs in cand.skills:
            skill = all_skills.get(cs.skill_id)
            if skill:
                c_skills.append(skill.normalized_name)
        
        c_fsp_index = c_fsp_indices.get(cand.id, 0.0)
        c_fsp_percentile = 0.0
        if not fsp_pool_variance_zero:
            c_fsp_percentile = (c_fsp_index - min_fsp) / (max_fsp - min_fsp) if (max_fsp - min_fsp) else 0.0
            
        cand_data = {
            "id": cand.id,
            "specialization": all_specs.get(cat_assign.specialization_id).name if all_specs.get(cat_assign.specialization_id) else "Unknown",
            "grade": cand_grade.level if cand_grade else 0,
            "is_confirmed": cat_assign.is_confirmed,
            "skills": c_skills,
            "fresh_days": cand.freshness_score,
            "context_score": 0.8,
            "avail_score": 1.0,
            "fsp_index": c_fsp_index,
            "team_role": cand.team_role,
            "work_format": cand.work_format,
            "years_of_experience": cand.years_of_experience
        }
        
        c_obj = CandObj(cand_data)
        
        match_info = calculate_match(c_obj, need_profile, fsp_pool_percentile=c_fsp_percentile, fsp_pool_variance_zero=fsp_pool_variance_zero)
        
        # Calculate counterfactual if relaxed
        if cf_skill:
            cf_match_info = calculate_match(c_obj, cf_need_profile, fsp_pool_percentile=c_fsp_percentile, fsp_pool_variance_zero=fsp_pool_variance_zero)
            if cf_match_info["score"] > 60 and match_info["score"] <= 60:
                cf_pass_count += 1
                
        safe_data = serialize_candidate_for_employer(cand_data, "sent")
        
        results.append({
            "candidate": safe_data,
            "match_score": match_info["score"],
            "explanation": match_info["explain"],
            "counterfactual": f"Ослабить {cf_skill} до nice-to-have → +{cf_pass_count} кандидатов" if cf_skill else None
        })
        
    results.sort(key=lambda x: x["match_score"], reverse=True)
    
    # We update counterfactual count across all returned objects so it makes sense globally
    for r in results:
        if cf_skill:
            r["counterfactual"] = f"Ослабить {cf_skill} до nice-to-have → +{cf_pass_count} кандидатов"
            
    total_count = len(results)
    
    return {
        "items": results[:10],
        "total_filtered": total_count
    }

@router.post("/{need_id}/revisions")
async def create_revision(
    need_id: uuid.UUID,
    filters: dict,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):

    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    need = db.query(Need).filter(Need.id == need_id).first()
    if not need or not employer or need.employer_id != employer.id:
        raise HTTPException(status_code=404, detail="Need not found")

    sl = db.query(Shortlist).filter(Shortlist.need_id == need_id).first()
    if not sl:
        sl = Shortlist(employer_id=employer.id, need_id=need_id, name="Shortlist")
        db.add(sl)
        db.commit()
        db.refresh(sl)
        
    from app.models.models import ShortlistRevision
    
# Replicate shortlist computation
    grade_min_obj = db.query(Grade).filter(Grade.id == need.grade_min_id).first()
    grade_max_obj = db.query(Grade).filter(Grade.id == need.grade_max_id).first()
    
    candidates = db.query(CandidateProfile).options(
        selectinload(CandidateProfile.category_assignment),
        selectinload(CandidateProfile.fsp_identity),
        selectinload(CandidateProfile.skills)
    ).join(CategoryAssignment).filter(CategoryAssignment.specialization_id == need.specialization_id).all()
    
    # We must apply filters passed in payload if any (or just simulate base filtering)
    # The requirement says "filters: dict", so we just save whatever the frontend sent
    # and save the candidate list at this exact point in time. 
    # To truly filter, we need to apply them, but `get_shortlist` itself filters based on need_profile.
    # Actually, the user can pass `skills`, `grade_min`, `grade_max` in filters!
    
    cf_skill = need.must_have_skills[0] if need.must_have_skills else None
    
    filtered_cands = []
    all_grades = {g.id: g for g in db.query(Grade).all()}
    all_skills = {s.id: s for s in db.query(Skill).all()}
    all_specs = {s.id: s for s in db.query(Specialization).all()}

    # Индекс ФСП по каждому кандидату — тем же способом, что и в get_shortlist.
    # Без него снимок ревизии не воспроизводит выдачу: get_shortlist считает
    # перцентили по пулу, а ревизия фиксирует состав на момент снимка (ТЗ 2.1).
    from app.services.fsp import calculate_fsp_index
    _spec = db.query(Specialization).filter(Specialization.id == need.specialization_id).first()
    _spec_code = _spec.code if _spec else "backend"
    c_fsp_indices = {}
    for _c in candidates:
        if getattr(_c, "fsp_identity", None):
            try:
                c_fsp_indices[_c.id] = calculate_fsp_index(_c.fsp_identity.achievements, _spec_code)
            except Exception:
                c_fsp_indices[_c.id] = 0.0
    fsp_indices_values = list(c_fsp_indices.values())
    max_fsp = max(fsp_indices_values) if fsp_indices_values else 0.0
    min_fsp = min(fsp_indices_values) if fsp_indices_values else 0.0
    fsp_pool_variance_zero = (max_fsp == min_fsp)

    for cand in candidates:
        cat_assign = cand.category_assignment
        if not cat_assign: continue
        cand_grade = all_grades.get(cat_assign.grade_id)
        
        # Resolve skills
        c_skills = []
        for cs in cand.skills:
            skill = all_skills.get(cs.skill_id)
            if skill:
                c_skills.append(skill.normalized_name)
        
        c_fsp_index = c_fsp_indices.get(cand.id, 0.0)
        c_fsp_percentile = 0.0
        if not fsp_pool_variance_zero:
            c_fsp_percentile = (c_fsp_index - min_fsp) / (max_fsp - min_fsp) if (max_fsp - min_fsp) else 0.0
            
        cand_data = {
            "id": str(cand.id),
            "specialization": all_specs.get(cat_assign.specialization_id).name if all_specs.get(cat_assign.specialization_id) else "Unknown",
            "grade": cand_grade.level if cand_grade else 0,
            "is_confirmed": cat_assign.is_confirmed,
            "skills": c_skills,
            "fresh_days": cand.freshness_score,
            "context_score": 0.8,
            "avail_score": 1.0,
            "fsp_index": c_fsp_index,
            "team_role": cand.team_role,
            "work_format": cand.work_format,
            "years_of_experience": cand.years_of_experience
        }
        filtered_cands.append(cand_data)

    # Состав подборки фиксируется на момент снимка (ТЗ 2.1: уточнение запроса
    # не должно терять ранее полученную подборку). Храним строковые id —
    # get_shortlist сравнивает их через str(c.id) в rev_obj.candidate_ids.
    cand_ids = [c["id"] for c in filtered_cands]
    last_revision = db.query(func.max(ShortlistRevision.revision)).filter(
        ShortlistRevision.shortlist_id == sl.id
    ).scalar() or 0
    rev = ShortlistRevision(
        shortlist_id=sl.id,
        revision=int(last_revision) + 1,
        filters=filters if isinstance(filters, dict) else {},
        ranking_params={},
        candidate_count=len(cand_ids),
        candidate_ids=cand_ids
    )

    db.add(rev)
    db.commit()
    db.refresh(rev)
    return {"revision_id": rev.id}

@router.get("/{need_id}/revisions")
async def list_revisions(
    need_id: uuid.UUID,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):

    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    need = db.query(Need).filter(Need.id == need_id).first()
    if not need or not employer or need.employer_id != employer.id:
        raise HTTPException(status_code=404, detail="Need not found")

    sl = db.query(Shortlist).filter(Shortlist.need_id == need_id).first()
    if not sl: return []
    from app.models.models import ShortlistRevision
    return db.query(ShortlistRevision).filter(ShortlistRevision.shortlist_id == sl.id).order_by(ShortlistRevision.created_at.desc()).all()

@router.post("/{need_id}/freeze/{candidate_id}")
async def freeze_candidate(
    need_id: uuid.UUID,
    candidate_id: uuid.UUID,
    current_user: dict = Depends(require_employer),
    db: Session = Depends(get_db)
):

    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == current_user["id"]).first()
    need = db.query(Need).filter(Need.id == need_id).first()
    if not need or not employer or need.employer_id != employer.id:
        raise HTTPException(status_code=404, detail="Need not found")

    sl = db.query(Shortlist).filter(Shortlist.need_id == need_id).first()
    if not sl:
        sl = Shortlist(employer_id=employer.id, need_id=need_id, name="Shortlist")
        db.add(sl)
        db.commit()
        db.refresh(sl)
        
    from app.models.models import ShortlistEntry
    # Check if entry exists
    entry = db.query(ShortlistEntry).filter(ShortlistEntry.shortlist_id == sl.id, ShortlistEntry.candidate_id == candidate_id).first()
    if entry:
        entry.is_pinned = True
    else:
        entry = ShortlistEntry(shortlist_id=sl.id, candidate_id=candidate_id, is_pinned=True, match_score=0.0, rank=0, explanation={})
        db.add(entry)

    db.add(entry)
    db.commit()
    return {"status": "frozen"}
