import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CoverManager from '@/components/CoverManager.vue'

const mocks = vi.hoisted(() => ({
  uploadCover: vi.fn(),
  downloadCover: vi.fn(),
}))

vi.mock('@/stores/tasks', () => ({
  useTasksStore: () => ({
    uploadCover: mocks.uploadCover,
    downloadCover: mocks.downloadCover,
    loading: false,
    error: null,
  }),
}))

const messageMocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
}))

vi.mock('naive-ui', async () => {
  const actual = await vi.importActual('naive-ui')
  return {
    ...actual,
    useMessage: () => messageMocks,
  }
})

const baseTask = {
  id: 1,
  status: 'staged',
  series_id: 1,
  series_name: '测试剧集',
  emby_series_id: null,
  library_id: 1,
  library_name: '动漫',
  season_number: 1,
  episode_number: 1,
  title: '测试集',
  source_file_path: '/source.mkv',
  staging_video_path: '/staging.mkv',
  staging_nfo_path: '/staging.nfo',
  staging_cover_path: null,
  target_video_path: '/target.mkv',
  target_nfo_path: '/target.nfo',
  target_cover_path: null,
  nfo_json: null,
  error_message: null,
  committed_at: null,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
}

function mountComponent(task: typeof baseTask) {
  return mount(CoverManager, {
    props: { task },
    global: {
      stubs: {
        'n-card': { template: '<div><slot /></div>' },
        'n-tabs': { template: '<div><slot /></div>' },
        'n-tab-pane': { template: '<div><slot /></div>' },
        'n-image': { template: '<img :src="src" />', props: ['src'] },
        'n-upload': { template: '<div><slot /></div>' },
        'n-input': {
          template: '<input :value="modelValue" @input="$emit(\'update:value\', $event.target.value)" />',
          props: ['modelValue'],
        },
        'n-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        'n-space': { template: '<div><slot /></div>' },
        'n-text': { template: '<span><slot /></span>' },
      },
    },
  })
}

describe('CoverManager.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.uploadCover.mockResolvedValue({ ...baseTask, staging_cover_path: '/staging-thumb.jpg' })
    mocks.downloadCover.mockResolvedValue({ ...baseTask, staging_cover_path: '/staging-thumb.jpg' })
  })

  it('shows empty state when no cover path is set', () => {
    const wrapper = mountComponent(baseTask)
    expect(wrapper.text()).toContain('暂无封面')
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('shows local cover when staging_cover_path exists', () => {
    const task = { ...baseTask, staging_cover_path: '/staging-thumb.jpg' }
    const wrapper = mountComponent(task)
    const img = wrapper.find('img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('/api/v1/tasks/1/cover/raw')
    expect(wrapper.text()).toContain('staging-thumb.jpg')
    expect(wrapper.text()).toContain('类型: image/jpeg')
  })

  it('shows target cover when target_cover_path exists', () => {
    const task = { ...baseTask, target_cover_path: '/target-thumb.png' }
    const wrapper = mountComponent(task)
    expect(wrapper.find('img').exists()).toBe(true)
    expect(wrapper.text()).toContain('target-thumb.png')
    expect(wrapper.text()).toContain('类型: image/png')
  })

  it('uploads cover when file selected', async () => {
    const file = new File(['jpeg'], 'cover.jpg', { type: 'image/jpeg' })
    const wrapper = mountComponent(baseTask)

    await (wrapper.vm as unknown as { handleUploadChange: (data: { file: { file: File } }) => Promise<void> })
      .handleUploadChange({ file: { file } })
    await flushPromises()

    expect(mocks.uploadCover).toHaveBeenCalledWith(1, file)
    expect(messageMocks.success).toHaveBeenCalledWith('封面上传成功')
  })

  it('downloads cover from URL when button clicked', async () => {
    const wrapper = mountComponent(baseTask)
    const vm = wrapper.vm as unknown as { coverUrlInput: string; handleDownloadCover: () => Promise<void> }
    vm.coverUrlInput = 'https://example.com/cover.jpg'

    await vm.handleDownloadCover()
    await flushPromises()

    expect(mocks.downloadCover).toHaveBeenCalledWith(1, 'https://example.com/cover.jpg')
    expect(messageMocks.success).toHaveBeenCalledWith('封面下载成功')
    expect(vm.coverUrlInput).toBe('')
  })

  it('warns when downloading with empty URL', async () => {
    const wrapper = mountComponent(baseTask)
    const vm = wrapper.vm as unknown as { coverUrlInput: string; handleDownloadCover: () => Promise<void> }
    vm.coverUrlInput = '   '

    await vm.handleDownloadCover()
    await flushPromises()

    expect(mocks.downloadCover).not.toHaveBeenCalled()
    expect(messageMocks.warning).toHaveBeenCalledWith('请输入封面图片 URL')
  })

  it('emits updated event after upload', async () => {
    const updated = { ...baseTask, staging_cover_path: '/staging-thumb.jpg' }
    mocks.uploadCover.mockResolvedValue(updated)
    const wrapper = mountComponent(baseTask)

    const file = new File(['jpeg'], 'cover.jpg', { type: 'image/jpeg' })
    await (wrapper.vm as unknown as { handleUploadChange: (data: { file: { file: File } }) => Promise<void> })
      .handleUploadChange({ file: { file } })
    await flushPromises()

    expect(wrapper.emitted('updated')).toHaveLength(1)
    expect(wrapper.emitted('updated')?.[0]).toEqual([updated])
  })
})
