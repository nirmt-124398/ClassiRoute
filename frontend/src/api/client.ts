// In dev, Vite proxy handles /v1, /auth, /keys, /analytics, /users, /health
// In production (Vercel), set VITE_API_URL to your Render backend URL
export const BASE_URL = (import.meta as any).env?.VITE_API_URL ?? ""

interface RequestOptions {
  method?: string
  body?: unknown
  headers?: Record<string, string>
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail)
  }
}

function getToken(): string | null {
  try {
    const stored = localStorage.getItem("auth")
    if (!stored) return null
    
    const parsed = JSON.parse(stored)
    const token = parsed?.token
    
    // Ensure token is a non-empty string
    if (typeof token === "string" && token.length > 0) {
      return token
    }
    return null
  } catch {
    // If localStorage is corrupted, clear it
    localStorage.removeItem("auth")
    return null
  }
}

// Check if user is authenticated
export function isAuthenticated(): boolean {
  return getToken() !== null
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
  requiresAuth = true,
): Promise<T> {
  const { method = "GET", body, headers = {} } = options
  const token = getToken()
  
  if (requiresAuth) {
    if (!token) {
      throw new ApiError(401, "Not authenticated. Please log in.")
    }
    headers["Authorization"] = `Bearer ${token}`
  }
  
  if (body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json"
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const err = await res.json()
      detail = err.detail ?? detail
    } catch {
      // use status text
    }
    throw new ApiError(res.status, detail)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}
