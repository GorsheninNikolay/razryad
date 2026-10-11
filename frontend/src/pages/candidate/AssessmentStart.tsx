import { useNavigate } from 'react-router-dom'
import { Button, Card, CardContent } from '@/design/components'
import { useCandidateProfile, useCreateAssessmentSession } from '@/api'

export default function AssessmentStart() {
  const navigate = useNavigate()
  const { data: profile } = useCandidateProfile()
  const createSession = useCreateAssessmentSession()
  
  const targetGrade = profile?.claimed_grade || 'Middle'

  const handleStart = () => {
    if (!profile?.specialization_id || !profile?.claimed_grade) {
      alert('Завершите онбординг перед началом теста')
      return
    }
    
    createSession.mutate(
      {
        target_grade: profile.claimed_grade,
      },
      {
        onSuccess: (data) => {
          navigate(`/candidate/assessment/session?sessionId=${data.session_id}`)
        },
      }
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4">
        <Card>
          <CardContent>
            <div className="text-center mb-8">
              <div className="mx-auto w-20 h-20 bg-primary-lighter rounded-full flex items-center justify-center mb-4">
                <svg className="w-10 h-10 text-primary-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                Проверка грейда: {targetGrade}
              </h1>
              <p className="text-gray-600">
                12–18 заданий, до 45 минут. Отвечайте самостоятельно.
              </p>
            </div>

            <div className="space-y-4 mb-8">
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-6 h-6 bg-secondary-light text-white rounded-full flex items-center justify-center text-sm font-medium">
                  1
                </div>
                <div>
                  <h3 className="font-medium text-gray-900">Адаптивное тестирование</h3>
                  <p className="text-sm text-gray-600">
                    Задания подбираются индивидуально на основе ваших ответов
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-6 h-6 bg-secondary-light text-white rounded-full flex items-center justify-center text-sm font-medium">
                  2
                </div>
                <div>
                  <h3 className="font-medium text-gray-900">Одно задание за раз</h3>
                  <p className="text-sm text-gray-600">
                    После ответа вернуться к заданию нельзя
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-6 h-6 bg-secondary-light text-white rounded-full flex items-center justify-center text-sm font-medium">
                  3
                </div>
                <div>
                  <h3 className="font-medium text-gray-900">Таймер на сессию</h3>
                  <p className="text-sm text-gray-600">
                    Время ограничено, но не торопитесь — качество важнее скорости
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
              <p className="text-sm text-yellow-800">
                <strong>Важно:</strong> Результаты теста определяют ваш грейд. 
                Отвечайте самостоятельно, не используйте внешние источники.
              </p>
            </div>

            <Button
              variant="primary"
              size="lg"
              className="w-full"
              onClick={handleStart}
              loading={createSession.isPending}
            >
              Начать тест
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
