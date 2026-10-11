import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useRegister } from '@/api'
import { Button, Input, Card, CardContent } from '@/design/components'

export default function Register() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const registerMutation = useRegister()
  
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<'candidate' | 'employer'>(
    (searchParams.get('role') as 'candidate' | 'employer') || 'candidate'
  )

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    registerMutation.mutate(
      { email, password, role },
      {
        onSuccess: (data) => {
          // Store confirmation link for DEV_MODE
          if (data.confirmation_link) {
            sessionStorage.setItem('confirmation_link', data.confirmation_link)
          }
          
          // Redirect to email verification with email
          navigate(`/auth/verify-email?email=${encodeURIComponent(email)}`)
        },
      }
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-secondary-dark via-secondary-base to-primary-accent flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardContent>
          <div className="text-center mb-6">
            <h1 className="text-3xl font-bold text-primary-accent mb-2">РАЗРЯД</h1>
            <h2 className="text-xl font-semibold text-gray-900">Регистрация</h2>
            <p className="text-gray-600 mt-1">Создайте аккаунт за пару минут</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              type="email"
              label="E-mail"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="example@email.com"
            />

            <Input
              type="password"
              label="Пароль"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Минимум 8 символов"
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Я регистрируюсь как
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setRole('candidate')}
                  className={`px-4 py-3 rounded-md border-2 font-medium transition-colors ${
                    role === 'candidate'
                      ? 'border-primary-accent bg-primary-lighter text-primary-accent'
                      : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'
                  }`}
                >
                  Кандидат
                </button>
                <button
                  type="button"
                  onClick={() => setRole('employer')}
                  className={`px-4 py-3 rounded-md border-2 font-medium transition-colors ${
                    role === 'employer'
                      ? 'border-primary-accent bg-primary-lighter text-primary-accent'
                      : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'
                  }`}
                >
                  Работодатель
                </button>
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              className="w-full"
              loading={registerMutation.isPending}
            >
              Зарегистрироваться
            </Button>

            {registerMutation.isError && (
              <p className="text-sm text-red-600 text-center">
                Ошибка регистрации. Проверьте данные и повторите попытку.
              </p>
            )}
          </form>

          <p className="mt-6 text-center text-sm text-gray-600">
            Уже есть аккаунт?{' '}
            <a href="/auth/login" className="text-primary-accent hover:text-primary-light font-medium">
              Войти
            </a>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
