import { http, HttpResponse } from 'msw'
import type {
  AuthResponse,
  CandidateProfile,
  EmployerProfile,
  AssessmentSession,
  AssessmentItem,
  AssessmentResult,
  Need,
  Shortlist,
  Invitation,
} from './types'

const API_BASE_URL = '/api/v1'

// Mock data
const mockUser = {
  id: 'user-1',
  email: 'test@example.com',
  role: 'candidate' as const,
  email_verified: true,
  created_at: new Date().toISOString(),
}

const mockCandidateProfile: CandidateProfile = {
  id: 'profile-1',
  user_id: 'user-1',
  first_name: 'Иван',
  last_name: 'Петров',
  city: 'Москва',
  timezone: 'Europe/Moscow',
  specialization_id: 'backend',
  subspecialization_id: 'backend-python',
  claimed_grade: 'middle',
  skills: ['Python', 'FastAPI', 'PostgreSQL', 'Docker'],
  experience_years: 3,
  team_role: 'backend-developer',
  work_format: 'hybrid',
  category_id: 'cat-middle-backend-python',
  category_confirmed: true,
  fsp_id: 'FSP-12345',
  fsp_verified: true,
  visible_to_employers: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

const mockEmployerProfile: EmployerProfile = {
  id: 'employer-1',
  user_id: 'user-2',
  company_name: 'ТехКомпания',
  contact_person: 'Мария Смирнова',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

const mockAssessmentSession: AssessmentSession = {
  session_id: 'session-1',
  candidate_id: 'profile-1',
  target_grade: 'middle',
  status: 'in_progress',
  current_item: 3,
  total_items: 15,
  expires_at: new Date(Date.now() + 2700000).toISOString(),
  created_at: new Date().toISOString(),
}

const mockAssessmentItems: AssessmentItem[] = [
  {
    item_id: 'item-1',
    item_version_id: 'v1',
    sequence: 1,
    content: {
      stem: 'Какой HTTP-код возвращается при успешном создании ресурса?',
      options: ['200 OK', '201 Created', '202 Accepted', '204 No Content'],
    },
  },
  {
    item_id: 'item-2',
    item_version_id: 'v1',
    sequence: 2,
    content: {
      stem: 'Какая структура данных обеспечивает O(1) доступ по ключу?',
      options: ['Массив', 'Связный список', 'Хеш-таблица', 'Дерево'],
    },
  },
]

const mockInvitations: Invitation[] = [
  {
    id: 'inv-1',
    employer_id: 'employer-1',
    candidate_id: 'profile-1',
    offer_description: 'Backend-разработчик в команду fintech-продукта',
    salary_min: 200000,
    salary_max: 280000,
    company_name: 'ТехКомпания',
    contact_method: 'hr@techcompany.ru',
    status: 'sent',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
]

export const handlers = [
  // Auth endpoints
  http.post(`${API_BASE_URL}/auth/register`, async ({ request }) => {
    const body = await request.json() as { email: string; password: string; role: string }
    const response: AuthResponse = {
      access_token: 'mock-access-token',
      refresh_token: 'mock-refresh-token',
      token_type: 'Bearer',
      expires_in: 3600,
      user: { ...mockUser, email: body.email, role: body.role as 'candidate' | 'employer' },
    }
    return HttpResponse.json(response)
  }),

  http.post(`${API_BASE_URL}/auth/login`, async () => {
    const response: AuthResponse = {
      access_token: 'mock-access-token',
      refresh_token: 'mock-refresh-token',
      token_type: 'Bearer',
      expires_in: 3600,
      user: mockUser,
    }
    return HttpResponse.json(response)
  }),

  http.post(`${API_BASE_URL}/auth/refresh`, async () => {
    return HttpResponse.json({
      access_token: 'mock-access-token-refreshed',
      refresh_token: 'mock-refresh-token-refreshed',
    })
  }),

  // Profile endpoints
  http.get(`${API_BASE_URL}/profiles/candidate/me`, () => {
    return HttpResponse.json(mockCandidateProfile)
  }),

  http.get(`${API_BASE_URL}/profiles/employer/me`, () => {
    return HttpResponse.json(mockEmployerProfile)
  }),

  http.put(`${API_BASE_URL}/profiles/candidate/me`, async ({ request }) => {
    const body = (await request.json()) as Partial<CandidateProfile>
    return HttpResponse.json({ ...mockCandidateProfile, ...body })
  }),

  http.put(`${API_BASE_URL}/profiles/employer/me`, async ({ request }) => {
    const body = (await request.json()) as Partial<EmployerProfile>
    return HttpResponse.json({ ...mockEmployerProfile, ...body })
  }),

  // Assessment endpoints
  http.post(`${API_BASE_URL}/assessment/sessions`, () => {
    return HttpResponse.json(mockAssessmentSession)
  }),

  http.get(`${API_BASE_URL}/assessment/sessions/:sessionId`, () => {
    return HttpResponse.json(mockAssessmentSession)
  }),

  http.get(`${API_BASE_URL}/assessment/sessions/:sessionId/next-item`, () => {
    return HttpResponse.json(mockAssessmentItems[0])
  }),

  http.post(`${API_BASE_URL}/assessment/sessions/:sessionId/answers`, () => {
    return HttpResponse.json({ success: true })
  }),

  http.post(`${API_BASE_URL}/assessment/sessions/:sessionId/complete`, () => {
    const result: AssessmentResult = {
      session_id: 'session-1',
      assigned_grade: 'middle',
      assigned_grade_id: 'grade-middle',
      is_confirmed: true,
      borderline: false,
      category: { specialization: 'backend', grade: 'middle' },
      final_theta: 0.75,
      final_se: 0.3,
      grade_probabilities: { junior: 0.1, middle: 0.85, senior: 0.05 },
      offered_lower_grade: null,
      reason: 'Грейд присвоен по итоговой оценке способности и стандартной ошибке.',
    }
    return HttpResponse.json(result)
  }),

  // Invitations
  http.get(`${API_BASE_URL}/invitations/incoming`, () => {
    return HttpResponse.json({
      data: mockInvitations,
      pagination: { next_cursor: null, has_more: false },
    })
  }),

  http.post(`${API_BASE_URL}/invitations/:invitationId/accept`, () => {
    return HttpResponse.json({ ...mockInvitations[0], status: 'accepted' })
  }),

  http.post(`${API_BASE_URL}/invitations/:invitationId/decline`, () => {
    return HttpResponse.json({ ...mockInvitations[0], status: 'declined' })
  }),

  // Needs and shortlists (for employer)
  http.post(`${API_BASE_URL}/needs`, async ({ request }) => {
    const body = (await request.json()) as Partial<Need>
    return HttpResponse.json({ ...body, id: 'need-1', created_at: new Date().toISOString() })
  }),

  http.post(`${API_BASE_URL}/needs/:needId/shortlist`, () => {
    const shortlist: Shortlist = {
      id: 'shortlist-1',
      need_id: 'need-1',
      candidates: [
        {
          candidate_id: 'cand-1',
          pseudonym: 'Кандидат #1234',
          category: 'Middle Backend Python',
          grade: 'middle',
          confirmed: true,
          skills: ['Python', 'FastAPI', 'PostgreSQL'],
          match_score: 0.92,
          explanation: 'Подтверждённый грейд, полное совпадение по стеку',
        },
      ],
      created_at: new Date().toISOString(),
    }
    return HttpResponse.json(shortlist)
  }),

  http.post(`${API_BASE_URL}/invitations`, async ({ request }) => {
    const body = (await request.json()) as Partial<Invitation>
    return HttpResponse.json({ ...body, id: 'inv-new', status: 'sent' as const, created_at: new Date().toISOString() })
  }),
]
