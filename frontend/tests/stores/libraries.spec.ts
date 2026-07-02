import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useLibrariesStore, type Library } from '../../src/stores/libraries'

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/client', () => ({ api: apiMock }))

const library: Library = {
  id: 1,
  emby_library_id: 'emby-1',
  name: '动漫',
  collection_type: 'tvshows',
  staging_root: '/staging',
  target_root: '/media',
  enabled: true,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
}

describe('libraries store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('加载媒体库并更新状态', async () => {
    apiMock.get.mockResolvedValue([library])

    const store = useLibrariesStore()
    await store.loadLibraries()

    expect(apiMock.get).toHaveBeenCalledWith('/libraries')
    expect(store.libraries).toEqual([library])
    expect(store.error).toBeNull()
  })
})
