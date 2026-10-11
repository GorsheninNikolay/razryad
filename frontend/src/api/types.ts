// API types based on contract/openapi-draft.yaml

export interface User {
  id: string
  email: string
  role: 'candidate' | 'employer'
  email_verified: boolean
  created_at: string
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
  confirmation_link?: string  // Only in DEV_MODE for register
}

export interface RegisterRequest {
  email: string
  password: string
  role: 'candidate' | 'employer'
}

export interface LoginRequest {
  email: string
  password: string
}

export interface CandidateProfile {
  id: string
  user_id: string
  first_name?: string
  last_name?: string
  city?: string
  timezone?: string
  specialization_id?: string
  subspecialization_id?: string
  claimed_grade?: string
  skills: string[]
  experience_years?: number
  years_of_experience?: number
  team_role?: string
  work_format?: string
  industry?: string
  bio?: string
  category_id?: string
  category_confirmed: boolean
  fsp_id?: string
  fsp_verified: boolean
  visible_to_employers: boolean
  created_at: string
  updated_at: string
}

export interface EmployerProfile {
  id: string
  user_id: string
  company_name: string
  contact_person: string
  created_at: string
  updated_at: string
}

export interface AssessmentSession {
  session_id: string
  candidate_id?: string
  target_grade?: string
  status?: 'in_progress' | 'completed' | 'expired'
  current_item?: number
  total_items?: number
  expires_at: string
  created_at?: string
  completed_at?: string
}

export interface AssessmentItemContent {
  stem: string
  options?: string[]  // For mcq type
  code?: string       // For code_output type
  // Reference fields that should never be displayed:
  correct_index?: number
  expected?: string
  rubric?: string
  accepted_keywords?: string[]
}

export interface AssessmentItem {
  item_id: string
  item_version_id: string
  sequence: number
  content: AssessmentItemContent
}

export interface AnswerResponse {
  is_correct: boolean
  current_theta: number
  current_se: number
  session_status: 'active' | 'completed' | 'expired'
}

export interface AssessmentResult {
  session_id: string
  assigned_grade: string | null
  assigned_grade_id: string | null
  is_confirmed: boolean
  borderline: boolean
  category: { specialization: string; grade: string } | null
  final_theta: number | null
  final_se: number | null
  grade_probabilities: Record<string, number>
  offered_lower_grade: string | null
  reason: string | null
}

export interface Need {
  id: string
  employer_id: string
  description: string
  specialization_id?: string
  grades: string[]
  required_skills: string[]
  optional_skills: string[]
  team_role?: string
  work_format?: string
  domain?: string
  salary_min: number
  salary_max: number
  created_at: string
}

export interface Shortlist {
  id: string
  need_id: string
  candidates: ShortlistCandidate[]
  created_at: string
}

export interface ShortlistCandidate {
  candidate_id: string
  pseudonym: string
  category: string
  grade: string
  confirmed: boolean
  skills: string[]
  match_score: number
  explanation: string
}

export interface ShortlistExplanation { matched_skills?: string[]; missing_must_have?: string[]; fsp_achievements?: string[]; freshness?: string; category_rank?: number }

export interface Invitation {
  subject?: string
  message?: string
  salary_min?: number
  salary_max?: number
  id: string
  employer_id: string
  candidate_id: string
  offer_description: string
  company_name: string
  contact_method: string
  contact_person?: string
  status: 'sent' | 'viewed' | 'accepted' | 'declined' | 'expired'
  created_at: string
  updated_at: string
}

export interface PaginatedResponse<T> {
  data: T[]
  pagination: {
    next_cursor: string | null
    has_more: boolean
  }
}

export interface ApiError {
  type: string
  title: string
  status: number
  detail?: string
  instance?: string
}
