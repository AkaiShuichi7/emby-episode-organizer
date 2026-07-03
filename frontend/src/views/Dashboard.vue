<template>
  <div class="dashboard">
    <n-spin :show="loading">
      <n-grid
        :x-gap="16"
        :y-gap="16"
        :cols="4"
      >
        <n-grid-item>
          <n-card title="Emby 状态">
            <n-space align="center">
              <n-badge
                :type="isEmbyConnected ? 'success' : 'error'"
                dot
              />
              {{ isEmbyConnected ? '已连接' : '未连接' }}
            </n-space>
          </n-card>
        </n-grid-item>
        <n-grid-item>
          <n-card title="媒体库数量">
            {{ librariesStore.libraries.length }}
          </n-card>
        </n-grid-item>
        <n-grid-item>
          <n-card title="剧集数量">
            {{ seriesStore.series.length }}
          </n-card>
        </n-grid-item>
        <n-grid-item>
          <n-card title="待入库任务">
            {{ tasksStore.tasks.length }}
          </n-card>
        </n-grid-item>
      </n-grid>

      <h3 class="mt-4">
        最近任务
      </h3>
      <n-data-table
        :columns="columns"
        :data="recentTasks"
        :bordered="false"
      />
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { NGrid, NGridItem, NCard, NSpin, NDataTable, NBadge, NSpace, NTag } from 'naive-ui'
import { useSettingsStore } from '@/stores/settings'
import { useLibrariesStore } from '@/stores/libraries'
import { useSeriesStore } from '@/stores/series'
import { useTasksStore, type Task } from '@/stores/tasks'

const settingsStore = useSettingsStore()
const librariesStore = useLibrariesStore()
const seriesStore = useSeriesStore()
const tasksStore = useTasksStore()

const loading = ref(true)

const isEmbyConnected = computed(() => {
  const url = settingsStore.allSettings['emby.server_url']
  const apiKey = settingsStore.allSettings['emby.api_key']
  return typeof url === 'string' && typeof apiKey === 'string' && !!(url && apiKey)
})
const recentTasks = computed(() => tasksStore.tasks.slice(0, 5))

function getStatusLabel(status: Task['status']): string {
  switch (status) {
    case 'draft': return '草稿'
    case 'staged': return '已暂存'
    case 'nfo_edited': return 'NFO 已编辑'
    case 'ready_to_commit': return '待入库'
    case 'committed': return '已入库'
    case 'failed': return '失败'
    case 'cancelled': return '已取消'
    default: return status
  }
}

function getStatusType(status: Task['status']): 'default' | 'success' | 'info' | 'warning' | 'error' {
  switch (status) {
    case 'committed': return 'success'
    case 'ready_to_commit':
    case 'staged':
    case 'nfo_edited': return 'info'
    case 'failed': return 'error'
    case 'cancelled': return 'warning'
    default: return 'default'
  }
}

function formatTime(time: string) {
  return new Date(time).toLocaleString('zh-CN')
}

const columns = [
  {
    title: '状态',
    key: 'status',
    render(row: Task) {
      return h(NTag, { type: getStatusType(row.status), size: 'small' }, { default: () => getStatusLabel(row.status) })
    }
  },
  { title: '剧集', key: 'series_name' },
  { title: '季', key: 'season_number' },
  { title: '集', key: 'episode_number' },
  { title: '标题', key: 'title' },
  {
    title: '创建时间',
    key: 'created_at',
    render(row: Task) {
      return formatTime(row.created_at)
    }
  }
]

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([
      settingsStore.loadSettings(),
      librariesStore.loadLibraries(),
      seriesStore.loadSeries(),
      tasksStore.loadTasks({})
    ])
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.dashboard {
  padding: 16px 0;
}
.mt-4 {
  margin-top: 24px;
  margin-bottom: 16px;
}
</style>
