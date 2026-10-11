import AppShell from '@/app/AppShell'
import { useIncomingInvitations, useAcceptInvitation, useDeclineInvitation } from '@/api'
import { asList } from '@/api/normalize'
import type { Invitation } from '@/api/types'
import { Button, Card, CardContent, Badge, Skeleton } from '@/design/components'
import { formatSalary, getStatusLabel } from '@/lib/utils'
import { useQueryClient } from '@tanstack/react-query'

export default function CandidateInvitations() {
  const { data, isLoading } = useIncomingInvitations()
  // /invitations/incoming возвращает массив, а не {data: [...]} — см. normalize.ts
  const invitations = asList<Invitation>(data)
  const acceptMutation = useAcceptInvitation()
  const declineMutation = useDeclineInvitation()
  const queryClient = useQueryClient()

  const handleAccept = (invitationId: string) => {
    if (!confirm('Принять приглашение? Ваши контакты будут раскрыты работодателю.')) return
    
    acceptMutation.mutate(invitationId, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['incomingInvitations'] })
      },
    })
  }

  const handleDecline = (invitationId: string) => {
    if (!confirm('Отклонить приглашение?')) return
    
    declineMutation.mutate(invitationId, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['incomingInvitations'] })
      },
    })
  }

  return (
    <AppShell role="candidate">
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-900">Входящие приглашения</h1>

        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <Card key={i}>
                <CardContent>
                  <Skeleton className="h-24 w-full" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : !invitations.length ? (
          <Card>
            <CardContent>
              <p className="text-gray-500 text-center py-8">Новых приглашений нет</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {invitations.map((invitation) => (
              <Card key={invitation.id}>
                <CardContent>
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="text-lg font-semibold">{invitation.company_name}</h3>
                        <Badge variant="status">{getStatusLabel(invitation.status)}</Badge>
                      </div>
                      <p className="text-gray-700 mb-3">{invitation.offer_description}</p>
                      <div className="space-y-1 text-sm">
                        <p className="text-gray-600">
                          <span className="font-medium">Зарплата:</span>{' '}
                          {/* API отдаёт salary_min / salary_max. Прежние имена
                              salary_from / salary_to давали undefined, и вместо
                              вилки кандидат видел «undefined – undefined ₽». */}
                          {formatSalary(invitation.salary_min, invitation.salary_max)}
                        </p>
                        {invitation.status === 'accepted' && invitation.contact_method && (
                          <div className="bg-green-50 border border-green-200 rounded-lg p-3 mt-3">
                            <p className="text-sm font-medium text-green-900 mb-1">
                              ✓ Контакты раскрыты
                            </p>
                            <p className="text-sm text-green-800">
                              <span className="font-medium">Способ связи:</span> {invitation.contact_method}
                            </p>
                            {invitation.contact_person && (
                              <p className="text-sm text-green-800">
                                <span className="font-medium">Контактное лицо:</span> {invitation.contact_person}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                    {invitation.status === 'sent' && (
                      <div className="flex gap-2 ml-4">
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => handleAccept(invitation.id)}
                          loading={acceptMutation.isPending}
                        >
                          Принять
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDecline(invitation.id)}
                          loading={declineMutation.isPending}
                        >
                          Отклонить
                        </Button>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-gray-500">
                    Получено: {new Date(invitation.created_at).toLocaleString('ru-RU')}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}
