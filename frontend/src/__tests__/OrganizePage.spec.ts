/* global describe, it, expect, vi, beforeEach */

import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import {
  NConfigProvider,
  NDialogProvider,
  NMessageProvider,
  NCard,
  NForm,
  NFormItem,
  NSelect,
  NInput,
  NInputNumber,
  NButton,
  NSpace,
  NTabs,
  NTabPane,
  NGrid,
  NFormItemGi,
  NGridItem,
  NSpin,
} from 'naive-ui'
import OrganizePage from '@/views/OrganizePage.vue'
import { api } from '@/api/client'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

const mockMessage = {
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
}

vi.mock('naive-ui', async () => {
  const actual = await vi.importActual('naive-ui')
  return {
    ...actual,
    useMessage: () => mockMessage,
  }
})

const organizePageStubs = {
  'n-config-provider': NConfigProvider,
  'n-dialog-provider': NDialogProvider,
  'n-message-provider': NMessageProvider,
  'n-card': NCard,
  'n-form': NForm,
  'n-form-item': NFormItem,
  'n-select': NSelect,
  'n-input': NInput,
  'n-input-number': NInputNumber,
  'n-button': NButton,
  'n-space': NSpace,
  'n-tabs': NTabs,
  'n-tab-pane': NTabPane,
  'n-grid': NGrid,
  'n-form-item-gi': NFormItemGi,
  'n-grid-item': NGridItem,
  'n-spin': NSpin,
  RouterView: true,
  'main-layout': true,
}

const mockSeries = [
  {
    id: 1,
    name: 'Test Series',
    emby_series_id: 'emby-123',
    library_id: 1,
    library_name: 'Test Lib',
    staging_path: '/staging',
    target_path: '/target',
    default_season: 1,
    enabled: true,
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  },
]

function mountOrganizePage() {
  return mount(OrganizePage, {
    global: {
      plugins: [createPinia()],
      stubs: organizePageStubs,
    },
  })
}

function findInput(wrapper: ReturnType<typeof mountOrganizePage>, placeholder: string) {
  const input = wrapper.findAllComponents(NInput).find((item) => item.props('placeholder') === placeholder)
  expect(input).toBeTruthy()
  return input!
}

