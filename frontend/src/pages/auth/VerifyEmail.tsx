import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Button, Card, CardContent } from '@/design/components'
import { useConfirmEmail } from '@/api'
import uiCopy from '../../../../content/ui-copy.ru.json'

const copy = uiCopy.screens['auth.verify-email']

export default function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const email = searchParams.get('email') || ''
  const token = searchParams.get('token')
  
  const confirmEmail = useConfirmEmail()
  const [confirmed, setConfirmed] = useState(false)
  const [error, setError] = useState('')

  // Auto-confirm if token is in URL (clicked dev link)
  useEffect(() => {
    if (token && !confirmed && !confirmEmail.isPending) {
      confirmEmail.mutate(
        { token },
        {
          onSuccess: () => {
            setConfirmed(true)
            // Auto-redirect to onboarding after 2 seconds
            setTimeout(() => {
              const role = localStorage.getItem('user_role') || 'candidate'
              if (role === 'candidate') {
                navigate('/candidate/onboarding/survey')
              } else {
                navigate('/employer/dashboard')
              }
            }, 2000)
          },
          onError: (err: any) => {
            setError(err.detail || copy.errors.invalid)
          },
        }
      )
    }
  }, [token, confirmed])

  // Get dev link from sessionStorage
  const devLink = sessionStorage.getItem('confirmation_link')

  if (confirmed) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-secondary-dark via-secondary-base to-primary-accent flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent>
            <div className="text-center">
              <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">✓ {copy.success}</h2>
              <p className="text-gray-600">Переходим к настройке профиля...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-secondary-dark via-secondary-base to-primary-accent flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent>
            <div className="text-center">
              <div className="mx-auto w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Ошибка подтверждения</h2>
              <p className="text-gray-600 mb-6">{error}</p>
              <Button
                variant="primary"
                onClick={() => navigate('/auth/register')}
              >
                Зарегистрироваться заново
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-secondary-dark via-secondary-base to-primary-accent flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardContent>
          <div className="text-center mb-6">
            <div className="mx-auto w-16 h-16 bg-primary-lighter rounded-full flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-primary-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">{copy.title}</h2>
            <p className="text-gray-600">{copy.subtitle.replace('{email}', email)}</p>
          </div>

          {/* Показываем подсказку, если бэкенд вернул ссылку. Условие намеренно
              НЕ завязано на import.meta.env.DEV: в собранной версии этот флаг
              всегда false, блок вырезался при сборке — и в локальной демонстрации
              не оставалось способа подтвердить адрес, кроме консоли сервера.
              Бэкенд отдаёт confirmation_link ТОЛЬКО при DEV_MODE=true, поэтому
              наличие ссылки само по себе означает демонстрационный режим. */}
          {devLink && (
            <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-sm text-yellow-800 font-medium mb-2">🔧 Демонстрационный режим</p>
              <p className="text-xs text-yellow-700 mb-3">
                Письма не отправляются — SMTP не подключён. Ссылка ниже та же, что
                сервер вывел в консоль.
              </p>
              {/* Ссылка ведёт на зарегистрированный клиентский маршрут /auth/verify-email,
                  который сам прочитает ?token= и вызовет подтверждение. Прежний вариант
                  (replace origin → /auth/confirm-email) вёл на незарегистрированный путь
                  и упирался в 404 — а это единственный способ подтвердить адрес в демо,
                  где SMTP нет. Извлекаем токен, а не подменяем origin: так ссылка не
                  зависит от хоста и порта. */}
              <a
                href={`/auth/verify-email?token=${devLink.split('token=')[1] ?? ''}`}
                className="block w-full px-4 py-2 bg-primary-accent text-white rounded-md text-center hover:bg-primary-light transition-colors text-sm font-medium"
              >
                Подтвердить email
              </a>
            </div>
          )}

          <p className="mt-6 text-xs text-center text-gray-500">
            Письмо может попасть в спам. Проверьте папку «Промоакции» или «Оповещения».
          </p>

          <div className="mt-4 text-center">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/auth/login')}
            >
              Уже подтвердили? Войти
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
