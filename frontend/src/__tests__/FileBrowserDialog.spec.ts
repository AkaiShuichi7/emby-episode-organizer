/* global describe, it, expect, vi, beforeEach */

import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import {
  NModal,
  NList,
  NListItem,
  NButton,
  NSpace,
  NBreadcrumb,
  NBreadcrumbItem,
  NText,
  NSpin,
} from 'naive-ui'
import FileBrowserDialog from '@/components/FileBrowserDialog.vue'
import { api } from '@/api/client'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('FileBrowserDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads initial path when show=true', async () => {
    const mockResponse = {
      current_path: '/media',
      parent_path: null,
      entries: [
        { name: 'Videos', path: '/media/Videos', is_dir: true, size: null, modified_at: null },
        { name: 'movie.mkv', path: '/media/movie.mkv', is_dir: false, size: 1024000, modified_at: '2026-01-01' },
      ],
    }
    ;(api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockResponse)

    const wrapper = mount(FileBrowserDialog, {
      props: { show: false, initialPath: '/media' },
      global: {
        plugins: [createPinia()],
        stubs: {
          'n-modal': NModal,
          'n-spin': NSpin,
          'n-space': NSpace,
          'n-breadcrumb': NBreadcrumb,
          'n-breadcrumb-item': NBreadcrumbItem,
          'n-list': NList,
          'n-list-item': NListItem,
          'n-button': NButton,
          'n-text': NText,
        },
      },
    })

    await wrapper.vm.$nextTick()
    await wrapper.setProps({ show: true })
    await wrapper.vm.$nextTick()
    expect(api.post).toHaveBeenCalledWith('/files/browse', { path: '/media' })
  })

  it('emits select with file path when file clicked', async () => {
    const mockResponse = {
      current_path: '/media',
      parent_path: null,
      entries: [
        { name: 'movie.mkv', path: '/media/movie.mkv', is_dir: false, size: 1024000, modified_at: '2026-01-01' },
      ],
    }
    ;(api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockResponse)

    const wrapper = mount(FileBrowserDialog, {
      props: { show: false },
      global: {
        plugins: [createPinia()],
        stubs: {
          'n-modal': NModal,
          'n-spin': NSpin,
          'n-space': NSpace,
          'n-breadcrumb': NBreadcrumb,
          'n-breadcrumb-item': NBreadcrumbItem,
          'n-list': NList,
          'n-list-item': NListItem,
          'n-button': NButton,
          'n-text': NText,
        },
      },
    })

    await wrapper.setProps({ show: true })
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const listItems = wrapper.findAllComponents(NListItem)
    expect(listItems.length).toBeGreaterThan(0)
  })
})
