/**
 * Auth API Client for Cachibot
 */

import type {
  AuthModeResponse,
  ChangePasswordRequest,
  CreateUserRequest,
  ExchangeTokenRequest,
  LoginRequest,
  LoginResponse,
  RefreshRequest,
  RefreshResponse,
  SetupRequest,
  SetupStatusResponse,
  UpdateUserRequest,
  User,
  UserListResponse,
} from '../types'
import { useAuthStore } from '../stores/auth'
import { hashPassword } from '../lib/utils'

const API_BASE = '/api'

class AuthApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message)
    this.name = 'AuthApiError'
  }
}

async function authRequest<T>(
  endpoint: string,
  options: RequestInit = {},
  includeAuth = false
): Promise<T> {
  const url = `${API_BASE}${endpoint}`

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  // Add Authorization header if requested
  if (includeAuth) {
    const { accessToken } = useAuthStore.getState()
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new AuthApiError(
      data.detail || `Request failed: ${response.statusText}`,
      response.status,
      data
    )
  }

  return response.json()
}

// ===== Public endpoints (no auth required) =====

export async function getAuthMode(): Promise<AuthModeResponse> {
  return authRequest('/auth/mode')
}

export async function exchangeToken(data: ExchangeTokenRequest): Promise<LoginResponse> {
  return authRequest('/auth/exchange', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function checkSetupRequired(): Promise<SetupStatusResponse> {
  return authRequest('/auth/setup-required')
}

export async function setupAdmin(data: SetupRequest): Promise<LoginResponse> {
  return authRequest('/auth/setup', {
    method: 'POST',
    body: JSON.stringify({
      ...data,
      password: await hashPassword(data.password),
    }),
  })
}

export async function login(data: LoginRequest): Promise<LoginResponse> {
  return authRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({
      ...data,
      password: await hashPassword(data.password),
    }),
  })
}

export async function refreshToken(data: RefreshRequest): Promise<RefreshResponse> {
  return authRequest('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ===== Protected endpoints (auth required) =====

export async function getCurrentUser(): Promise<User> {
  return authRequest('/auth/me', {}, true)
}

export async function changePassword(data: ChangePasswordRequest): Promise<{ status: string }> {
  return authRequest(
    '/auth/change-password',
    {
      method: 'POST',
      body: JSON.stringify({
        current_password: await hashPassword(data.current_password),
        new_password: await hashPassword(data.new_password),
      }),
    },
    true
  )
}

// ===== Admin-only endpoints =====

export async function listUsers(
  limit = 100,
  offset = 0
): Promise<UserListResponse> {
  return authRequest(`/auth/users?limit=${limit}&offset=${offset}`, {}, true)
}

export async function createUser(data: CreateUserRequest): Promise<User> {
  return authRequest(
    '/auth/users',
    {
      method: 'POST',
      body: JSON.stringify({
        ...data,
        password: await hashPassword(data.password),
      }),
    },
    true
  )
}

export async function updateUser(
  userId: string,
  data: UpdateUserRequest
): Promise<User> {
  return authRequest(
    `/auth/users/${userId}`,
    {
      method: 'PUT',
      body: JSON.stringify(data),
    },
    true
  )
}

export async function deactivateUser(userId: string): Promise<{ status: string }> {
  return authRequest(
    `/auth/users/${userId}`,
    {
      method: 'DELETE',
    },
    true
  )
}

// ===== Token refresh logic =====

let refreshPromise: Promise<RefreshResponse> | null = null

export async function tryRefreshToken(): Promise<string | null> {
  const { refreshToken: token, setAccessToken, logout } = useAuthStore.getState()

  if (!token) {
    return null
  }

  // Deduplicate concurrent refresh requests
  if (refreshPromise) {
    try {
      const result = await refreshPromise
      return result.access_token
    } catch {
      return null
    }
  }

  try {
    refreshPromise = refreshToken({ refresh_token: token })
    const result = await refreshPromise
    setAccessToken(result.access_token)
    return result.access_token
  } catch {
    logout()
    return null
  } finally {
    refreshPromise = null
  }
}

export { AuthApiError }
