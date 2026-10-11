import type { ApiError } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export class ApiClient {
  private getAuthToken(): string | null {
    return localStorage.getItem('access_token')
  }

  private setAuthToken(token: string): void {
    localStorage.setItem('access_token', token)
  }

  private clearAuthToken(): void {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  private async refreshToken(): Promise<boolean> {
    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) return false

    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })

      if (response.ok) {
        const data = await response.json()
        this.setAuthToken(data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
        return true
      }
      
      this.clearAuthToken()
      return false
    } catch {
      return false
    }
  }

  async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`
    const token = this.getAuthToken()

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }

    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    let response = await fetch(url, { ...options, headers })

    // Handle 401 with token refresh
    if (response.status === 401 && token) {
      const refreshed = await this.refreshToken()
      if (refreshed) {
        const newToken = this.getAuthToken()
        if (newToken) {
          headers['Authorization'] = `Bearer ${newToken}`
          response = await fetch(url, { ...options, headers })
        }
      } else {
        // Refresh failed, redirect to login
        window.location.href = '/auth/login'
        throw new Error('Authentication required')
      }
    }

    // Handle problem+json errors
    if (!response.ok) {
      const contentType = response.headers.get('content-type')
      if (contentType?.includes('application/problem+json')) {
        const error: ApiError = await response.json()
        throw error
      }
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    return response.json()
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' })
  }

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async patch<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }

  setTokens(accessToken: string, refreshToken: string): void {
    this.setAuthToken(accessToken)
    localStorage.setItem('refresh_token', refreshToken)
  }

  clearTokens(): void {
    this.clearAuthToken()
  }

  isAuthenticated(): boolean {
    return !!this.getAuthToken()
  }
}

export const apiClient = new ApiClient()
