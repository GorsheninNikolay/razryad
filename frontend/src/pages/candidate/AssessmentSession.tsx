import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Button, Card, CardContent } from '@/design/components'
import { useAssessmentSession, useNextAssessmentItem, useSubmitAnswer, useCompleteAssessment } from '@/api'
import { useQueryClient } from '@tanstack/react-query'
import uiCopy from '../../../../content/ui-copy.ru.json'

const copy = uiCopy.screens['candidate.assessment']

export default function AssessmentSession() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const sessionId = searchParams.get('sessionId')
  
  const { data: session } = useAssessmentSession(sessionId)
  const { data: currentItem, refetch: refetchItem, error: itemError } = useNextAssessmentItem(sessionId)
  const submitAnswer = useSubmitAnswer()
  const completeAssessment = useCompleteAssessment()
  
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null)
  const [textAnswer, setTextAnswer] = useState('')
  const [timeRemaining, setTimeRemaining] = useState(2700) // 45 minutes

  // Handle 404 from next-item (session completed)
  useEffect(() => {
    if (itemError && (itemError as any)?.status === 404) {
      // 404 means no more items - session is completed
      navigate(`/candidate/assessment/result?sessionId=${sessionId}`)
    }
  }, [itemError, sessionId, navigate])

  // Timer countdown
  useEffect(() => {
    if (!session) return
    
    const timer = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          handleTimeout()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [session])

  const handleTimeout = () => {
    if (sessionId) {
      completeAssessment.mutate(sessionId, {
        onSuccess: () => {
          navigate(`/candidate/assessment/result?sessionId=${sessionId}`)
        },
      })
    }
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  // Detect item type from content structure
  const getItemType = () => {
    if (!currentItem?.content) return 'text'
    if (currentItem.content.options) return 'mcq'
    if (currentItem.content.code) return 'code'
    return 'text'
  }

  const handleSubmitAnswer = async () => {
    if (!currentItem || !sessionId) return

    const itemType = getItemType()
    let answer: number | string

    // Determine answer based on item type
    if (itemType === 'mcq') {
      if (selectedAnswer === null) return
      answer = selectedAnswer
    } else {
      if (textAnswer.trim() === '') return
      answer = textAnswer
    }

    submitAnswer.mutate(
      {
        sessionId,
        itemId: currentItem.item_id,
        answer,
      },
      {
        onSuccess: (response) => {
          // Check session_status from the response
          if (response.session_status === 'completed') {
            // Session completed - navigate to results
            navigate(`/candidate/assessment/result?sessionId=${sessionId}`)
          } else if (response.session_status === 'expired') {
            // Session expired - show error and navigate to start
            alert('Время сессии истекло')
            navigate('/candidate/assessment/start')
          } else {
            // Session active - fetch next item
            setSelectedAnswer(null)
            setTextAnswer('')
            queryClient.invalidateQueries({ queryKey: ['assessmentSession', sessionId] })
            refetchItem()
          }
        },
        onError: (error: any) => {
          // Handle errors gracefully
          if (error?.status === 404) {
            // 404 likely means session is completed - navigate to results
            navigate(`/candidate/assessment/result?sessionId=${sessionId}`)
          } else {
            alert('Ошибка при отправке ответа. Попробуйте ещё раз.')
          }
        },
      }
    )
  }

  if (!session || !currentItem || !currentItem.content) {
    return <div className="min-h-screen flex items-center justify-center">
      <p>Загрузка задания...</p>
    </div>
  }

  const itemType = getItemType()
  const canSubmit = itemType === 'mcq' ? selectedAnswer !== null : textAnswer.trim().length > 0

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        {/* Header with timer and progress */}
        <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">
                Задание {currentItem.sequence ?? '—'}
              </p>
              {session.current_item && session.total_items && (
                <div className="w-48 bg-gray-200 rounded-full h-2 mt-2">
                  <div
                    className="bg-primary-accent h-2 rounded-full transition-all"
                    style={{ width: `${(session.current_item / session.total_items) * 100}%` }}
                  />
                </div>
              )}
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-600">Время</p>
              <p className={`text-2xl font-bold ${timeRemaining < 300 ? 'text-red-600' : 'text-gray-900'}`}>
                {formatTime(timeRemaining)}
              </p>
            </div>
          </div>
        </div>

        {/* Question Card */}
        <Card>
          <CardContent>
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                {currentItem.content.stem}
              </h2>
            </div>

            {/* Code Display (read-only) */}
            {currentItem.content.code && (
              <div className="mb-6">
                <div className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto">
                  <pre className="font-mono text-sm whitespace-pre-wrap">{currentItem.content.code}</pre>
                </div>
              </div>
            )}

            {/* Multiple Choice (options present) */}
            {itemType === 'mcq' && currentItem.content.options && (
              <div className="space-y-3 mb-6">
                {currentItem.content.options.map((option, index) => (
                  <button
                    key={index}
                    onClick={() => setSelectedAnswer(index)}
                    className={`w-full p-4 rounded-lg border-2 text-left transition-all ${
                      selectedAnswer === index
                        ? 'border-primary-accent bg-primary-lighter'
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-5 h-5 rounded-full border-2 flex-shrink-0 ${
                        selectedAnswer === index
                          ? 'border-primary-accent bg-primary-accent'
                          : 'border-gray-300'
                      }`}>
                        {selectedAnswer === index && (
                          <div className="w-full h-full flex items-center justify-center">
                            <div className="w-2 h-2 bg-white rounded-full" />
                          </div>
                        )}
                      </div>
                      <span className="text-gray-900">{option}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {/* Text/Essay Answer (no options, no code OR code with text answer expected) */}
            {(itemType === 'text' || itemType === 'code') && (
              <div className="mb-6">
                <textarea
                  value={textAnswer}
                  onChange={(e) => setTextAnswer(e.target.value)}
                  className={`w-full h-40 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-accent ${
                    itemType === 'code' ? 'font-mono text-sm' : ''
                  }`}
                  placeholder={itemType === 'code' ? 'Что выведет код?' : 'Ваш ответ...'}
                />
              </div>
            )}

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-6">
              <p className="text-sm text-yellow-800">{copy.warning}</p>
            </div>

            <Button
              variant="primary"
              size="lg"
              className="w-full"
              onClick={handleSubmitAnswer}
              disabled={!canSubmit}
              loading={submitAnswer.isPending || completeAssessment.isPending}
            >
              Ответить
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
