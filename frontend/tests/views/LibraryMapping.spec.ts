import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import LibraryMapping from '@/views/LibraryMapping.vue'

const mocks = vi.hoisted(() => ({
  loadLibraries: vi.fn(),
  createLibrary: vi.fn(),
  updateLibrary: vi.fn(),
  deleteLibrary: vi.fn(),
  apiGet: vi.fn()
}))

vi.mock('@/stores/libraries', () => ({
  useLibrariesStore: () => ({
    libraries: [],
    loading: false,
    error: null,
    loadLibraries: mocks.loadLibraries,
    createLibrary: mocks.createLibrary,
    updateLibrary: mocks.updateLibrary,
    deleteLibrary: mocks.deleteLibrary
  })
}))

vi.mock('@/api/client', () => ({
  api: {
    get: mocks.apiGet,
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

vi.mock('naive-ui', async () => {
  const actual = await vi.importActual('naive-ui')
  return {
    ...actual,
    useMessage: () => ({
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn()
    })
  }
})

describe('LibraryMapping.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.loadLibraries.mockResolvedValue([])
    mocks.apiGet.mockResolvedValue([{ ItemId: 'emby-1', Name: '动画', CollectionType: 'tvshows' }])
    mocks.createLibrary.mockResolvedValue({ id: 1 })
  })

  it('refresh populates select and submit sends selected library name', async () => {
    const wrapper = mount(LibraryMapping, {
      global: {
        stubs: {
          'n-card': { template: '<div><slot name="header-extra" /><slot /></div>' },
          'n-data-table': true,
          'n-modal': { template: '<div><slot /></div>' },
          'n-form': { template: '<form><slot /></form>' },
          'n-form-item': { template: '<div><slot /></div>' },
          'n-input': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['modelValue']
          },
          'n-select': {
            props: ['options', 'value'],
            template:
              '<select :value="value" @change="$emit(\'update:value\', $event.target.value)">' +
              '<option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>' +
              '</select>'
          },
          'n-switch': {
            props: ['value'],
            template: '<input type="checkbox" :checked="value" @change="$emit(\'update:value\', $event.target.checked)" />'
          },
          'n-space': { template: '<div><slot /><slot name="default" /></div>' },
          'n-popconfirm': { template: '<div><slot name="trigger" /><slot /></div>' },
          'n-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>'
          }
        }
      }
    })

    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('刷新 Emby 媒体库'))?.trigger('click')
    await flushPromises()

    expect(mocks.apiGet).toHaveBeenCalledWith('/emby/libraries')

    await wrapper.findAll('button').find((button) => button.text().includes('添加映射'))?.trigger('click')
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      libraryOptions: Array<{ label: string; value: string }>
      handleSubmit: () => Promise<void>
      formData: {
        name: string
        staging_root: string
        target_root: string
        enabled: boolean
      }
    }

    expect(vm.libraryOptions).toEqual([{ label: '动画', value: '动画' }])

    vm.formData.name = '动画'
    vm.formData.staging_root = '/data/downloads/anime'
    vm.formData.target_root = '/data/media/anime'
    vm.formData.enabled = true

    await vm.handleSubmit()

    expect(mocks.createLibrary).toHaveBeenCalledWith({
      name: '动画',
      staging_root: '/data/downloads/anime',
      target_root: '/data/media/anime',
      enabled: true,
      collection_type: 'tvshows'
    })
  })
})
