import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useSeriesStore, type Series } from '../../src/stores/series'

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/client', () => ({ api: apiMock }))

const seriesConfig: Series = {
  id: 2,
  emby_series_id: 'emby-series-2',
  name: '孤独摇滚',
  library_id: 1,
  library_name: '动漫',
  staging_path: '/staging/bocchi',
  target_path: '/media/bocchi',
  default_season: 1,
  enabled: true,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
}

describe('series store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('按媒体库加载剧集并更新状态', async () => {
    apiMock.get.mockResolvedValue([seriesConfig])

    const store = useSeriesStore()
    await store.loadSeries(1)

    expect(apiMock.get).toHaveBeenCalledWith('/series?library_id=1')
    expect(store.series).toEqual([seriesConfig])
    expect(store.error).toBeNull()
  })
})
