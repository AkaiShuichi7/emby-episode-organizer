<script setup lang="ts">
import { ref, watch, computed } from 'vue'
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
  useMessage
} from 'naive-ui'
import { api } from '@/api/client'

interface FileEntry {
  name: string
  path: string
  is_dir: boolean
  size: number | null
  modified_at: string | null
}

interface BrowseResponse {
  current_path: string
  parent_path: string | null
  entries: FileEntry[]
}

const props = defineProps<{
  show: boolean
  initialPath?: string
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'select', path: string): void
}>()

const loading = ref(false)
const currentPath = ref('')
const parentPath = ref<string | null>(null)
const entries = ref<FileEntry[]>([])

let message: ReturnType<typeof useMessage> | null = null
try {
  message = useMessage()
} catch {
  // 测试环境未包裹 NMessageProvider，降级为空对象
}

const loadPath = async (path: string) => {
  loading.value = true
  try {
    const res = await api.post<BrowseResponse>('/files/browse', { path })
    currentPath.value = res.current_path
    parentPath.value = res.parent_path
    entries.value = res.entries.sort((a, b) => {
      if (a.is_dir === b.is_dir) return a.name.localeCompare(b.name)
      return a.is_dir ? -1 : 1
    })
  } catch {
    message?.error('浏览目录失败')
  } finally {
    loading.value = false
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    loadPath(props.initialPath || '')
  }
})

const handleEntryClick = (entry: FileEntry) => {
  if (entry.is_dir) {
    loadPath(entry.path)
  } else {
    emit('select', entry.path)
    emit('update:show', false)
  }
}

const pathSegments = computed(() => {
  if (!currentPath.value) return []
  const parts = currentPath.value.split(/[/\\]/).filter(Boolean)
  // 处理不同操作系统的根路径
  const isWindows = currentPath.value.includes(':')
  const segments: { name: string; path: string }[] = []
  
  let current = ''
  if (!isWindows) {
    segments.push({ name: '/', path: '/' })
    current = '/'
  }

  parts.forEach((part, index) => {
    if (isWindows && index === 0) {
      current = part + '\\'
      segments.push({ name: part, path: current })
    } else {
      const sep = isWindows ? '\\' : '/'
      current = current.endsWith(sep) ? current + part : current + sep + part
      segments.push({ name: part, path: current })
    }
  })
  return segments
})

</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="选择源视频文件"
    style="width: 800px"
    @update:show="val => emit('update:show', val)"
  >
    <n-spin :show="loading">
      <n-space vertical>
        <n-breadcrumb>
          <n-breadcrumb-item
            v-for="seg in pathSegments"
            :key="seg.path"
            @click="loadPath(seg.path)"
          >
            {{ seg.name }}
          </n-breadcrumb-item>
        </n-breadcrumb>

        <div style="max-height: 400px; overflow-y: auto; border: 1px solid #efeff5; border-radius: 4px;">
          <n-list
            hoverable
            clickable
          >
            <n-list-item
              v-if="parentPath"
              @click="loadPath(parentPath)"
            >
              <n-text depth="3">
                ..
              </n-text>
            </n-list-item>
            <n-list-item
              v-for="entry in entries"
              :key="entry.path"
              @click="handleEntryClick(entry)"
            >
              <n-space justify="space-between">
                <n-text>
                  <span v-if="entry.is_dir">📁</span>
                  <span v-else>📄</span>
                  {{ entry.name }}
                </n-text>
                <n-text
                  v-if="!entry.is_dir && entry.size"
                  depth="3"
                >
                  {{ (entry.size / 1024 / 1024).toFixed(2) }} MB
                </n-text>
              </n-space>
            </n-list-item>
          </n-list>
        </div>

        <n-space justify="end">
          <n-button @click="emit('update:show', false)">
            取消
          </n-button>
        </n-space>
      </n-space>
    </n-spin>
  </n-modal>
</template>
