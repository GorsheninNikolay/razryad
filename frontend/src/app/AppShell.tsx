import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { apiClient } from '@/api'

interface AppShellProps {
  children: ReactNode
  role?: 'candidate' | 'employer'
}

export default function AppShell({ children, role }: AppShellProps) {
  const location = useLocation()

  const handleLogout = () => {
    apiClient.clearTokens()
    window.location.href = '/auth/login'
  }

  const candidateNav = [
    { path: '/candidate/dashboard', label: 'Кабинет' },
    { path: '/candidate/invitations', label: 'Приглашения' },
    { path: '/candidate/profile', label: 'Профиль' },
  ]

  const employerNav = [
    { path: '/employer/dashboard', label: 'Кабинет' },
    { path: '/employer/need', label: 'Новая потребность' },
    { path: '/employer/search', label: 'Поиск кандидатов' },
    { path: '/employer/shortlist', label: 'Подборка' },
    { path: '/employer/invitations', label: 'Отправленные приглашения' },
    { path: '/employer/vacancies', label: 'Вакансии' },
  ]

  const navItems = role === 'candidate' ? candidateNav : role === 'employer' ? employerNav : []

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link to="/" className="text-2xl font-bold text-primary-accent">
              РАЗРЯД
            </Link>
            
            {role && (
              <nav className="hidden md:flex space-x-8">
                {navItems.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                      location.pathname === item.path
                        ? 'border-primary-accent text-primary-accent'
                        : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
            )}

            {apiClient.isAuthenticated() && (
              <button
                onClick={handleLogout}
                className="text-sm text-gray-700 hover:text-gray-900"
              >
                Выйти
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}
