import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import EmbySettings from '@/views/EmbySettings.vue'
import { createPinia, setActivePinia } from 'pinia'

const mockLoadEmbyConfig = vi.fn()
const mockSaveSettings = vi.fn()
const mockTestEmbyConnection = vi.fn()

vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    embyConfig: { url: 'http://localhost', apiKeyMasked: '********', apiKeySet: true, autoRefresh: true },
    loading: false,
    error: null,
    loadEmbyConfig: mockLoadEmbyConfig,
    saveSettings: mockSaveSettings,
    testEmbyConnection: mockTestEmbyConnection
  })
}))

vi.mock('naive-ui', async () => {
  const actual = await vi.importActual('naive-ui')
  return {
    ...actual,
    useMessage: () => ({
      success: vi.fn(),
      error: vi.fn()
    })
  }
})

describe('EmbySettings.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders form and calls loadEmbyConfig on mount', async () => {
    mount(EmbySettings, {
      global: {
        stubs: {
          'n-card': true,
          'n-form': true,
          'n-form-item': true,
          'n-input': true,
          'n-switch': true,
          'n-button': true,
          'n-space': true,
          'n-alert': true,
          'n-spin': true
        }
      }
    })

    expect(mockLoadEmbyConfig).toHaveBeenCalled()
  })

  it('triggers test connection action', async () => {
    const wrapper = mount(EmbySettings, {
      global: {
        stubs: {
          'n-card': true,
          'n-form': true,
          'n-form-item': true,
          'n-input': true,
          'n-switch': true,
          'n-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>'
          },
          'n-space': true,
          'n-alert': true,
          'n-spin': true
        }
      }
    })

    const testBtn = wrapper.findAll('button').find(b => b.text().includes('测试连接'))
    await testBtn?.trigger('click')
    expect(mockTestEmbyConnection).toHaveBeenCalled()
  })

  it('triggers save settings action', async () => {
    const wrapper = mount(EmbySettings, {
      global: {
        stubs: {
          'n-card': true,
          'n-form': true,
          'n-form-item': true,
          'n-input': true,
          'n-switch': true,
          'n-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>'
          },
          'n-space': true,
          'n-alert': true,
          'n-spin': true
        }
      }
    })

    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('保存'))
    await saveBtn?.trigger('click')
    expect(mockSaveSettings).toHaveBeenCalled()
  })
})
