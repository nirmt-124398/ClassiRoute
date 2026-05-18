import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiRequest, ApiError } from './client'

const mockStorage: Record<string, string> = {}
vi.stubGlobal('localStorage', {
  getItem: (key: string) => mockStorage[key] ?? null,
  setItem: (key: string, value: string) => { mockStorage[key] = value },
  removeItem: (key: string) => { delete mockStorage[key] },
  clear: () => { Object.keys(mockStorage).forEach(k => delete mockStorage[k]) },
})

global.fetch = vi.fn()

describe('api client', () => {
  beforeEach(() => {
    mockStorage['auth'] = JSON.stringify({
      token: 'fake-jwt-token',
      user: { id: '123', email: 'test@test.com', username: 'testuser' },
      loading: false,
    })
    ;(global.fetch as vi.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: 'test' }),
      statusText: 'OK',
    } as any)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('attaches Authorization header from localStorage "auth" key', async () => {
    await apiRequest('/test-endpoint')
    const call = (global.fetch as vi.Mock).mock.calls[0]
    const headers = call[1]?.headers as Record<string, string>
    expect(headers['Authorization']).toBe('Bearer fake-jwt-token')
  })

  it('sends no Authorization header when not logged in', async () => {
    localStorage.clear()
    ;(global.fetch as vi.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
      statusText: 'OK',
    } as any)
    await apiRequest('/test-endpoint')
    const call = (global.fetch as vi.Mock).mock.calls[0]
    const headers = call[1]?.headers as Record<string, string>
    expect(headers['Authorization']).toBeUndefined()
  })

  it('throws ApiError on non-ok response', async () => {
    ;(global.fetch as vi.Mock).mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Content',
      json: async () => ({ detail: 'validation error' }),
    } as any)
    await expect(apiRequest('/test-endpoint')).rejects.toThrow(ApiError)
    await expect(apiRequest('/test-endpoint')).rejects.toMatchObject({
      status: 422,
      detail: 'validation error',
    })
  })
})