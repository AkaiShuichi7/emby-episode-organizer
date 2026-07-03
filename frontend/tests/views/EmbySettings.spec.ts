import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import EmbySettings from '@/views/EmbySettings.vue'
import { createPinia, setActivePinia } from 'pinia'

const mockLoadSettings = vi.fn()
const mockSaveSettings = vi.fn()

vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    allSettings: {
      'emby.server_url': 'http://localhost',
      'emby.api_key': '************',
      'emby.auto_refresh': true
    },
    loading: false,
    error: null,
    loadSettings: mockLoadSettings,
    saveSettings: mockSaveSettings,
    testEmbyConnection: vi.fn()
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
    mockLoadSettings.mockResolvedValue({})
    mockSaveSettings.mockResolvedValue({})
  })

  it('renders form and calls loadSettings on mount', async () => {
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

    await flushPromises()

    expect(mockLoadSettings).toHaveBeenCalled()
  })

  it('save does not submit masked api key', async () => {
    const wrapper = mount(EmbySettings, {
      global: {
        stubs: {
          'n-card': { template: '<div><slot name="header-extra" /><slot /></div>' },
          'n-form': { template: '<form><slot /></form>' },
          'n-form-item': { template: '<div><slot /></div>' },
          'n-input': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['modelValue']
          },
          'n-switch': true,
          'n-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>'
          },
          'n-space': { template: '<div><slot /></div>' },
          'n-alert': true,
          'n-spin': true
        }
      }
    })

    await flushPromises()

    const inputs = wrapper.findAll('input')
    await inputs[0]?.setValue('http://localhost')
    await inputs[1]?.setValue('************')

    await wrapper.findAll('button')[0]?.trigger('click')

    expect(mockSaveSettings).toHaveBeenCalledWith({
      'emby.server_url': 'http://localhost',
      'emby.auto_refresh': true
    })
  })
})
