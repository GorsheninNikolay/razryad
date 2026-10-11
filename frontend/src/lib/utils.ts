import { type ClassValue, clsx } from 'clsx'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export function formatSalary(from?: number | null, to?: number | null): string {
  // Поля вилки в API необязательные: приглашение может быть без неё.
  // Раньше сигнатура требовала оба числа, и отсутствие значения давало
  // в интерфейсе «undefined – undefined ₽».
  const hasFrom = from !== null && from !== undefined
  const hasTo = to !== null && to !== undefined
  if (!hasFrom && !hasTo) return 'вилка не указана'
  if (!hasFrom) return `до ${to!.toLocaleString('ru-RU')} ₽`
  if (!hasTo) return `от ${from!.toLocaleString('ru-RU')} ₽`
  return `${from!.toLocaleString('ru-RU')} – ${to!.toLocaleString('ru-RU')} ₽`
}

export function getGradeLabel(grade: string): string {
  const labels: Record<string, string> = {
    intern: 'Intern',
    junior: 'Junior',
    middle: 'Middle',
    senior: 'Senior',
    lead: 'Lead',
  }
  return labels[grade.toLowerCase()] || grade
}

export function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    sent: 'Отправлено',
    viewed: 'Просмотрено',
    accepted: 'Принято',
    declined: 'Отклонено',
    expired: 'Истекло',
  }
  return labels[status] || status
}
