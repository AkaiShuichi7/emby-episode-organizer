import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SeriesConfig from '@/views/SeriesConfig.vue'

const mocks = vi.hoisted(() => ({
  loadSeries: vi.fn(),
  loadEmbySeries: vi.fn(),
  createSeriesConfig: vi.fn(),
  updateSeriesConfig: vi.fn(),
  loadLibraries: vi.fn(),
  apiDelete: vi.fn()
}))

vi.mock('@/stores/series', () => ({
  useSeriesStore: () => ({
    series: [],
    embySearchResults: [],
    loading: false,
    error: null,
    loadSeries: mocks.loadSeries,
    loadEmbySeries: mocks.loadEmbySeries,
    createSeriesConfig: mocks.createSeriesConfig,
    updateSeriesConfig: mocks.updateSeriesConfig
  })
}))

vi.mock('@/stores/libraries', () => {
  const libraries: Array<{ id: number; name: string; staging_root?: string; target_root?: string; enabled?: boolean }> = []
  return {
    useLibrariesStore: () => ({
      libraries,
      loading: false,
      error: null,
      loadLibraries: async () => {
        const data = await mocks.loadLibraries()
        libraries.splice(0, libraries.length, ...data)
        return data
      }
    })
  }
})

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: mocks.apiDelete
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

