import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/api/client'

export type TaskStatus = 'draft' | 'staged' | 'nfo_edited' | 'ready_to_commit' | 'committed' | 'failed' | 'cancelled'

export interface Task {
  id: number
  status: TaskStatus
  series_id: number | null
  series_name: string | null
  emby_series_id: string | null
  library_id: number | null
  library_name: string | null
  season_number: number
  episode_number: number
  title: string | null
  source_file_path: string | null
  staging_video_path: string | null
  staging_nfo_path: string | null
  staging_cover_path: string | null
  target_video_path: string | null
  target_nfo_path: string | null
  target_cover_path: string | null
  nfo_json: Record<string, unknown> | null
  error_message: string | null
  committed_at: string | null
  created_at: string
  updated_at: string
}

export interface TaskFilters {
  status?: TaskStatus
  series_id?: number
}

export interface TaskPreviewPayload {
  series_id: number
  season_number: number
  episode_number?: number | null
  title: string
  source_file_path: string
  cover_url?: string | null
}

export interface TaskPreview {
  series_id: number
  season_number: number
  episode_number?: number | null
  title: string
  source_file_path: string
  staging_video_path?: string | null
  staging_nfo_path?: string | null
  staging_cover_path?: string | null
  target_video_path?: string | null
  target_nfo_path?: string | null
  target_cover_path?: string | null
}

export interface TaskCreatePayload {
  series_id: number
  season_number: number
  episode_number: number
  title: string
  source_file_path: string
  cover_url?: string | null
  nfo_json?: Record<string, unknown> | null
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
 * 管理整理任务、预览结果与任务提交动作。
 *
 * @returns 任务状态、预览状态、加载、创建、更新与提交动作。
 */
export const useTasksStore = defineStore('tasks', () => {
  const tasks = ref<Task[]>([])
  const currentTask = ref<Task | null>(null)
  const preview = ref<TaskPreview | null>(null)
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

  async function loadTasks(filters: TaskFilters = {}) {
    return run(async () => {
      const loadedTasks = await api.get<Task[]>(withQuery('/tasks', { status: filters.status, series_id: filters.series_id }))
      tasks.value = loadedTasks
      return loadedTasks
    })
  }

  async function previewTask(payload: TaskPreviewPayload) {
    return run(async () => {
      const nextPreview = await api.post<TaskPreview>('/tasks/preview', payload)
      preview.value = nextPreview
      return nextPreview
    })
  }

  async function createTask(payload: TaskCreatePayload) {
    return run(async () => {
      const task = await api.post<Task>('/tasks', payload)
      tasks.value = [...tasks.value, task]
      currentTask.value = task
      return task
    })
  }

  async function updateNFO(id: number, nfoJson: Record<string, unknown>) {
    return run(async () => {
      const task = await api.put<Task>(`/tasks/${id}/nfo`, { nfo_json: nfoJson })
      currentTask.value = task
      tasks.value = tasks.value.map((item) => (item.id === id ? task : item))
      return task
    })
  }

  async function uploadCover(id: number, file: File) {
    return run(async () => {
      const formData = new FormData()
      formData.append('file', file)
      const task = await api.post<Task>(`/tasks/${id}/cover/upload`, formData)
      currentTask.value = task
      tasks.value = tasks.value.map((item) => (item.id === id ? task : item))
      return task
    })
  }

  async function downloadCover(id: number, url: string) {
    return run(async () => {
      const task = await api.post<Task>(`/tasks/${id}/cover/download`, { cover_url: url })
      currentTask.value = task
      tasks.value = tasks.value.map((item) => (item.id === id ? task : item))
      return task
    })
  }

  async function commitTask(id: number) {
    return run(async () => {
      const task = await api.post<Task>(`/tasks/${id}/commit`)
      currentTask.value = task
      tasks.value = tasks.value.map((item) => (item.id === id ? task : item))
      return task
    })
  }

  async function deleteTask(id: number) {
    return run(async () => {
      await api.delete<void>(`/tasks/${id}`)
      tasks.value = tasks.value.filter((item) => item.id !== id)
      if (currentTask.value?.id === id) currentTask.value = null
    })
  }

  return {
    tasks,
    currentTask,
    preview,
    loading,
    error,
    loadTasks,
    previewTask,
    createTask,
    updateNFO,
    uploadCover,
    downloadCover,
    commitTask,
    deleteTask,
  }
})
