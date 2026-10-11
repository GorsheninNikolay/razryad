/**
 * Приведение ответов-списков к массиву.
 *
 * Бэкенд отдаёт коллекции в двух формах: простым массивом (`/invitations/incoming`,
 * `/invitations/sent`, `/search/`) и объектом с полями (`/shortlists/{id}` →
 * `{items, total_filtered}`). Компоненты, написанные в расчёте на одну из форм,
 * падают на другой — причём не при сборке, а в рантайме, белым экраном:
 *
 *   invitations?.data.filter(...)   // invitations — массив, .data === undefined
 *   TypeError: Cannot read properties of undefined (reading 'filter')
 *
 * Поэтому любой ответ-коллекцию прогоняем через `asList` и не полагаемся на то,
 * что сервер выберет «удобную» форму.
 */
export function asList<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) return payload as T[]

  if (payload && typeof payload === 'object') {
    const candidate = payload as { items?: unknown; data?: unknown; results?: unknown }
    for (const key of ['items', 'data', 'results'] as const) {
      const value = candidate[key]
      if (Array.isArray(value)) return value as T[]
    }
  }

  return []
}
