import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import Dashboard from '@/views/Dashboard.vue'

const mockLoadEmbyConfig = vi.fn()
vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    embyConfig: { url: 'http://localhost', api_key: '123' },
    loadEmbyConfig: mockLoadEmbyConfig
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
  it('renders 4 cards and calls load methods', async () => {
    const wrapper = mount(Dashboard, {
      global: {
        stubs: {
          'n-grid': true,
          'n-grid-item': true,
          'n-card': true,
          'n-spin': true,
          'n-data-table': true,
          'n-badge': true,
          'n-space': true
        }
      }
    })

    expect(mockLoadEmbyConfig).toHaveBeenCalled()
    expect(mockLoadLibraries).toHaveBeenCalled()
    expect(mockLoadSeries).toHaveBeenCalled()
    expect(mockLoadTasks).toHaveBeenCalledWith({ status: 'staged' })

    const cards = wrapper.findAll('.n-card-header__main')
    expect(cards.length).toBe(4)
    expect(cards[0].text()).toBe('Emby 状态')
    expect(cards[1].text()).toBe('媒体库数量')
    expect(cards[2].text()).toBe('剧集数量')
    expect(cards[3].text()).toBe('待入库任务')
  })
})
