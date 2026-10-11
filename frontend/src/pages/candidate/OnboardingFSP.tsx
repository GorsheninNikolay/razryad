import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, CardContent, Input } from '@/design/components'
import { useLinkFSP } from '@/api'
import uiCopy from '../../../../content/ui-copy.ru.json'

const copy = uiCopy.screens['candidate.onboarding.fsp']

export default function OnboardingFSP() {
  const navigate = useNavigate()
  const linkFSP = useLinkFSP()
  const [fspId, setFspId] = useState('')
  const [connected, setConnected] = useState(false)

  const handleConnect = async () => {
    if (!fspId) return
    
    linkFSP.mutate(
      { fsp_id: fspId },
      {
        onSuccess: () => {
          setConnected(true)
          setTimeout(() => {
            navigate('/candidate/assessment/start')
          }, 1500)
        },
      }
    )
  }

  const handleSkip = () => {
    // Equal-priority skip button as required
    navigate('/candidate/assessment/start')
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4">
        <Card>
          <CardContent>
            <div className="mb-6">
              <h1 className="text-2xl font-bold text-gray-900 mb-2">{copy.title}</h1>
              <p className="text-gray-600">{copy.subtitle}</p>
            </div>

            {!connected ? (
              <>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                  <p className="text-sm text-blue-800">
                    Достижения ФСП дают дополнительное подтверждение грейда, но профиль работает 
                    и без них. Вы можете привязать ФСП ID позже в настройках.
                  </p>
                </div>

                <div className="space-y-6 mb-6">
                  <Input
                    label="ФСП ID"
                    value={fspId}
                    onChange={(e) => setFspId(e.target.value)}
                    placeholder="FSP-12345"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Button
                    variant="ghost"
                    size="lg"
                    onClick={handleSkip}
                    className="w-full"
                  >
                    {copy.skip}
                  </Button>
                  <Button
                    variant="primary"
                    size="lg"
                    onClick={handleConnect}
                    loading={linkFSP.isPending}
                    disabled={!fspId}
                    className="w-full"
                  >
                    {copy.connect}
                  </Button>
                </div>

                <p className="mt-4 text-xs text-center text-gray-500">
                  {copy.empty}
                </p>
              </>
            ) : (
              <div className="text-center py-8">
                <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
                  <svg className="w-8 h-8 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">✓ {copy.success}</h3>
                <p className="text-gray-600">Переходим к тесту...</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
