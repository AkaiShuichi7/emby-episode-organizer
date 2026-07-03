/* global describe, it, expect, beforeEach */

import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import {
  NConfigProvider,
  NDialogProvider,
  NMessageProvider,
  NSpin,
  NCard,
  NTable,
  NTag,
  NText,
} from 'naive-ui'
import TaskPreview from '@/components/TaskPreview.vue'
import type { TaskPreview as TaskPreviewType } from '@/stores/tasks'

const mountComponent = (preview: TaskPreviewType | null = null) => {
  return mount(TaskPreview, {
    props: { preview },
    global: {
      plugins: [createPinia()],
      components: { NConfigProvider, NDialogProvider, NMessageProvider, NSpin, NCard, NTable, NTag, NText },
      stubs: {
        'n-config-provider': NConfigProvider,
        'n-dialog-provider': NDialogProvider,
        'n-message-provider': NMessageProvider,
        'n-spin': NSpin,
        'n-card': NCard,
        'n-table': NTable,
        'n-tag': NTag,
        'n-text': NText,
      },
    },
  })
}

describe('TaskPreview', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders 4+ path rows from preview', () => {
    const preview: TaskPreviewType = {
      series_id: 1,
      season_number: 1,
      episode_number: 5,
      title: 'Test Episode',
      source_file_path: '/source/Test.mkv',
      staging_video_path: '/staging/Test - S01E05 - Test Episode.mkv',
      staging_nfo_path: '/staging/Test - S01E05 - Test Episode.nfo',
      staging_cover_path: '/staging/Test - S01E05 - Test Episode-thumb.jpg',
      target_video_path: '/target/Season 01/Test - S01E05 - Test Episode.mkv',
      target_nfo_path: '/target/Season 01/Test - S01E05 - Test Episode.nfo',
      target_cover_path: '/target/Season 01/Test - S01E05 - Test Episode-thumb.jpg',
    }

    const wrapper = mountComponent(preview)
    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBeGreaterThanOrEqual(4)
  })

  it('shows placeholder text when no preview', () => {
    const wrapper = mountComponent(null)
    expect(wrapper.findComponent(NText).exists()).toBe(true)
  })
})
