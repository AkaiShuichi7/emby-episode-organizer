<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  NCard,
  NTabs,
  NTabPane,
  NImage,
  NUpload,
  NInput,
  NButton,
  NSpace,
  NText,
  useMessage,
} from 'naive-ui'
import type { UploadFileInfo } from 'naive-ui'
import { useTasksStore, type Task } from '@/stores/tasks'

const props = defineProps<{
  task: Task
}>()

const emit = defineEmits<{
  (e: 'updated', value: Task): void
}>()

const tasksStore = useTasksStore()
const message = useMessage()

const coverUrl = computed(() => {
  if (props.task.staging_cover_path || props.task.target_cover_path) {
    return `/api/v1/tasks/${props.task.id}/cover/raw`
  }
  return undefined
})

const coverInfo = computed(() => {
  const path = props.task.staging_cover_path || props.task.target_cover_path
  if (!path) return null
  return {
    name: path.split('/').pop() || path.split('\\').pop() || '',
    contentType: guessContentType(path),
  }
})

const coverUrlInput = ref('')

function guessContentType(path: string): string {
  if (path.toLowerCase().endsWith('.png')) return 'image/png'
  if (path.toLowerCase().endsWith('.jpg') || path.toLowerCase().endsWith('.jpeg')) return 'image/jpeg'
  if (path.toLowerCase().endsWith('.webp')) return 'image/webp'
  return '未知'
}

async function handleUploadChange(data: { file: UploadFileInfo }) {
  const file = data.file.file
  if (!file) return

  const updated = await tasksStore.uploadCover(props.task.id, file)
  if (updated) {
    message.success('封面上传成功')
    emit('updated', updated)
  } else {
    message.error(tasksStore.error || '封面上传失败')
  }
}

async function handleDownloadCover() {
  const url = coverUrlInput.value.trim()
  if (!url) {
    message.warning('请输入封面图片 URL')
    return
  }

  const updated = await tasksStore.downloadCover(props.task.id, url)
  if (updated) {
    message.success('封面下载成功')
    coverUrlInput.value = ''
    emit('updated', updated)
  } else {
    message.error(tasksStore.error || '封面下载失败')
  }
}
</script>

<template>
  <n-card
    title="封面"
    :segmented="{ content: true }"
  >
    <div v-if="coverUrl">
      <n-image
        :src="coverUrl"
        style="width: 100%; border-radius: 4px;"
      />
      <div
        v-if="coverInfo"
        style="margin-top: 8px; font-size: 12px; color: #666;"
      >
        <div>{{ coverInfo.name }}</div>
        <div>类型: {{ coverInfo.contentType }}</div>
      </div>
    </div>
    <p
      v-else
      style="text-align: center; color: #999; padding: 24px 0;"
    >
      暂无封面
    </p>

    <n-tabs
      type="segment"
      style="margin-top: 16px;"
    >
      <n-tab-pane
        name="upload"
        tab="本地上传"
      >
        <n-upload
          :show-file-list="false"
          accept="image/*"
          @change="handleUploadChange"
        >
          <n-button
            block
            size="small"
          >
            选择本地图片
          </n-button>
        </n-upload>
      </n-tab-pane>

      <n-tab-pane
        name="url"
        tab="URL 下载"
      >
        <n-space vertical>
          <n-input
            v-model:value="coverUrlInput"
            placeholder="输入封面图片 URL"
            size="small"
          />
          <n-button
            block
            size="small"
            @click="handleDownloadCover"
          >
            下载封面
          </n-button>
          <n-text
            depth="3"
            style="font-size: 12px;"
          >
            下载后替换当前封面
          </n-text>
        </n-space>
      </n-tab-pane>
    </n-tabs>
  </n-card>
</template>
