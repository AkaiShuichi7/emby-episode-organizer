/* global describe, it, expect, vi, beforeEach, afterEach */

import { setActivePinia, createPinia } from 'pinia'
import { api } from '@/api/client'

// Mock api module
vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('series store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loadSeasons calls correct endpoint', async () => {
    const { useSeriesStore } = await import('@/stores/series')
    const store = useSeriesStore()

    const mockSeasons = [
      { Id: '1', Name: 'Season 1', IndexNumber: 1 },
      { Id: '2', Name: 'Season 2', IndexNumber: 2 },
    ]
    ;(api.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockSeasons)

    const result = await store.loadSeasons('emby-series-123')

    expect(api.get).toHaveBeenCalledWith('/emby/series/emby-series-123/seasons')
    expect(store.seasons).toEqual(mockSeasons)
    expect(result).toEqual(mockSeasons)
  })

  it('loadLatestEpisode calls correct endpoint with season', async () => {
    const { useSeriesStore } = await import('@/stores/series')
    const store = useSeriesStore()

    const mockLatest = { latest_episode: 5, next_episode: 6 }
    ;(api.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockLatest)

    const result = await store.loadLatestEpisode('emby-series-123', 1)

    expect(api.get).toHaveBeenCalledWith('/emby/series/emby-series-123/seasons/1/latest')
    expect(store.latestEpisode).toEqual(mockLatest)
    expect(result).toEqual(mockLatest)
  })

  it('loadEpisodes calls correct endpoint with season number', async () => {
    const { useSeriesStore } = await import('@/stores/series')
    const store = useSeriesStore()

    const mockEpisodes = [
      { Id: 'e1', Name: 'Episode 1', IndexNumber: 1, ParentIndexNumber: 1 },
      { Id: 'e2', Name: 'Episode 2', IndexNumber: 2, ParentIndexNumber: 1 },
    ]
    ;(api.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockEpisodes)

    const result = await store.loadEpisodes('emby-series-123', 1)

    expect(api.get).toHaveBeenCalledWith('/emby/series/emby-series-123/seasons/1/episodes')
    expect(store.episodes).toEqual(mockEpisodes)
    expect(result).toEqual(mockEpisodes)
  })
})
