<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import {
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
  useMessage,
  NGrid,
  NGridItem,
  NFormItemGi,
  NSpin
} from 'naive-ui'
import { useSeriesStore } from '@/stores/series'
import { useTasksStore } from '@/stores/tasks'
import FileBrowserDialog from '@/components/FileBrowserDialog.vue'
import TaskPreview from '@/components/TaskPreview.vue'

const message = useMessage()
const seriesStore = useSeriesStore()
const tasksStore = useTasksStore()

const form = ref({
  series_id: null as number | null,
  season_number: 1,
  episode_number: 1,
  title: '',
  source_file_path: '',
  cover_url: ''
})

const showFileBrowser = ref(false)
const loadingPreview = ref(false)
const creatingTask = ref(false)
const titleManuallyEdited = ref(false)
const duplicateTaskMessage = '该剧集季×集已存在任务，请删除原任务后重试'

onMounted(async () => {
  await seriesStore.loadSeries()
})

const seriesOptions = computed(() => {
  return seriesStore.series
    .filter(s => s.enabled)
    .map(s => ({
      label: s.name,
      value: s.id
    }))
})

const seasonOptions = computed(() => {
  return seriesStore.seasons.map(s => ({
    label: s.Name || `Season ${s.IndexNumber}`,
    value: s.IndexNumber
  }))
})

watch(() => form.value.series_id, async (newId) => {
  if (!newId) return
  const series = seriesStore.series.find(s => s.id === newId)
  if (series?.emby_series_id) {
    await seriesStore.loadSeasons(series.emby_series_id)
    form.value.season_number = series.default_season
  }
})

watch(() => [form.value.series_id, form.value.season_number], async ([newId, newSeason]) => {
  if (!newId || !newSeason) return
  const series = seriesStore.series.find(s => s.id === newId)
  if (series?.emby_series_id) {
    const latest = await seriesStore.loadLatestEpisode(series.emby_series_id, newSeason as number)
    if (latest) {
      form.value.episode_number = latest.next_episode
    }
  }
})

const handleFileSelect = (path: string) => {
  form.value.source_file_path = path
  // 从文件名推导默认标题
  const filename = path.split(/[/\\]/).pop() || ''
  const title = filename.substring(0, filename.lastIndexOf('.')) || filename
  if (!titleManuallyEdited.value || !form.value.title) {
    form.value.title = title
  }
}

const updatePreview = async () => {
  if (!form.value.series_id || !form.value.source_file_path || !form.value.title) return
  loadingPreview.value = true
  await tasksStore.previewTask({
    series_id: form.value.series_id,
    season_number: form.value.season_number,
    episode_number: form.value.episode_number,
    title: form.value.title,
    source_file_path: form.value.source_file_path,
    cover_url: form.value.cover_url || null
  })
  loadingPreview.value = false
}

watch(() => [
  form.value.series_id,
  form.value.season_number,
  form.value.episode_number,
  form.value.title,
  form.value.source_file_path,
  form.value.cover_url
], () => {
  updatePreview()
}, { deep: true })

const handleCreate = async () => {
  if (!form.value.series_id || !form.value.source_file_path || !form.value.title) {
    message.error('请填写完整表单')
    return
  }
  creatingTask.value = true
  const task = await tasksStore.createTask({
    series_id: form.value.series_id,
    season_number: form.value.season_number,
    episode_number: form.value.episode_number,
    title: form.value.title,
    source_file_path: form.value.source_file_path,
    cover_url: form.value.cover_url || null,
    nfo_json: { title: form.value.title }
  })
  creatingTask.value = false
  if (task) {
    message.success('任务创建成功')
    await tasksStore.loadTasks()
    form.value.season_number = 1
    form.value.episode_number = 1
    form.value.title = ''
    form.value.source_file_path = ''
    form.value.cover_url = ''
    titleManuallyEdited.value = false
    tasksStore.preview = null
  } else {
    message.error(tasksStore.error === 'DUPLICATE_TASK' ? duplicateTaskMessage : tasksStore.error || '创建失败')
  }
}
</script>

<template>
  <div class="organize-page">
    <n-grid
      :cols="24"
      :x-gap="16"
    >
      <n-grid-item :span="14">
        <n-card title="整理新分集">
          <n-form
            :model="form"
            label-placement="left"
            label-width="100"
          >
            <n-form-item
              label="选择剧集"
              required
            >
              <n-select
                v-model:value="form.series_id"
                :options="seriesOptions"
                placeholder="选择已配置的剧集"
                filterable
              />
            </n-form-item>

            <n-grid
              :cols="2"
              :x-gap="12"
            >
              <n-form-item-gi
                label="季"
                required
              >
                <n-select
                  v-model:value="form.season_number"
                  :options="seasonOptions"
                  placeholder="选择季"
                />
              </n-form-item-gi>
              <n-form-item-gi
                label="集号"
                required
              >
                <n-input-number
                  v-model:value="form.episode_number"
                  :min="1"
                />
              </n-form-item-gi>
            </n-grid>

            <n-form-item
              label="源视频"
              required
            >
              <n-input
                v-model:value="form.source_file_path"
                placeholder="选择服务器上的视频文件"
                readonly
                @click="showFileBrowser = true"
              >
                <template #suffix>
                  <n-button
                    size="small"
                    type="primary"
                    @click.stop="showFileBrowser = true"
                  >
                    浏览
                  </n-button>
                </template>
              </n-input>
            </n-form-item>

            <n-form-item
              label="标题"
              required
            >
              <n-input
                v-model:value="form.title"
                placeholder="分集标题"
                @update:value="titleManuallyEdited = true"
              />
            </n-form-item>

            <n-form-item label="封面">
              <n-tabs
                type="line"
                animated
              >
                <n-tab-pane
                  name="url"
                  tab="图片 URL"
                >
                  <n-input
                    v-model:value="form.cover_url"
                    placeholder="https://..."
                  />
                </n-tab-pane>
                <n-tab-pane
                  name="upload"
                  tab="本地上传"
                >
                  <div style="padding: 12px; border: 1px dashed #ccc; text-align: center;">
                    UI 占位：本地上传将在后续任务实现
                  </div>
                </n-tab-pane>
              </n-tabs>
            </n-form-item>

            <n-space justify="end">
              <n-button
                type="primary"
                size="large"
                :loading="creatingTask"
                :disabled="!form.series_id || !form.source_file_path || !form.title"
                @click="handleCreate"
              >
                创建整理任务
              </n-button>
            </n-space>
          </n-form>
        </n-card>
      </n-grid-item>

      <n-grid-item :span="10">
        <n-spin :show="loadingPreview">
          <task-preview :preview="tasksStore.preview" />
        </n-spin>
      </n-grid-item>
    </n-grid>

    <file-browser-dialog
      v-model:show="showFileBrowser"
      @select="handleFileSelect"
    />
  </div>
</template>

<style scoped>
.organize-page {
  padding: 16px;
}
</style>
