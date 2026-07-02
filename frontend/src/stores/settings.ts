import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/api/client'

export interface EmbyConfig {
  url?: string
  apiKeyMasked?: string
  apiKeySet?: boolean
  autoRefresh?: boolean
}

export type SettingsMap = Record<string, unknown>

export interface EmbyTestPayload {
  server_url: string
  api_key: string
}

export interface EmbyTestResult {
  success: boolean
  message: string
  server_name?: string | null
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '请求失败'
}

/**
 * 管理全局设置与 Emby 连接配置。
 *
 * @returns 设置状态、加载动作、保存动作与连接测试动作。
 */
export const useSettingsStore = defineStore('settings', () => {
  const embyConfig = ref<EmbyConfig | null>(null)
  const allSettings = ref<SettingsMap>({})
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

  async function loadSettings() {
    return run(async () => {
      const settings = await api.get<SettingsMap>('/settings')
      allSettings.value = settings
      return settings
    })
  }

  async function loadEmbyConfig() {
    return run(async () => {
      const config = await api.get<EmbyConfig>('/settings/emby')
      embyConfig.value = config
      return config
    })
  }

  async function saveSettings(payload: SettingsMap) {
    return run(async () => {
      const settings = await api.put<SettingsMap>('/settings', payload)
      allSettings.value = settings
      return settings
    })
  }

  async function testEmbyConnection(payload: EmbyTestPayload) {
    return run(() => api.post<EmbyTestResult>('/emby/test', payload))
  }

  return { embyConfig, allSettings, loading, error, loadSettings, loadEmbyConfig, saveSettings, testEmbyConnection }
})