describe('SeriesConfig.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.loadSeries.mockResolvedValue([])
    mocks.loadEmbySeries.mockResolvedValue([])
    mocks.loadLibraries.mockResolvedValue([])
    mocks.createSeriesConfig.mockResolvedValue({ id: 1 })
  })

  it('renders search bar and configured series list', async () => {
    const wrapper = mount(SeriesConfig, {
      global: {
        stubs: {
          'n-card': { template: '<div><slot /></div>' },
          'n-data-table': { template: '<div />' },
          'n-modal': { template: '<div><slot /></div>' },
          'n-form': { template: '<form><slot /></form>' },
          'n-form-item': { template: '<div><slot /></div>' },
          'n-input': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['modelValue']
          },
          'n-input-number': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', Number($event.target.value))" />',
            props: ['modelValue', 'min']
          },
          'n-select': {
            props: ['options', 'value'],
            template:
              '<select :value="value" @change="$emit(\'update:value\', Number($event.target.value))">' +
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

    expect(wrapper.find('.series-config').exists()).toBe(true)
    expect(mocks.loadSeries).toHaveBeenCalled()
    expect(mocks.loadLibraries).toHaveBeenCalled()
  })

  it('search calls loadEmbySeries with keyword', async () => {
    const wrapper = mount(SeriesConfig, {
      global: {
        stubs: {
          'n-card': { template: '<div><slot /></div>' },
          'n-data-table': { template: '<div />' },
          'n-modal': { template: '<div><slot /></div>' },
          'n-form': { template: '<form><slot /></form>' },
          'n-form-item': { template: '<div><slot /></div>' },
          'n-input': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['modelValue']
          },
          'n-input-number': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', Number($event.target.value))" />',
            props: ['modelValue', 'min']
          },
          'n-select': {
            props: ['options', 'value'],
            template:
              '<select :value="value" @change="$emit(\'update:value\', Number($event.target.value))">' +
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

    const vm = wrapper.vm as unknown as { keyword: string; handleSearch: () => Promise<void> }
    vm.keyword = 'test series'

    await vm.handleSearch()

    expect(mocks.loadEmbySeries).toHaveBeenCalledWith('test series')
  })

  it('openAddModal autofills form from EmbySeries row', async () => {
    const wrapper = mount(SeriesConfig, {
      global: {
        stubs: {
          'n-card': { template: '<div><slot /></div>' },
          'n-data-table': { template: '<div />' },
          'n-modal': { template: '<div><slot /></div>' },
          'n-form': { template: '<form><slot /></form>' },
          'n-form-item': { template: '<div><slot /></div>' },
          'n-input': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['modelValue']
          },
          'n-input-number': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', Number($event.target.value))" />',
            props: ['modelValue', 'min']
          },
          'n-select': {
            props: ['options', 'value'],
            template:
              '<select :value="value" @change="$emit(\'update:value\', Number($event.target.value))">' +
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

    const vm = wrapper.vm as unknown as {
      openAddModal: (row: { Id?: string; Name?: string }) => void
      addForm: {
        name: string
        emby_series_id: string
        library_id: number | null
        staging_path: string
        target_path: string
        default_season: number
        enabled: boolean
      }
      showAddModal: boolean
    }

    vm.openAddModal({ Id: 'emby-123', Name: 'Test Series' })

    expect(vm.addForm.name).toBe('Test Series')
    expect(vm.addForm.emby_series_id).toBe('emby-123')
    expect(vm.addForm.library_id).toBeNull()
    expect(vm.addForm.staging_path).toBe('')
    expect(vm.addForm.target_path).toBe('')
    expect(vm.addForm.default_season).toBe(1)
    expect(vm.addForm.enabled).toBe(true)
    expect(vm.showAddModal).toBe(true)
  })

  it('handleLibraryChange autofills paths from library roots', async () => {
    mocks.loadLibraries.mockResolvedValue([
      { id: 1, name: '动画', staging_root: '/data/staging', target_root: '/data/target', enabled: true }
    ])

    const wrapper = mount(SeriesConfig, {
      global: {
        stubs: {
          'n-card': { template: '<div><slot /></div>' },
          'n-data-table': { template: '<div />' },
          'n-modal': { template: '<div><slot /></div>' },
          'n-form': { template: '<form><slot /></form>' },
          'n-form-item': { template: '<div><slot /></div>' },
          'n-input': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['modelValue']
          },
          'n-input-number': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', Number($event.target.value))" />',
            props: ['modelValue', 'min']
          },
          'n-select': {
            props: ['options', 'value'],
            template:
              '<select :value="value" @change="$emit(\'update:value\', Number($event.target.value))">' +
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

    const vm = wrapper.vm as unknown as {
      handleLibraryChange: (libraryId: number | null, form: { name: string; staging_path: string; target_path: string }) => void
      addForm: { name: string; staging_path: string; target_path: string }
    }

    vm.addForm.name = 'Test Series'
    vm.handleLibraryChange(1, vm.addForm)

    expect(vm.addForm.staging_path).toBe('/data/staging/Test_Series')
    expect(vm.addForm.target_path).toBe('/data/target/Test_Series')
  })

  it('submitAdd creates series config and refreshes list', async () => {
    const wrapper = mount(SeriesConfig, {
      global: {
        stubs: {
          'n-card': { template: '<div><slot /></div>' },
          'n-data-table': { template: '<div />' },
          'n-modal': { template: '<div><slot /></div>' },
          'n-form': { template: '<form><slot /></form>' },
          'n-form-item': { template: '<div><slot /></div>' },
          'n-input': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['modelValue']
          },
          'n-input-number': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', Number($event.target.value))" />',
            props: ['modelValue', 'min']
          },
          'n-select': {
            props: ['options', 'value'],
            template:
              '<select :value="value" @change="$emit(\'update:value\', Number($event.target.value))">' +
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

    const vm = wrapper.vm as unknown as {
      addForm: {
        name: string
        emby_series_id: string
        library_id: number
        staging_path: string
        target_path: string
        default_season: number
        enabled: boolean
      }
      showAddModal: boolean
      submitAdd: () => Promise<void>
    }

    vm.addForm = {
      name: 'Test Series',
      emby_series_id: 'emby-123',
      library_id: 1,
      staging_path: '/data/staging/Test_Series',
      target_path: '/data/target/Test_Series',
      default_season: 1,
      enabled: true
    }

    await vm.submitAdd()

    expect(mocks.createSeriesConfig).toHaveBeenCalledWith({
      name: 'Test Series',
      emby_series_id: 'emby-123',
      library_id: 1,
      staging_path: '/data/staging/Test_Series',
      target_path: '/data/target/Test_Series',
      default_season: 1,
      enabled: true
    })
    expect(mocks.loadSeries).toHaveBeenCalled()
    expect(vm.showAddModal).toBe(false)
  })

  it('toggleEnabled updates series enabled state', async () => {
    mocks.loadSeries.mockResolvedValue([
      { id: 1, name: 'Test', enabled: true, library_id: 1, emby_series_id: 'emby-1' }
    ])
    mocks.updateSeriesConfig.mockResolvedValue({ id: 1, name: 'Test', enabled: false, library_id: 1, emby_series_id: 'emby-1' })

    const wrapper = mount(SeriesConfig, {
      global: {
        stubs: {
          'n-card': { template: '<div><slot /></div>' },
          'n-data-table': { template: '<div />' },
          'n-modal': { template: '<div><slot /></div>' },
          'n-form': { template: '<form><slot /></form>' },
          'n-form-item': { template: '<div><slot /></div>' },
          'n-input': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['modelValue']
          },
          'n-input-number': {
            template: '<input :value="modelValue" @input="$emit(\'update:value\', Number($event.target.value))" />',
            props: ['modelValue', 'min']
          },
          'n-select': {
            props: ['options', 'value'],
            template:
              '<select :value="value" @change="$emit(\'update:value\', Number($event.target.value))">' +
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

    const vm = wrapper.vm as unknown as {
      toggleEnabled: (row: { id: number; enabled: boolean }) => Promise<void>
    }

    await vm.toggleEnabled({ id: 1, enabled: true })

    expect(mocks.updateSeriesConfig).toHaveBeenCalledWith(1, { enabled: false })
    expect(mocks.loadSeries).toHaveBeenCalled()
  })
})