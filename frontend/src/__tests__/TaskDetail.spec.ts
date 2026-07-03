import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import {
  NCard,
  NButton,
  NSpace,
  NTag,
  NImage,
  NPopconfirm,
  NDescriptions,
  NDescriptionsItem,
  NSpin,
  NDivider,
  NUpload,
  NTooltip,
} from 'naive-ui'
import TaskDetail from '@/views/TaskDetail.vue'
import NFOEditor from '@/components/NFOEditor.vue'
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
  const actual = await vi.importActual<typeof import('naive-ui')>('naive-ui')
  return {
    ...actual,
    useMessage: () => mockMessage,
  }
})

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { id: '42' },
  }),
  useRouter: () => ({
    push: mockPush,
  }),
}))

describe('TaskDetail', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  function createMockTask(overrides: Partial<Task> = {}): Task {
    return {
      id: 42,
      status: 'staged',
      series_id: 1,
      series_name: '测试剧集',
      emby_series_id: 'emby-1',
      library_id: 1,
      library_name: '测试库',
      season_number: 1,
      episode_number: 5,
      title: '测试标题',
      source_file_path: '/source/test.mkv',
      staging_video_path: '/staging/test.mkv',
      staging_nfo_path: '/staging/test.nfo',
      staging_cover_path: '/staging/test-thumb.jpg',
      target_video_path: '/target/test.mkv',
      target_nfo_path: '/target/test.nfo',
      target_cover_path: '/target/test-thumb.jpg',
      nfo_json: { title: '原标题', plot: '原剧情' },
      error_message: null,
      committed_at: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      ...overrides,
    }
  }

  async function mountDetail() {
    const mockTask = createMockTask()
    ;(api.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockTask)

    const wrapper = mount(TaskDetail, {
      global: {
        plugins: [createPinia()],
        stubs: {
          'n-card': NCard,
          'n-button': NButton,
          'n-space': NSpace,
          'n-tag': NTag,
          'n-image': NImage,
          'n-popconfirm': NPopconfirm,
          'n-grid': true,
          'n-grid-item': true,
          'n-descriptions': NDescriptions,
          'n-descriptions-item': NDescriptionsItem,
          'n-spin': NSpin,
          'n-divider': NDivider,
          'n-upload': NUpload,
          'n-tooltip': NTooltip,
          'n-f-o-editor': NFOEditor,
        },
      },
    })

    await nextTick()
    await nextTick()
    return wrapper
  }

  it('loads task on mount', async () => {
    await mountDetail()
    expect(api.get).toHaveBeenCalledWith('/tasks/42')
  })

  it('saving NFO calls updateNFO and shows success message', async () => {
    const updatedTask = createMockTask({
      nfo_json: { title: '新标题', plot: '新剧情' },
    })
    ;(api.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(createMockTask())
    ;(api.put as ReturnType<typeof vi.fn>).mockResolvedValueOnce(updatedTask)

    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useTasksStore()
    const updateSpy = vi.spyOn(store, 'updateNFO')

    const wrapper = mount(TaskDetail, {
      global: {
        plugins: [pinia],
        stubs: {
          'n-card': NCard,
          'n-button': NButton,
          'n-space': NSpace,
          'n-tag': NTag,
          'n-image': NImage,
          'n-popconfirm': NPopconfirm,
          'n-grid': true,
          'n-grid-item': true,
          'n-descriptions': NDescriptions,
          'n-descriptions-item': NDescriptionsItem,
          'n-spin': NSpin,
          'n-divider': NDivider,
          'n-upload': NUpload,
          'n-tooltip': NTooltip,
          'n-f-o-editor': NFOEditor,
        },
      },
    })

    await nextTick()
    await nextTick()

    const editor = wrapper.findComponent(NFOEditor)
    await editor.vm.$emit('save', { title: '新标题', plot: '新剧情' })

    await new Promise((resolve) => setTimeout(resolve, 100))

    expect(updateSpy).toHaveBeenCalledWith(42, { title: '新标题', plot: '新剧情' })
    expect(mockMessage.success).toHaveBeenCalledWith('NFO 保存成功')
  })
})
