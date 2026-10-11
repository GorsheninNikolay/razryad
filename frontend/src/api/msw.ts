import { setupWorker } from 'msw/browser'
import { handlers } from './mocks'

export const worker = setupWorker(...handlers)

export async function startMockServiceWorker() {
  if (import.meta.env.VITE_USE_MOCKS === 'true') {
    await worker.start({
      onUnhandledRequest: 'bypass',
    })
    console.log('[MSW] Mock Service Worker started')
  }
}