describe('OrganizePage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads series on mount', async () => {
    const mockSeries = [
      {
        id: 1,
        name: 'Test Series',
        emby_series_id: 'emby-123',
        library_id: 1,
        library_name: 'Test Lib',
        staging_path: '/staging',
        target_path: '/target',
        default_season: 1,
        enabled: true,
        created_at: '2026-01-01',
        updated_at: '2026-01-01',
      },
    ]
    ;(api.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockSeries)

    mount(OrganizePage, {
      global: {
        plugins: [createPinia()],
        stubs: {
          'n-config-provider': NConfigProvider,
          'n-dialog-provider': NDialogProvider,
          'n-message-provider': NMessageProvider,
          'n-card': NCard,
          'n-form': NForm,
          'n-form-item': NFormItem,
          'n-select': NSelect,
          'n-input': NInput,
          'n-input-number': NInputNumber,
          'n-button': NButton,
          'n-space': NSpace,
          'n-tabs': NTabs,
          'n-tab-pane': NTabPane,
          'n-grid': NGrid,
          'n-form-item-gi': NFormItemGi,
          'n-grid-item': NGridItem,
          'n-spin': NSpin,
          RouterView: true,
          'main-layout': true,
        },
      },
    })

    await nextTick()
    expect(api.get).toHaveBeenCalledWith('/series')
  })

  it('selecting series loads seasons via emby_series_id', async () => {
    const mockSeries = [
      {
        id: 1,
        name: 'Test Series',
        emby_series_id: 'emby-123',
        library_id: 1,
        library_name: 'Test Lib',
        staging_path: '/staging',
        target_path: '/target',
        default_season: 1,
        enabled: true,
        created_at: '2026-01-01',
        updated_at: '2026-01-01',
      },
    ]
    const mockSeasons = [
      { Id: '1', Name: 'Season 1', IndexNumber: 1 },
      { Id: '2', Name: 'Season 2', IndexNumber: 2 },
    ]

    ;(api.get as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce(mockSeries)
      .mockResolvedValueOnce(mockSeasons)

    const wrapper = mount(OrganizePage, {
      global: {
        plugins: [createPinia()],
        stubs: {
          'n-config-provider': NConfigProvider,
          'n-dialog-provider': NDialogProvider,
          'n-message-provider': NMessageProvider,
          'n-card': NCard,
          'n-form': NForm,
          'n-form-item': NFormItem,
          'n-select': NSelect,
          'n-input': NInput,
          'n-input-number': NInputNumber,
          'n-button': NButton,
          'n-space': NSpace,
          'n-tabs': NTabs,
          'n-tab-pane': NTabPane,
          'n-grid': NGrid,
          'n-form-item-gi': NFormItemGi,
          'n-grid-item': NGridItem,
          'n-spin': NSpin,
          RouterView: true,
          'main-layout': true,
        },
      },
    })

    await nextTick()
    const seriesSelect = wrapper.findAllComponents(NSelect)[0]
    seriesSelect.vm.$emit('update:value', 1)
    await nextTick()

    expect(api.get).toHaveBeenCalledWith('/emby/series/emby-123/seasons')
  })

  it('updates source-derived title unless title was manually edited', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce([])

    const wrapper = mountOrganizePage()
    await nextTick()

    const fileDialog = wrapper.findComponent({ name: 'FileBrowserDialog' })
    fileDialog.vm.$emit('select', '/downloads/AAA.mp4')
    await nextTick()
    expect(findInput(wrapper, '分集标题').props('value')).toBe('AAA')

    fileDialog.vm.$emit('select', '/downloads/BBB.mp4')
    await nextTick()
    expect(findInput(wrapper, '分集标题').props('value')).toBe('BBB')

    findInput(wrapper, '分集标题').vm.$emit('update:value', '手动标题')
    await nextTick()
    fileDialog.vm.$emit('select', '/downloads/CCC.mp4')
    await nextTick()

    expect(findInput(wrapper, '分集标题').props('value')).toBe('手动标题')
  })

  it('creates task with initial nfo title and resets form on success', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockImplementation((path: string) => {
      if (path === '/series') return Promise.resolve(mockSeries)
      if (path === '/tasks') return Promise.resolve([])
      return Promise.resolve([])
    })
    ;(api.post as ReturnType<typeof vi.fn>).mockImplementation((path: string, payload: unknown) => {
      if (path === '/tasks/preview') return Promise.resolve(payload)
      if (path === '/tasks') {
        return Promise.resolve({
          id: 1,
          status: 'staged',
          nfo_json: { title: 'AAA' },
        })
      }
      return Promise.resolve(null)
    })

    const wrapper = mountOrganizePage()
    await nextTick()
    wrapper.findAllComponents(NSelect)[0].vm.$emit('update:value', 1)
    wrapper.findComponent({ name: 'FileBrowserDialog' }).vm.$emit('select', '/downloads/AAA.mp4')
    wrapper.findComponent(NInputNumber).vm.$emit('update:value', 8)
    await nextTick()

    const createButton = wrapper.findAllComponents(NButton).find((button) => button.text() === '创建整理任务')
    await createButton?.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/tasks', {
      series_id: 1,
      season_number: 1,
      episode_number: 8,
      title: 'AAA',
      source_file_path: '/downloads/AAA.mp4',
      cover_url: null,
      nfo_json: { title: 'AAA' },
    })
    expect(mockMessage.success).toHaveBeenCalledWith('任务创建成功')
    expect(findInput(wrapper, '选择服务器上的视频文件').props('value')).toBe('')
    expect(findInput(wrapper, '分集标题').props('value')).toBe('')

    ;(api.post as ReturnType<typeof vi.fn>).mockClear()
    wrapper.findComponent({ name: 'FileBrowserDialog' }).vm.$emit('select', '/downloads/DDD.mp4')
    await nextTick()
    await createButton?.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/tasks', {
      series_id: 1,
      season_number: 1,
      episode_number: 1,
      title: 'DDD',
      source_file_path: '/downloads/DDD.mp4',
      cover_url: null,
      nfo_json: { title: 'DDD' },
    })
  })
})
