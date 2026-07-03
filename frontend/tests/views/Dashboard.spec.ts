import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { flushPromises } from '@vue/test-utils'
import Dashboard from '@/views/Dashboard.vue'

const mockLoadSettings = vi.fn()
vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    allSettings: {
      'emby.server_url': 'http://localhost',
      'emby.api_key': '123'
    },
    loadSettings: mockLoadSettings
  })
}))

const mockLoadLibraries = vi.fn()
vi.mock('@/stores/libraries', () => ({
  useLibrariesStore: () => ({
    libraries: [],
    loadLibraries: mockLoadLibraries
  })
}))

const mockLoadSeries = vi.fn()
vi.mock('@/stores/series', () => ({
  useSeriesStore: () => ({
    series: [],
    loadSeries: mockLoadSeries
  })
}))

const mockLoadTasks = vi.fn()
vi.mock('@/stores/tasks', () => ({
  useTasksStore: () => ({
    tasks: [],
    loadTasks: mockLoadTasks
  })
}))

describe('Dashboard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders 4 cards and calls load methods', async () => {
    const wrapper = mount(Dashboard, {
      global: {
        stubs: {
          'n-grid': { template: '<div><slot /></div>' },
          'n-grid-item': { template: '<div><slot /></div>' },
          'n-card': { props: ['title'], template: '<div class="n-card-header__main">{{ title }}<slot /></div>' },
          'n-spin': { template: '<div><slot /></div>' },
          'n-data-table': { template: '<div />' },
          'n-badge': { template: '<div />' },
          'n-space': { template: '<div><slot /></div>' }
        }
      }
    })

    await flushPromises()

    expect(mockLoadSettings).toHaveBeenCalled()
    expect(mockLoadLibraries).toHaveBeenCalled()
    expect(mockLoadSeries).toHaveBeenCalled()
    expect(mockLoadTasks).toHaveBeenCalledWith({})

    const cards = wrapper.findAll('.n-card-header__main')
    expect(cards.length).toBe(4)
    expect(cards[0].text()).toBe('Emby 状态')
    expect(cards[1].text()).toBe('媒体库数量')
    expect(cards[2].text()).toBe('剧集数量')
    expect(cards[3].text()).toBe('待入库任务')
  })
})
