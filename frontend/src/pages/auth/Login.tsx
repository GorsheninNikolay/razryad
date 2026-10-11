import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLogin } from '@/api'
import { Button, Input, Card, CardContent } from '@/design/components'

export default function Login() {
  const navigate = useNavigate()
  const loginMutation = useLogin()
  
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    loginMutation.mutate(
      { email, password },
      {
        onSuccess: (data) => {
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)
          
          if (data.user.role === 'candidate') {
            navigate('/candidate/dashboard')
          } else {
            navigate('/employer/dashboard')
          }
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
            <h2 className="text-xl font-semibold text-gray-900">Вход</h2>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              type="email"
              label="E-mail"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />

            <Input
              type="password"
              label="Пароль"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            <Button
              type="submit"
              variant="primary"
              size="lg"
              className="w-full"
              loading={loginMutation.isPending}
            >
              Войти
            </Button>

            {loginMutation.isError && (
              <p className="text-sm text-red-600 text-center">
                Неверный email или пароль
              </p>
            )}
          </form>

          <p className="mt-6 text-center text-sm text-gray-600">
            Нет аккаунта?{' '}
            <a href="/auth/register" className="text-primary-accent hover:text-primary-light font-medium">
              Зарегистрироваться
            </a>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
