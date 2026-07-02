import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/api/client'

export interface Library {
  id: number
  emby_library_id: string | null
  name: string
  collection_type: string | null
  staging_root: string | null
  target_root: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface LibraryCreatePayload {
  name: string
  collection_type?: string | null
  staging_root: string
  target_root: string
  enabled: boolean
}

export interface LibraryUpdatePayload {
  name?: string | null
  collection_type?: string | null
  staging_root?: string | null
  target_root?: string | null
  enabled?: boolean | null
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '请求失败'
}

/**
 * 管理媒体库映射列表。
 *
 * @returns 媒体库状态、加载、创建、更新与删除动作。
 */
export const useLibrariesStore = defineStore('libraries', () => {
  const libraries = ref<Library[]>([])
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

  async function loadLibraries() {
    return run(async () => {
      const loadedLibraries = await api.get<Library[]>('/libraries')
      libraries.value = loadedLibraries
      return loadedLibraries
    })
  }

  async function createLibrary(payload: LibraryCreatePayload) {
    return run(async () => {
      const library = await api.post<Library>('/libraries', payload)
      libraries.value = [...libraries.value, library]
      return library
    })
  }

  async function updateLibrary(id: number, payload: LibraryUpdatePayload) {
    return run(async () => {
      const library = await api.put<Library>(`/libraries/${id}`, payload)
      libraries.value = libraries.value.map((item) => (item.id === id ? library : item))
      return library
    })
  }

  async function deleteLibrary(id: number) {
    return run(async () => {
      await api.delete<void>(`/libraries/${id}`)
      libraries.value = libraries.value.filter((item) => item.id !== id)
    })
  }

  return { libraries, loading, error, loadLibraries, createLibrary, updateLibrary, deleteLibrary }
})
