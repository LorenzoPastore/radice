const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const TOKEN_KEY = 'radice_auth_token'

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(TOKEN_KEY)
}

export function setAuthToken(token: string | null): void {
  if (typeof window === 'undefined') return
  if (token === null) window.localStorage.removeItem(TOKEN_KEY)
  else window.localStorage.setItem(TOKEN_KEY, token)
}

export class ApiError extends Error {
  status: number
  detail?: string
  fieldErrors?: Record<string, string[]>

  constructor(
    status: number,
    detail?: string,
    fieldErrors?: Record<string, string[]>,
  ) {
    super(detail ?? `API error ${status}`)
    this.status = status
    this.detail = detail
    this.fieldErrors = fieldErrors
  }
}

export async function apiRequest<T>(
  path: string,
  options?: RequestInit & { skipAuth?: boolean },
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
  }

  if (!options?.skipAuth) {
    const token = getAuthToken()
    if (token) headers.Authorization = `Token ${token}`
  }

  const { skipAuth: _skipAuth, ...fetchOptions } = options ?? {}

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...fetchOptions,
    headers,
  })

  if (response.status === 204) return undefined as T

  const text = await response.text()
  let body: unknown = {}
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = { detail: text }
    }
  }

  if (!response.ok) {
    const bodyObj = (body ?? {}) as Record<string, unknown>
    const detail =
      typeof bodyObj.detail === 'string' ? bodyObj.detail : undefined
    const fieldErrors =
      !detail && typeof body === 'object' && body !== null
        ? (body as Record<string, string[]>)
        : undefined
    throw new ApiError(response.status, detail, fieldErrors)
  }

  return body as T
}
