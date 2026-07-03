import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import {
  NCard,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NButton,
  NSpace,
  NDynamicInput,
} from 'naive-ui'
import NFOEditor from '@/components/NFOEditor.vue'

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

describe('NFOEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  function mountComponent(props = {}) {
    return mount(NFOEditor, {
      props: {
        modelValue: null,
        ...props,
      },
      global: {
        stubs: {
          'n-card': NCard,
          'n-form': NForm,
          'n-form-item': NFormItem,
          'n-input': NInput,
          'n-input-number': NInputNumber,
          'n-button': NButton,
          'n-space': NSpace,
          'n-dynamic-input': NDynamicInput,
        },
      },
    })
  }

  it('renders NFO fields from modelValue', async () => {
    const wrapper = mountComponent({
      modelValue: {
        title: '测试标题',
        plot: '测试剧情',
        premiered: '2026-01-01',
        year: 2026,
        genre: '剧情',
        tag: '热门',
        director: '导演',
        studio: '工作室',
        rating: 8.5,
      },
    })
    await nextTick()

    const inputs = wrapper.findAllComponents(NInput)
    expect(inputs.length).toBeGreaterThan(0)
    expect(inputs[0].props('value')).toBe('测试标题')
  })

  it('emits save with edited data when save button clicked', async () => {
    const wrapper = mountComponent({
      modelValue: { title: '原标题', plot: '原剧情' },
    })
    await nextTick()

    const inputs = wrapper.findAllComponents(NInput)
    const titleInput = inputs[0]
    await titleInput.vm.$emit('update:value', '新标题')
    await nextTick()

    const saveButton = wrapper.findAllComponents(NButton).find((btn) =>
      btn.text().includes('保存')
    )
    expect(saveButton).toBeDefined()
    await saveButton?.trigger('click')

    const saveEvents = wrapper.emitted('save')
    expect(saveEvents).toHaveLength(1)
    const payload = saveEvents?.[0]?.[0] as Record<string, unknown>
    expect(payload.title).toBe('新标题')
    expect(payload.plot).toBe('原剧情')
  })
})
