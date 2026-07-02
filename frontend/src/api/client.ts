import type { paths } from './types'

const API_BASE = '/api/v1'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'
type ApiPath = keyof paths

interface ApiErrorPayload {
  success?: boolean
  message?: string
  detail?: unknown
}

/**
 * API 错误。
 *
 * 统一承载 HTTP 状态码、错误信息和后端 detail，便于前端直接展示或分支处理。
 */
export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, message: string, detail: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Object.prototype.toString.call(value) === '[object Object]'
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return undefined
  }

  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    return response.json()
  }

  const text = await response.text()
  return text.length > 0 ? text : undefined
}

async function parseError(response: Response): Promise<ApiErrorPayload> {
  const body = await parseBody(response)
  if (isPlainObject(body)) {
    return body as ApiErrorPayload
  }

  return {}
}

function normalizeHeaders(body: unknown, headers?: HeadersInit): Headers {
  const nextHeaders = new Headers(headers)
  nextHeaders.set('Accept', 'application/json')

  if (body instanceof FormData) {
    nextHeaders.delete('Content-Type')
    return nextHeaders
  }

  if (body !== undefined && body !== null && !nextHeaders.has('Content-Type')) {
    nextHeaders.set('Content-Type', 'application/json')
  }

  return nextHeaders
}

function normalizeBody(body: unknown, headers: Headers): BodyInit | undefined {
  if (body === undefined || body === null) {
    return undefined
  }

  if (body instanceof FormData || body instanceof Blob || body instanceof URLSearchParams || body instanceof ReadableStream) {
    headers.delete('Content-Type')
    return body
  }

  if (typeof body === 'string') {
    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'text/plain;charset=UTF-8')
    }
    return body
  }

  if (body instanceof ArrayBuffer || ArrayBuffer.isView(body)) {
    headers.delete('Content-Type')
    return body as ArrayBuffer
  }

  if (isPlainObject(body) || Array.isArray(body)) {
    headers.set('Content-Type', 'application/json')
    return JSON.stringify(body)
  }

  // ponytail: TS narrows BodyInit 不到某些 unknown 分支, 强制 cast; runtime 安全.
  return body as BodyInit
}

/**
 * 发送 API 请求。
 *
 * @param path OpenAPI 路径，默认走 `/api/v1`。
 * @param options fetch 配置。
 * @returns 解析后的 JSON 或文本结果。
 * @throws ApiError 当 HTTP 状态码非 2xx 时抛出。
 */
export async function apiRequest<T>(path: ApiPath | string, options: RequestInit = {}): Promise<T> {
  const headers = normalizeHeaders(options.body, options.headers)
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    body: normalizeBody(options.body, headers),
  })

  if (!response.ok) {
    const payload = await parseError(response)
    throw new ApiError(
      response.status,
      payload.message ?? `请求失败：${response.status}`,
      payload.detail ?? payload,
    )
  }

  return (await parseBody(response)) as T
}

export const api = {
  /** GET 请求。 */
  get<T>(path: ApiPath | string, options: RequestInit = {}) {
    return apiRequest<T>(path, { ...options, method: 'GET' })
  },
  /** POST 请求。 */
  post<T>(path: ApiPath | string, body?: unknown, options: RequestInit = {}) {
    return apiRequest<T>(path, { ...options, method: 'POST', body: body as BodyInit | null | undefined })
  },
  /** PUT 请求。 */
  put<T>(path: ApiPath | string, body?: unknown, options: RequestInit = {}) {
    return apiRequest<T>(path, { ...options, method: 'PUT', body: body as BodyInit | null | undefined })
  },
  /** DELETE 请求。 */
  delete<T>(path: ApiPath | string, options: RequestInit = {}) {
    return apiRequest<T>(path, { ...options, method: 'DELETE' })
  },
}
