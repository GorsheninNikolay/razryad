"""Resume upload and standard profile PDF endpoints."""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from app.services.resume import extract_text, parse_resume, generate_profile_pdf
router=APIRouter()
@router.post('/resume/parse')
async def parse_resume_file(file:UploadFile=File(...)):
 data=await file.read()
 try:return parse_resume(extract_text(data))
 except (ValueError,RuntimeError) as e: raise HTTPException(400,str(e))
@router.post('/profile.pdf')
async def profile_pdf(profile:dict):
 return Response(generate_profile_pdf(profile),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename=razryad-profile.pdf'})
