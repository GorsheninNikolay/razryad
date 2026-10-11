import { Routes, Route } from 'react-router-dom'
import ProtectedRoute from './app/ProtectedRoute'
import Landing from './pages/Landing'
import { Register, Login, VerifyEmail } from './pages/auth'
import * as CandidatePages from './pages/candidate'
import * as EmployerPages from './pages/employer'

function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<Landing />} />
      <Route path="/auth/register" element={<Register />} />
      <Route path="/auth/login" element={<Login />} />
      <Route path="/auth/verify-email" element={<VerifyEmail />} />

      {/* Candidate onboarding */}
      <Route
        path="/candidate/onboarding/survey"
        element={
          <ProtectedRoute>
            <CandidatePages.OnboardingSurvey />
          </ProtectedRoute>
        }
      />
      <Route
        path="/candidate/onboarding/grade"
        element={
          <ProtectedRoute>
            <CandidatePages.OnboardingGrade />
          </ProtectedRoute>
        }
      />
      <Route
        path="/candidate/onboarding/profile"
        element={
          <ProtectedRoute>
            <CandidatePages.OnboardingProfile />
          </ProtectedRoute>
        }
      />
      <Route
        path="/candidate/onboarding/fsp"
        element={
          <ProtectedRoute>
            <CandidatePages.OnboardingFSP />
          </ProtectedRoute>
        }
      />

      {/* Assessment */}
      <Route
        path="/candidate/assessment/start"
        element={
          <ProtectedRoute>
            <CandidatePages.AssessmentStart />
          </ProtectedRoute>
        }
      />
      <Route
        path="/candidate/assessment/session"
        element={
          <ProtectedRoute>
            <CandidatePages.AssessmentSession />
          </ProtectedRoute>
        }
      />
      <Route
        path="/candidate/assessment/result"
        element={
          <ProtectedRoute>
            <CandidatePages.AssessmentResult />
          </ProtectedRoute>
        }
      />

      {/* Candidate dashboard */}
      <Route
        path="/candidate/dashboard"
        element={
          <ProtectedRoute>
            <CandidatePages.Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/candidate/invitations"
        element={
          <ProtectedRoute>
            <CandidatePages.Invitations />
          </ProtectedRoute>
        }
      />
      {/* Меню ведёт на «Профиль», но отдельной страницы профиля нет —
          редактирование профиля живёт в онбординге. Подключаем её, иначе
          пункт меню вёл на 404. */}
      <Route
        path="/candidate/profile"
        element={
          <ProtectedRoute>
            <CandidatePages.OnboardingProfile />
          </ProtectedRoute>
        }
      />

      {/* Employer routes.
          Раньше здесь был только /employer/dashboard с пометкой «stub»:
          восемь страниц кабинета работодателя существовали как компоненты,
          но не были подключены — весь кабинет был недоступен по адресам,
          а пункты меню и переходы между экранами вели на 404. */}
      <Route
        path="/employer/dashboard"
        element={
          <ProtectedRoute>
            <EmployerPages.Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/employer/company"
        element={
          <ProtectedRoute>
            <EmployerPages.Company />
          </ProtectedRoute>
        }
      />
      <Route
        path="/employer/need"
        element={
          <ProtectedRoute>
            <EmployerPages.Need />
          </ProtectedRoute>
        }
      />
      <Route
        path="/employer/categories"
        element={
          <ProtectedRoute>
            <EmployerPages.Categories />
          </ProtectedRoute>
        }
      />
      <Route
        path="/employer/shortlist"
        element={
          <ProtectedRoute>
            <EmployerPages.Shortlist />
          </ProtectedRoute>
        }
      />
      <Route
        path="/employer/search"
        element={
          <ProtectedRoute>
            <EmployerPages.Search />
          </ProtectedRoute>
        }
      />
      <Route
        path="/employer/invite/:candidateId"
        element={
          <ProtectedRoute>
            <EmployerPages.Invite />
          </ProtectedRoute>
        }
      />
      <Route
        path="/employer/invitations"
        element={
          <ProtectedRoute>
            <EmployerPages.Invitations />
          </ProtectedRoute>
        }
      />
      <Route
        path="/employer/vacancies"
        element={
          <ProtectedRoute>
            <EmployerPages.Vacancies />
          </ProtectedRoute>
        }
      />

      {/* 404 */}
      <Route path="*" element={<div className="p-8 text-center text-gray-600">404 - Страница не найдена</div>} />
    </Routes>
  )
}

export default App
