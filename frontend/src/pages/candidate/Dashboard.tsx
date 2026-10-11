import AppShell from '@/app/AppShell'
import { useCandidateProfile, useIncomingInvitations } from '@/api'
import { asList } from '@/api/normalize'
import type { Invitation } from '@/api/types'
import { Badge, Button, Skeleton } from '@/design/components'
import { Link } from 'react-router-dom'

export default function CandidateDashboard() {
  const { data: profile, isLoading: profileLoading } = useCandidateProfile()
  const { data: invitations, isLoading: invitationsLoading } = useIncomingInvitations()

  // Сервер отдаёт /invitations/incoming ПРОСТЫМ МАССИВОМ. Обращение к
  // invitations.data падало с TypeError и давало белый экран — нормализуем.
  const invitationList = asList<Invitation>(invitations)
  const newInvitationsCount = invitationList.filter((i) => i.status === 'sent').length

  // Determine onboarding status
  const hasIndustry = !!profile?.industry
  const hasSpecialization = !!profile?.specialization_id
  const hasSkills = profile?.skills && profile.skills.length > 0
  const hasClaimedGrade = !!profile?.claimed_grade
  
  // For showing the assessment link, require basic profile info (grade is optional for test)
  const canTakeAssessment = hasIndustry && hasSpecialization && hasSkills
  
  // For onboarding prompt, same requirement
  const onboardingComplete = canTakeAssessment

  // Determine next onboarding step
  const getNextOnboardingStep = () => {
    if (!hasIndustry || !hasSpecialization) return '/candidate/onboarding/survey'
    if (!hasClaimedGrade) return '/candidate/onboarding/grade'
    if (!hasSkills) return '/candidate/onboarding/profile'
    return '/candidate/onboarding/fsp'
  }

  return (
    <AppShell role="candidate">
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-900">Кабинет кандидата</h1>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Моя категория</h3>
            {profileLoading ? (
              <Skeleton className="h-8 w-48" />
            ) : profile?.category_id ? (
              <>
                <p className="text-2xl font-semibold text-primary-accent">
                  {profile.category_id}
                </p>
                {profile.category_confirmed && (
                  <Badge variant="confirmed" className="mt-2">✓ Подтверждено</Badge>
                )}
              </>
            ) : (
              <div>
                <p className="text-gray-500 mb-2">
                  {onboardingComplete ? 'Категория не назначена' : 'Завершите онбординг'}
                </p>
                {!onboardingComplete && (
                  <Link
                    to={getNextOnboardingStep()}
                    className="text-primary-accent hover:text-primary-light text-sm font-medium"
                  >
                    Продолжить настройку →
                  </Link>
                )}
              </div>
            )}
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Входящие приглашения</h3>
            {invitationsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <>
                <p className="text-3xl font-semibold text-gray-900">{newInvitationsCount}</p>
                <p className="mt-1 text-sm text-gray-500">новых</p>
              </>
            )}
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Опыт</h3>
            {profileLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <>
                <p className="text-3xl font-semibold text-gray-900">
                  {profile?.experience_years ?? '—'}
                </p>
                <p className="mt-1 text-sm text-gray-500">лет</p>
              </>
            )}
          </div>
        </div>

        {/* Assessment card */}
        {!profileLoading && canTakeAssessment && (
          <div className="bg-gradient-to-r from-primary-accent to-primary-light p-6 rounded-lg shadow text-white">
            <h2 className="text-xl font-semibold mb-2">Подтвердите свой грейд</h2>
            <p className="mb-4">
              {profile?.category_confirmed 
                ? 'Пройдите тест повторно для актуализации категории'
                : 'Пройдите тест для подтверждения грейда и получения верифицированной категории'}
            </p>
            <Link to="/candidate/assessment/start">
              <Button variant="primary" className="bg-white text-primary-accent hover:bg-gray-100">
                {profile?.category_confirmed ? 'Пройти тест повторно' : 'Начать тест'}
              </Button>
            </Link>
          </div>
        )}

        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Последние приглашения</h2>
          {invitationsLoading ? (
            <Skeleton className="h-20 w-full" />
          ) : invitationList.length ? (
            <div className="space-y-3">
              {invitationList.slice(0, 3).map((inv) => (
                <div key={inv.id} className="p-4 border border-gray-200 rounded-lg">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-medium text-gray-900">{inv.company_name}</p>
                      <p className="text-sm text-gray-600">{inv.offer_description}</p>
                    </div>
                    <Badge variant="status">{inv.status}</Badge>
                  </div>
                </div>
              ))}
              <Link to="/candidate/invitations" className="text-primary-accent hover:text-primary-light text-sm font-medium">
                Смотреть все →
              </Link>
            </div>
          ) : (
            <p className="text-gray-500">Пока нет приглашений. Поддерживайте профиль актуальным.</p>
          )}
        </div>
      </div>
    </AppShell>
  )
}
