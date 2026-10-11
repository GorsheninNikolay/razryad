import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, CardContent } from '@/design/components'
import { useCandidateProfile, useUpdateCandidateProfile } from '@/api'
import AppShell from '@/app/AppShell'
import uiCopy from '../../../../content/ui-copy.ru.json'

const copy = uiCopy.screens['candidate.onboarding.grade']
const common = uiCopy.common

const grades = [
  { value: 'intern', label: 'Intern', description: 'Стажёр, начинаю путь' },
  { value: 'junior', label: 'Junior', description: '0–2 года опыта' },
  { value: 'middle', label: 'Middle', description: '2–4 года опыта' },
  { value: 'senior', label: 'Senior', description: '4+ лет опыта' },
  { value: 'lead', label: 'Lead', description: 'Ведущий, наставник команды' },
]

export default function OnboardingGrade() {
  const navigate = useNavigate()
  const updateProfile = useUpdateCandidateProfile()
  const profile = useCandidateProfile()
  useEffect(() => { if (profile.data?.claimed_grade) setSelectedGrade(profile.data.claimed_grade) }, [profile.data])
  const [selectedGrade, setSelectedGrade] = useState('')

  const handleSubmit = async () => {
    if (!selectedGrade) return
    
    // Save claimed grade to backend
    updateProfile.mutate(
      { claimed_grade: selectedGrade },
      {
        onSuccess: () => {
          navigate('/candidate/onboarding/profile')
        },
      }
    )
  }

  return (
    <AppShell role="candidate"><div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4">
        <Card>
          <CardContent>
            <div className="mb-6"><p className="text-sm text-primary-accent font-semibold">ШАГ 2 ИЗ 3</p>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">{copy.title}</h1>
              <p className="text-gray-600">{copy.subtitle}</p>
            </div>

            <div className="space-y-3 mb-6">
              {grades.map((grade) => (
                <button
                  key={grade.value}
                  onClick={() => setSelectedGrade(grade.value)}
                  className={`w-full p-4 rounded-lg border-2 text-left transition-all ${
                    selectedGrade === grade.value
                      ? 'border-primary-accent bg-primary-lighter'
                      : 'border-gray-200 bg-white hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-lg text-gray-900">{grade.label}</div>
                      <div className="text-sm text-gray-600">{grade.description}</div>
                    </div>
                    {selectedGrade === grade.value && (
                      <div className="text-primary-accent">
                        <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
              <p className="text-sm text-blue-800">{copy.hint}</p>
            </div>

            <div className="flex gap-3">
              <Button
                variant="ghost"
                onClick={() => navigate('/candidate/onboarding/survey')}
              >
                {common.back}
              </Button>
              <Button
                variant="primary"
                className="flex-1"
                onClick={handleSubmit}
                disabled={!selectedGrade}
              >
                {copy.cta}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div></AppShell>
  )
}
