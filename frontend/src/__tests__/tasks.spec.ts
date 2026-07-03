/* global describe, it, expect, vi, beforeEach, afterEach */

import { setActivePinia, createPinia } from 'pinia'
import { api } from '@/api/client'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('tasks store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('previewTask sends correct payload', async () => {
    const { useTasksStore } = await import('@/stores/tasks')
    const store = useTasksStore()

    const mockPreview = {
      series_id: 1,
      season_number: 1,
      episode_number: 5,
      title: 'Test Episode',
      source_file_path: '/staging/Test - S01E05 - Test Episode.mkv',
      staging_video_path: '/staging/Test - S01E05 - Test Episode.mkv',
      staging_nfo_path: '/staging/Test - S01E05 - Test Episode.nfo',
      staging_cover_path: '/staging/Test - S01E05 - Test Episode-thumb.jpg',
      target_video_path: '/target/Season 01/Test - S01E05 - Test Episode.mkv',
      target_nfo_path: '/target/Season 01/Test - S01E05 - Test Episode.nfo',
      target_cover_path: '/target/Season 01/Test - S01E05 - Test Episode-thumb.jpg',
    }
    ;(api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockPreview)

    const result = await store.previewTask({
      series_id: 1,
      season_number: 1,
      episode_number: 5,
      title: 'Test Episode',
      source_file_path: '/staging/Test - S01E05 - Test Episode.mkv',
    })

    expect(api.post).toHaveBeenCalledWith('/tasks/preview', {
      series_id: 1,
      season_number: 1,
      episode_number: 5,
      title: 'Test Episode',
      source_file_path: '/staging/Test - S01E05 - Test Episode.mkv',
      cover_url: undefined,
    })
    expect(store.preview).toEqual(mockPreview)
    expect(result).toEqual(mockPreview)
  })

  it('createTask adds task to store', async () => {
    const { useTasksStore } = await import('@/stores/tasks')
    const store = useTasksStore()

    const mockTask = {
      id: 10,
      status: 'staged' as const,
      series_id: 1,
      series_name: 'Test Series',
      emby_series_id: 'emby-123',
      library_id: 1,
      library_name: 'Test Library',
      season_number: 1,
      episode_number: 5,
      title: 'Test Episode',
      source_file_path: '/source/Test.mkv',
      staging_video_path: '/staging/Test - S01E05 - Test Episode.mkv',
      staging_nfo_path: null,
      staging_cover_path: null,
      target_video_path: '/target/Season 01/Test - S01E05 - Test Episode.mkv',
      target_nfo_path: null,
      target_cover_path: null,
      nfo_json: null,
      error_message: null,
      committed_at: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }
    ;(api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockTask)

    const result = await store.createTask({
      series_id: 1,
      season_number: 1,
      episode_number: 5,
      title: 'Test Episode',
      source_file_path: '/source/Test.mkv',
    })

    expect(api.post).toHaveBeenCalledWith('/tasks', {
      series_id: 1,
      season_number: 1,
      episode_number: 5,
      title: 'Test Episode',
      source_file_path: '/source/Test.mkv',
      cover_url: undefined,
      nfo_json: undefined,
    })
    expect(store.tasks).toContainEqual(mockTask)
    expect(store.currentTask).toEqual(mockTask)
    expect(result).toEqual(mockTask)
  })

  it('loadTasks populates tasks array', async () => {
    const { useTasksStore } = await import('@/stores/tasks')
    const store = useTasksStore()

    const mockTasks = [
      {
        id: 1,
        status: 'staged' as const,
        series_id: 1,
        series_name: 'Series A',
        emby_series_id: 'emby-1',
        library_id: 1,
        library_name: 'Lib A',
        season_number: 1,
        episode_number: 1,
        title: 'Episode 1',
        source_file_path: '/source/a.mkv',
        staging_video_path: '/staging/a.mkv',
        staging_nfo_path: null,
        staging_cover_path: null,
        target_video_path: '/target/Season 01/a.mkv',
        target_nfo_path: null,
        target_cover_path: null,
        nfo_json: null,
        error_message: null,
        committed_at: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ]
    ;(api.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockTasks)

    const result = await store.loadTasks()

    expect(api.get).toHaveBeenCalledWith('/tasks')
    expect(store.tasks).toEqual(mockTasks)
    expect(result).toEqual(mockTasks)
  })

  it('cancelTask updates cached task', async () => {
    const { useTasksStore } = await import('@/stores/tasks')
    const store = useTasksStore()
    const task = {
      id: 1,
      status: 'staged' as const,
      series_id: 1,
      series_name: 'Series A',
      emby_series_id: 'emby-1',
      library_id: 1,
      library_name: 'Lib A',
      season_number: 1,
      episode_number: 1,
      title: 'Episode 1',
      source_file_path: '/source/a.mkv',
      staging_video_path: '/staging/a.mkv',
      staging_nfo_path: null,
      staging_cover_path: null,
      target_video_path: '/target/Season 01/a.mkv',
      target_nfo_path: null,
      target_cover_path: null,
      nfo_json: null,
      error_message: null,
      committed_at: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }
    const cancelled = { ...task, status: 'cancelled' as const }
    store.tasks = [task]
    store.currentTask = task
    ;(api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce(cancelled)

    const result = await store.cancelTask(1)

    expect(api.post).toHaveBeenCalledWith('/tasks/1/cancel')
    expect(store.tasks).toEqual([cancelled])
    expect(store.currentTask).toEqual(cancelled)
    expect(result).toEqual(cancelled)
  })
})
