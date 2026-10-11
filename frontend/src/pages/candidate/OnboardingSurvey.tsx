import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, CardContent, Select } from '@/design/components'
import { useCandidateProfile, useUpdateCandidateProfile } from '@/api'
import AppShell from '@/app/AppShell'
import uiCopy from '../../../../content/ui-copy.ru.json'
import taxonomy from '../../../../content/taxonomy.json'

const copy = uiCopy.screens['candidate.onboarding.survey']
const common = uiCopy.common

type Step = 'industry' | 'specialization' | 'subspecialization'

export default function OnboardingSurvey() {
  const navigate = useNavigate()
  const updateProfile = useUpdateCandidateProfile()
  const profile = useCandidateProfile()
  const [saveError, setSaveError] = useState('')
  const [currentStep, setCurrentStep] = useState<Step>('industry')
  const [industry, setIndustry] = useState('')
  const [specialization, setSpecialization] = useState('')
  const [subspecialization, setSubspecialization] = useState('')

  useEffect(() => { if (profile.data) { const p = profile.data; setIndustry(p.industry || ''); setSpecialization(p.specialization_id || ''); setSubspecialization(p.subspecialization_id || '') } }, [profile.data])

  const industries = taxonomy.industries
  const specializations = taxonomy.specializations.filter(s => !industry || s.industry_id === industry)
  const subspecializations = specialization
    ? taxonomy.specializations.find(s => s.id === specialization)?.subspecializations || []
    : []

  const handleNext = () => {
    if (currentStep === 'industry' && industry) {
      setCurrentStep('specialization')
    } else if (currentStep === 'specialization' && specialization) {
      if (subspecializations.length > 0) {
        setCurrentStep('subspecialization')
      } else {
        handleComplete()
      }
    } else if (currentStep === 'subspecialization') {
      handleComplete()
    }
  }

  const handleComplete = async () => {
    setSaveError('')
    // Save survey data to backend
    setSaveError('')
    updateProfile.mutate(
      {
        specialization_id: specialization,
        subspecialization_id: subspecialization || undefined,
      },
      {
        onSuccess: () => { navigate('/candidate/onboarding/grade') },
        onError: (error) => { setSaveError(`Не удалось сохранить выбор: ${error.message}`) },
      }
    )
  }

  const canProceed = () => {
    if (currentStep === 'industry') return !!industry
    if (currentStep === 'specialization') return !!specialization
    if (currentStep === 'subspecialization') return !!subspecialization
    return false
  }

  const progress = currentStep === 'industry' ? 33 : currentStep === 'specialization' ? 67 : 100

  return (
    <AppShell role="candidate"><div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4">
        {/* Progress bar */}
        <div className="mb-8">
          <div className="flex justify-between text-sm text-gray-600 mb-2">
            <span>{copy.steps[0]}</span>
            <span>{copy.steps[1]}</span>
            <span>{copy.steps[2]}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-primary-accent h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <Card>
          <CardContent>
            <div className="mb-6"><p className="text-sm text-primary-accent font-semibold">ШАГ {currentStep === 'industry' ? '1' : currentStep === 'specialization' ? '2' : '3'} ИЗ 3</p>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">{copy.title}</h1>
              <p className="text-gray-600">{copy.subtitle}</p>
            </div>

            <div className="space-y-6">
              {currentStep === 'industry' && (
                <Select
                  label={copy.industry}
                  value={industry}
                  onChange={(e) => {
                    setIndustry(e.target.value)
                    setSpecialization('')
                    setSubspecialization('')
                  }}
                  options={[
                    { value: '', label: 'Выберите...' },
                    ...industries.map(ind => ({ value: ind.id, label: ind.name }))
                  ]}
                />
              )}

              {currentStep === 'specialization' && (
                <Select
                  label={copy.specialization}
                  value={specialization}
                  onChange={(e) => {
                    setSpecialization(e.target.value)
                    setSubspecialization('')
                  }}
                  options={[
                    { value: '', label: 'Выберите...' },
                    ...specializations.map(spec => ({ value: spec.id, label: spec.name }))
                  ]}
                />
              )}

              {currentStep === 'subspecialization' && subspecializations.length > 0 && (
                <Select
                  label={copy.subspecialization}
                  value={subspecialization}
                  onChange={(e) => setSubspecialization(e.target.value)}
                  options={[
                    { value: '', label: 'Выберите...' },
                    ...subspecializations.map(sub => ({ value: sub.id, label: sub.name }))
                  ]}
                />
              )}

              {saveError && <p role="alert" className="text-red-600">{saveError}</p>}

              {currentStep === 'subspecialization' && subspecializations.length === 0 && (
                <div className="text-center py-4 text-gray-500">
                  {copy.empty}
                </div>
              )}
            </div>

            {saveError && <p role="alert" className="mt-4 text-sm text-red-600">{saveError}</p>}
            <div className="mt-8 flex gap-3">
              {currentStep !== 'industry' && (
                <Button
                  variant="ghost"
                  onClick={() => {
                    if (currentStep === 'subspecialization') setCurrentStep('specialization')
                    else if (currentStep === 'specialization') setCurrentStep('industry')
                  }}
                >
                  {common.back}
                </Button>
              )}
              <Button
                variant="primary"
                className="flex-1"
                onClick={handleNext}
                disabled={!canProceed()}
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
