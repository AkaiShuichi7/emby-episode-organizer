import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/api/client'

export interface Series {
  id: number
  emby_series_id: string | null
  name: string
  library_id: number | null
  library_name: string | null
  staging_path: string | null
  target_path: string | null
  default_season: number
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface SeriesCreatePayload {
  name: string
  library_id?: number | null
  emby_series_id?: string | null
  staging_path?: string | null
  target_path?: string | null
  default_season: number
  enabled: boolean
}

export interface SeriesUpdatePayload {
  name?: string | null
  library_id?: number | null
  emby_series_id?: string | null
  staging_path?: string | null
  target_path?: string | null
  default_season?: number | null
  enabled?: boolean | null
}

export interface Season {
  Id?: string
  Name?: string
  IndexNumber?: number
  [key: string]: unknown
}

export interface Episode {
  Id?: string
  Name?: string
  IndexNumber?: number
  ParentIndexNumber?: number
  [key: string]: unknown
}

export interface EmbySeries {
  Id?: string
  Name?: string
  ProductionYear?: number
  [key: string]: unknown
}

export interface LatestEpisode {
  latest_episode: number
  next_episode: number
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '请求失败'
}

function withQuery(path: string, params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

/**
 * 管理剧集配置与 Emby 剧集查询结果。
 *
 * @returns 剧集配置、Emby 季集数据状态与相关加载/保存动作。
 */
export const useSeriesStore = defineStore('series', () => {
  const series = ref<Series[]>([])
  const currentSeries = ref<Series | null>(null)
  const seasons = ref<Season[]>([])
  const episodes = ref<Episode[]>([])
  const latestEpisode = ref<LatestEpisode | null>(null)
  const embySearchResults = ref<EmbySeries[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function run<T>(action: () => Promise<T>): Promise<T | null> {
    loading.value = true
    error.value = null

    try {
      return await action()
    } catch (caught) {
      error.value = getErrorMessage(caught)
      return null
    } finally {
      loading.value = false
    }
  }

  async function loadSeries(libraryId?: number) {
    return run(async () => {
      const loadedSeries = await api.get<Series[]>(withQuery('/series', { library_id: libraryId }))
      series.value = loadedSeries
      return loadedSeries
    })
  }

  async function loadEmbySeries(q: string) {
    return run(async () => {
      const results = await api.get<EmbySeries[]>(withQuery('/emby/series/search', { keyword: q }))
      embySearchResults.value = results
      return results
    })
  }

  async function loadSeasons(embySeriesId: string) {
    return run(async () => {
      const loadedSeasons = await api.get<Season[]>(`/emby/series/${embySeriesId}/seasons`)
      seasons.value = loadedSeasons
      return loadedSeasons
    })
  }

  async function loadEpisodes(embySeriesId: string, season: number) {
    return run(async () => {
      const loadedEpisodes = await api.get<Episode[]>(`/emby/series/${embySeriesId}/seasons/${season}/episodes`)
      episodes.value = loadedEpisodes
      return loadedEpisodes
    })
  }

  async function loadLatestEpisode(embySeriesId: string, season: number) {
    return run(async () => {
      const episode = await api.get<LatestEpisode>(`/emby/series/${embySeriesId}/seasons/${season}/latest`)
      latestEpisode.value = episode
      return episode
    })
  }

  async function createSeriesConfig(payload: SeriesCreatePayload) {
    return run(async () => {
      const createdSeries = await api.post<Series>('/series', payload)
      series.value = [...series.value, createdSeries]
      currentSeries.value = createdSeries
      return createdSeries
    })
  }

  async function updateSeriesConfig(id: number, payload: SeriesUpdatePayload) {
    return run(async () => {
      const updatedSeries = await api.put<Series>(`/series/${id}`, payload)
      series.value = series.value.map((item) => (item.id === id ? updatedSeries : item))
      currentSeries.value = updatedSeries
      return updatedSeries
    })
  }

  return {
    series,
    currentSeries,
    seasons,
    episodes,
    latestEpisode,
    embySearchResults,
    loading,
    error,
    loadSeries,
    loadEmbySeries,
    loadSeasons,
    loadEpisodes,
    loadLatestEpisode,
    createSeriesConfig,
    updateSeriesConfig,
  }
})
