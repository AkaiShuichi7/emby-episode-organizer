import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useTasksStore, type Task } from '../../src/stores/tasks'

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/client', () => ({ api: apiMock }))

const task: Task = {
  id: 3,
  status: 'staged',
  series_id: 2,
  series_name: '孤独摇滚',
  emby_series_id: 'emby-series-2',
  library_id: 1,
  library_name: '动漫',
  season_number: 1,
  episode_number: 8,
  title: '波形',
  source_file_path: '/downloads/08.mkv',
  staging_video_path: '/staging/08.mkv',
  staging_nfo_path: '/staging/08.nfo',
  staging_cover_path: null,
  target_video_path: '/media/Season 01/08.mkv',
  target_nfo_path: '/media/Season 01/08.nfo',
  target_cover_path: null,
  nfo_json: { title: '波形' },
  error_message: null,
  committed_at: null,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
}

describe('tasks store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('按过滤条件加载任务并更新状态', async () => {
    apiMock.get.mockResolvedValue([task])

    const store = useTasksStore()
    await store.loadTasks({ status: 'staged', series_id: 2 })

    expect(apiMock.get).toHaveBeenCalledWith('/tasks?status=staged&series_id=2')
    expect(store.tasks).toEqual([task])
    expect(store.error).toBeNull()
  })
})
