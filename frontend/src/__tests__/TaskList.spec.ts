import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import {
  NCard,
  NSelect,
  NButton,
  NSpace,
  NDataTable,
  NTag,
  NPopconfirm,
  NPagination,
} from 'naive-ui'
import TaskList from '@/views/TaskList.vue'
import { useTasksStore, type Task } from '@/stores/tasks'
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

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

describe('TaskList', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  function createMockTask(overrides: Partial<Task> = {}): Task {
    return {
      id: 1,
      status: 'staged',
      series_id: 1,
      series_name: '测试剧集',
      emby_series_id: 'emby-1',
      library_id: 1,
      library_name: '测试库',
      season_number: 1,
      episode_number: 1,
      title: '测试标题',
      source_file_path: '/source/test.mkv',
      staging_video_path: '/staging/test.mkv',
      staging_nfo_path: null,
      staging_cover_path: null,
      target_video_path: '/target/test.mkv',
      target_nfo_path: null,
      target_cover_path: null,
      nfo_json: null,
      error_message: null,
      committed_at: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      ...overrides,
    }
  }

  async function mountList() {
    (api.get as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce([createMockTask()])
      .mockResolvedValueOnce([
        {
          id: 1,
          name: '测试剧集',
          emby_series_id: 'emby-1',
          library_id: 1,
          library_name: '测试库',
          staging_path: '/staging',
          target_path: '/target',
          default_season: 1,
          enabled: true,
          created_at: '2026-01-01',
          updated_at: '2026-01-01',
        },
      ])

    const wrapper = mount(TaskList, {
      global: {
        plugins: [createPinia()],
        stubs: {
          'n-card': NCard,
          'n-select': NSelect,
          'n-button': NButton,
          'n-space': NSpace,
          'n-data-table': NDataTable,
          'n-tag': NTag,
          'n-popconfirm': NPopconfirm,
          'n-pagination': NPagination,
        },
      },
    })

    await nextTick()
    await nextTick()
    return wrapper
  }

  it('loads tasks on mount', async () => {
    await mountList()
    const store = useTasksStore()
    expect(store.tasks.length).toBe(1)
  })

  it('filtering by status triggers loadTasks with selected status', async () => {
    (api.get as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce([createMockTask()])
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([])

    const wrapper = mount(TaskList, {
      global: {
        plugins: [createPinia()],
        stubs: {
          'n-card': NCard,
          'n-select': NSelect,
          'n-button': NButton,
          'n-space': NSpace,
          'n-data-table': NDataTable,
          'n-tag': NTag,
          'n-popconfirm': NPopconfirm,
          'n-pagination': NPagination,
        },
      },
    })

    await nextTick()
    await nextTick()

    const selects = wrapper.findAllComponents(NSelect)
    const statusSelect = selects[0]
    await statusSelect.vm.$emit('update:value', 'committed')
    await nextTick()

    expect(api.get).toHaveBeenCalledWith('/tasks?status=committed')
  })
})
