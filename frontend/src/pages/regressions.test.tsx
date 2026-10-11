import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import CandidateInvitations from './candidate/Invitations'
import { Invitations, Shortlist } from './employer/EmployerPages'
import type { Invitation } from '@/api/types'

vi.mock('@/api/msw', () => ({startMockServiceWorker: vi.fn()}))

const base: Invitation = {
  id: 'invitation-1', employer_id: 'employer-1', candidate_id: 'candidate-1',
  status: 'viewed', company_name: 'Example Company', subject: 'Backend offer',
  message: 'Build distributed systems', salary_min: 100000, salary_max: 200000,
  contact_method: 'employer@example.com', created_at: '2026-10-01T00:00:00Z',
}

function mount(page: React.ReactNode, route: string) {
  const client = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}})
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route]}>{page}</MemoryRouter></QueryClientProvider>)
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('candidate invitations', () => {
  it.each(['sent', 'viewed'] as const)('can accept %s and reads subject/message', async status => {
    let current: Invitation = {...base, status}
    const fetch = vi.fn(async (_url: unknown, options?: RequestInit) => {
      if (options?.method === 'POST') {
        current = {...current, status: 'accepted'}
        return new Response(JSON.stringify({status: 'accepted'}), {status: 200})
      }
      return new Response(JSON.stringify([current]), {status: 200})
    })
    vi.stubGlobal('fetch', fetch)
    mount(<CandidateInvitations />, '/candidate/invitations')
    expect(await screen.findByText('Backend offer')).toBeTruthy()
    expect(screen.getByText('Build distributed systems')).toBeTruthy()
    expect(screen.getByRole('button', {name: 'Отклонить'})).toBeTruthy()
    fireEvent.click(screen.getByRole('button', {name: 'Принять'}))
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/invitations/invitation-1/accept', expect.objectContaining({method: 'POST'})))
    await waitFor(() => expect(screen.queryByRole('button', {name: 'Принять'})).toBeNull())
  })
  it.each(['declined', 'expired', 'withdrawn', 'accepted', 'hired'] as const)('does not offer actions for %s', async status => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([{...base, status}]), {status: 200})))
    mount(<CandidateInvitations />, '/candidate/invitations')
    await screen.findByText('Backend offer')
    expect(screen.queryByRole('button', {name: 'Принять'})).toBeNull()
    expect(screen.queryByRole('button', {name: 'Отклонить'})).toBeNull()
  })
})

describe('employer contacts', () => {
  it.each(['accepted', 'hired'] as const)('shows candidate contacts in %s, not employer email', async status => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([{...base, status, candidate_fio: 'Candidate Name', candidate_contacts: {email: 'candidate@example.com', phone: '+79990000000'}}]), {status: 200})))
    mount(<Invitations />, '/employer/invitations')
    expect(await screen.findByText('Candidate Name')).toBeTruthy()
    expect(screen.getByText('candidate@example.com · +79990000000')).toBeTruthy()
    expect(screen.queryByText('employer@example.com')).toBeNull()
  })
  it('does not render contacts before acceptance even if a response contains them', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([{...base, candidate_pseudonym: 'Backend · Middle · #1234', candidate_fio: 'Private Name', candidate_contacts: {email: 'private@example.com'}}]), {status: 200})))
    mount(<Invitations />, '/employer/invitations')
    await screen.findByText('Контакты скрыты до принятия')
    expect(screen.queryByText('private@example.com')).toBeNull()
    expect(screen.queryByText('Private Name')).toBeNull()
  })
})

describe('shortlist contract', () => {
  it('renders confirmed grade independently of grade_match with explanation and rounded score', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({items: [{candidate: {id: '1', pseudonym: 'Senior candidate', grade: 'Senior', is_confirmed: true}, match_score: 83.1968953915127, explanation: {grade_match: .8, skills_matched: ['python'], skills_missing: ['docker'], fsp_highlights: ['Algorithm Cup'], freshness: 0}, counterfactual: 'Relax docker requirement'}], total_filtered: 1}), {status: 200})))
    mount(<Shortlist />, '/employer/shortlist?need=need-1')
    expect(await screen.findByText('✓ Грейд подтверждён · Senior')).toBeTruthy()
    expect(screen.getByText('Почему в подборке · 83 из 100')).toBeTruthy()
    expect(screen.getByText('✓ Совпали: python')).toBeTruthy()
    expect(screen.getByText('⚠ Не покрыто: docker')).toBeTruthy()
    expect(screen.getByText('🏆 ФСП: Algorithm Cup')).toBeTruthy()
    expect(screen.getByText('◷ Свежесть: 0')).toBeTruthy()
    expect(screen.getByText('💡 Relax docker requirement')).toBeTruthy()
  })
  it.each([false, undefined])('does not infer confirmation from grade_match when flag is %s', async is_confirmed => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({items: [{candidate: {id: '1', grade: 'Middle', is_confirmed}, match_score: 0, explanation: {grade_match: 1}}], total_filtered: 1}), {status: 200})))
    mount(<Shortlist />, '/employer/shortlist?need=need-1')
    await screen.findByText('Почему в подборке · 0 из 100')
    expect(screen.queryByText(/✓ Грейд подтверждён/)).toBeNull()
    expect(screen.getByText(is_confirmed === false ? 'Предварительный · Middle' : 'Статус грейда не указан · Middle')).toBeTruthy()
  })
})
