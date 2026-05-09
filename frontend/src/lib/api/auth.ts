import { apiRequest, setAuthToken } from './client'
import type { LoginResponse, Person, User } from './types'

export async function register(data: {
  email: string
  password: string
  given_names: string
  surname: string
  display_name?: string
}): Promise<{ user: User; person: Person; detail: string }> {
  return apiRequest('/api/auth/register/', {
    method: 'POST',
    body: JSON.stringify(data),
    skipAuth: true,
  })
}

export async function login(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const result = await apiRequest<LoginResponse>('/api/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
    skipAuth: true,
  })
  setAuthToken(result.token)
  return result
}

export async function logout(): Promise<void> {
  try {
    await apiRequest('/api/auth/logout/', { method: 'POST' })
  } finally {
    setAuthToken(null)
  }
}

export async function verifyEmail(
  token: string,
): Promise<{ user: User; detail: string }> {
  return apiRequest('/api/auth/verify-email/', {
    method: 'POST',
    body: JSON.stringify({ token }),
    skipAuth: true,
  })
}

export async function resendVerification(): Promise<{ detail: string }> {
  return apiRequest('/api/auth/resend-verification/', { method: 'POST' })
}

export async function requestPasswordReset(
  email: string,
): Promise<{ detail: string }> {
  return apiRequest('/api/auth/password-reset/request/', {
    method: 'POST',
    body: JSON.stringify({ email }),
    skipAuth: true,
  })
}

export async function confirmPasswordReset(
  token: string,
  new_password: string,
): Promise<{ detail: string }> {
  return apiRequest('/api/auth/password-reset/confirm/', {
    method: 'POST',
    body: JSON.stringify({ token, new_password }),
    skipAuth: true,
  })
}
