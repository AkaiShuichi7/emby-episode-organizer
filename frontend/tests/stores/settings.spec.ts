import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useSettingsStore } from '../../src/stores/settings'

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/client', () => ({ api: apiMock }))

describe('settings store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('加载全部设置并更新状态', async () => {
    const settings = { 'emby.server_url': 'http://emby.local', 'emby.api_key': 'xxxx****1234' }
    apiMock.get.mockResolvedValue(settings)

    const store = useSettingsStore()
    await store.loadSettings()

    expect(apiMock.get).toHaveBeenCalledWith('/settings')
    expect(store.allSettings).toEqual(settings)
    expect(store.error).toBeNull()
  })
})
