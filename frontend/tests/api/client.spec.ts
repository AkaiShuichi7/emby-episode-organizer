import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/api/client'

describe('api client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('构造 GET 请求', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await api.get('/health')

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/health', expect.objectContaining({ method: 'GET' }))
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect((init.headers as Headers).get('accept')).toBe('application/json')
  })

  it('序列化 POST JSON body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await api.post('/api/v1/libraries', { name: 'demo' })

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect(init.body).toBe(JSON.stringify({ name: 'demo' }))
    expect((init.headers as Headers).get('content-type')).toBe('application/json')
  })

  it('保留 FormData 的 multipart 边界', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const formData = new FormData()
    formData.append('file', new Blob(['demo']), 'demo.txt')

    await api.post('/api/v1/tasks/1/cover', formData)

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.body).toBe(formData)
    expect((init.headers as Headers).has('content-type')).toBe(false)
  })

  it('抛出 ApiError 时带 message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ success: false, message: '坏请求', detail: { field: 'name' } }), {
          status: 400,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    )

    await expect(api.get('/api/v1/settings')).rejects.toMatchObject({
      name: 'ApiError',
      status: 400,
      message: '坏请求',
      detail: { field: 'name' },
    })
  })

  it('返回 2xx JSON 数据', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ data: 1 }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    )

    await expect(api.get<{ data: number }>('/api/v1/health')).resolves.toEqual({ data: 1 })
  })
})
