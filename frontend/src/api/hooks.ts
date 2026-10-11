import { useQuery, useMutation, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query'
import { apiClient } from './client'
import type {
  AuthResponse,
  RegisterRequest,
  LoginRequest,
  CandidateProfile,
  AssessmentSession,
  AssessmentItem,
  AnswerResponse,
  AssessmentResult,
  Invitation,
  ShortlistItem,
} from './types'

// Auth hooks
export function useRegister(options?: UseMutationOptions<AuthResponse, Error, RegisterRequest>) {
  return useMutation({
    mutationFn: (data: RegisterRequest) => apiClient.post<AuthResponse>('/auth/register', data),
    ...options,
  })
}

export function useLogin(options?: UseMutationOptions<AuthResponse, Error, LoginRequest>) {
  return useMutation({
    mutationFn: (data: LoginRequest) => apiClient.post<AuthResponse>('/auth/login', data),
    ...options,
  })
}

// Email confirmation
export function useConfirmEmail(options?: UseMutationOptions<{ message: string; email: string; user_id: string }, Error, { token: string }>) {
  return useMutation({
    mutationFn: (data: { token: string }) => apiClient.post<{ message: string; email: string; user_id: string }>('/auth/confirm-email', data),
    ...options,
  })
}

// Profile hooks
export function useCandidateProfile(options?: UseQueryOptions<CandidateProfile, Error>) {
  return useQuery({
    queryKey: ['candidateProfile'],
    queryFn: () => apiClient.get<CandidateProfile>('/profiles/candidate/me'),
    ...options,
  })
}

export function useUpdateCandidateProfile(options?: UseMutationOptions<CandidateProfile, Error, Partial<CandidateProfile>>) {
  return useMutation({
    mutationFn: (data: Partial<CandidateProfile>) => apiClient.put<CandidateProfile>('/profiles/candidate/me', data),
    ...options,
  })
}

// Assessment hooks
export function useCreateAssessmentSession(options?: UseMutationOptions<AssessmentSession, Error, { target_grade: string }>) {
  return useMutation({
    mutationFn: (data) => apiClient.post<AssessmentSession>('/assessment/sessions', data),
    ...options,
  })
}

export function useAssessmentSession(sessionId: string | null, options?: UseQueryOptions<AssessmentSession, Error>) {
  return useQuery({
    queryKey: ['assessmentSession', sessionId],
    queryFn: () => apiClient.get<AssessmentSession>(`/assessment/sessions/${sessionId}`),
    enabled: !!sessionId,
    ...options,
  })
}

export function useNextAssessmentItem(sessionId: string | null, options?: UseQueryOptions<AssessmentItem, Error>) {
  return useQuery({
    queryKey: ['assessmentItem', sessionId],
    queryFn: () => apiClient.get<AssessmentItem>(`/assessment/sessions/${sessionId}/next-item`),
    enabled: !!sessionId,
    ...options,
  })
}

export function useSubmitAnswer(options?: UseMutationOptions<AnswerResponse, Error, { sessionId: string; itemId: string; answer: number | string | number[] }>) {
  return useMutation({
    mutationFn: ({ sessionId, itemId, answer }) => 
      apiClient.post<AnswerResponse>(`/assessment/sessions/${sessionId}/answers`, { item_id: itemId, response_data: { answer } }),
    ...options,
  })
}

export function useCompleteAssessment(options?: UseMutationOptions<AssessmentResult, Error, string>) {
  return useMutation({
    mutationFn: (sessionId: string) => apiClient.post<AssessmentResult>(`/assessment/sessions/${sessionId}/complete`),
    ...options,
  })
}

// Employer workflow hooks. Payloads mirror the OpenAPI resources; unknown optional fields are preserved.
export interface NeedPayload { title: string; description: string; specialization_id: string; grade_min_id: string; grade_max_id: string; must_have_skills: string[]; nice_to_have_skills: string[]; salary_min: number; salary_max: number; work_format?: string; location?: string }
export interface EmployerNeedResult extends NeedPayload { id: string; employer_id: string; parsed_data?: { confidence?: Record<string, number>; extracted_skills?: string[] } }
export interface ShortlistResponse { items: ShortlistItem[]; total_filtered: number }
export function useCreateNeed(options?: UseMutationOptions<EmployerNeedResult, Error, NeedPayload>) { return useMutation({ mutationFn: (data: NeedPayload) => apiClient.post<EmployerNeedResult>('/needs/', data), ...options }) }
export function useNeeds(options?: Omit<UseQueryOptions<EmployerNeedResult[], Error>, 'queryKey'|'queryFn'>) { return useQuery({ queryKey: ['needs'], queryFn: () => apiClient.get<EmployerNeedResult[]>('/needs/'), ...options }) }
export function useNeed(needId: string | null, options?: UseQueryOptions<EmployerNeedResult, Error>) { return useQuery({ queryKey: ['need', needId], queryFn: () => apiClient.get<EmployerNeedResult>(`/needs/${needId}`), enabled: !!needId, ...options }) }
export function useRecommendedCategories(needId: string | null, options?: UseQueryOptions<{ categories?: unknown[] }|unknown[], Error>) { return useQuery({ queryKey: ['categories', needId], queryFn: () => apiClient.get<{ categories?: unknown[] }|unknown[]>(`/needs/${needId}/categories`), enabled: !!needId, ...options }) }
export function useShortlist(needId: string | null, options?: UseQueryOptions<ShortlistResponse, Error>) { return useQuery({ queryKey: ['shortlist', needId], queryFn: () => apiClient.get<ShortlistResponse>(`/shortlists/${needId}`), enabled: !!needId, ...options }) }
export function useSearchCandidates(params: Record<string, string | number | undefined>, options?: Omit<UseQueryOptions<unknown, Error>, 'queryKey' | 'queryFn'>) { const query = new URLSearchParams(Object.entries(params).filter(([,v]) => v !== undefined).map(([k,v]) => [k, String(v)])); return useQuery({ queryKey: ['candidateSearch', query.toString()], queryFn: () => apiClient.get<unknown>(`/search/?${query}`), ...options }) }
export function useCreateInvitation(options?: UseMutationOptions<Invitation, Error, Record<string, unknown>>) { return useMutation({ mutationFn: (data) => apiClient.post<Invitation>('/invitations/', data), ...options }) }
export function useSentInvitations(options?: UseQueryOptions<Invitation[], Error>) { return useQuery({ queryKey: ['sentInvitations'], queryFn: () => apiClient.get<Invitation[]>('/invitations/sent'), ...options }) }
export function useWithdrawInvitation(options?: UseMutationOptions<{status:string}, Error, string>) { return useMutation({ mutationFn: (id:string) => apiClient.post<{status:string}>(`/invitations/${id}/withdraw`), ...options }) }
export function useHireInvitation(options?: UseMutationOptions<{status:string}, Error, string>) { return useMutation({ mutationFn: (id:string) => apiClient.post<{status:string}>(`/invitations/${id}/hire`), ...options }) }
export function useInvitationHistory(id:string|null, options?: UseQueryOptions<Array<Record<string,unknown>>, Error>) { return useQuery({ queryKey:['invitationHistory',id], queryFn:()=>apiClient.get<Array<Record<string,unknown>>>(`/invitations/${id}/history`), enabled:!!id, ...options }) }
export function useVacancies(options?: UseQueryOptions<unknown[], Error>) { return useQuery({ queryKey: ['vacancies'], queryFn: () => apiClient.get<unknown[]>('/vacancies/'), ...options }) }
export function useCreateVacancy(options?: UseMutationOptions<unknown, Error, Record<string, unknown>>) { return useMutation({ mutationFn: (data) => apiClient.post('/vacancies/', data), ...options }) }
export function useUpdateVacancy(options?: UseMutationOptions<unknown, Error, { id:string; data:Record<string,unknown> }>) { return useMutation({ mutationFn: ({id,data}) => apiClient.put(`/vacancies/${id}`, data), ...options }) }
export function useApplications(vacancyId: string | null, options?: UseQueryOptions<unknown[], Error>) { return useQuery({ queryKey: ['applications', vacancyId], queryFn: () => apiClient.get<unknown[]>(`/applications/?vacancy_id=${vacancyId}`), enabled: !!vacancyId, ...options }) }

// Invitations hooks
export function useIncomingInvitations(options?: UseQueryOptions<Invitation[], Error>) {
  return useQuery({
    queryKey: ['incomingInvitations'],
    queryFn: () => apiClient.get<Invitation[]>('/invitations/incoming'),
    ...options,
  })
}

export function useAcceptInvitation(options?: UseMutationOptions<Invitation, Error, string>) {
  return useMutation({
    mutationFn: (invitationId: string) => apiClient.post<Invitation>(`/invitations/${invitationId}/accept`),
    ...options,
  })
}

export function useDeclineInvitation(options?: UseMutationOptions<Invitation, Error, string>) {
  return useMutation({
    mutationFn: (invitationId: string) => apiClient.post<Invitation>(`/invitations/${invitationId}/decline`),
    ...options,
  })
}

// FSP hooks
export function useLinkFSP(options?: UseMutationOptions<{ success: boolean; achievements?: any[] }, Error, { fsp_id: string }>) {
  return useMutation({
    mutationFn: (data) => apiClient.post('/fsp/link', data),
    ...options,
  })
}

export function useUnlinkFSP(options?: UseMutationOptions<{ message: string }, Error>) {
  return useMutation({
    mutationFn: () => apiClient.delete<{ message: string }>('/fsp/unlink'),
    ...options,
  })
}

export function useFSPStatus(options?: UseQueryOptions<{ linked: boolean; fsp_id?: string; achievements?: any[] }, Error>) {
  return useQuery({
    queryKey: ['fspStatus'],
    queryFn: () => apiClient.get<{ linked: boolean; fsp_id?: string; achievements?: any[] }>('/fsp/status'),
    ...options,
  })
}
