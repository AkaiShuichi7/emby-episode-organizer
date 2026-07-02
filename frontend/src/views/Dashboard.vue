<template>
  <div class="dashboard">
    <n-spin :show="loading">
      <n-grid :x-gap="16" :y-gap="16" :cols="4">
        <n-grid-item>
          <n-card title="Emby 状态">
            <n-space align="center">
              <n-badge :type="isEmbyConnected ? 'success' : 'error'" dot />
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

      <h3 class="mt-4">最近任务</h3>
      <n-data-table
        :columns="columns"
        :data="recentTasks"
        :bordered="false"
      />
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NGrid, NGridItem, NCard, NSpin, NDataTable, NBadge, NSpace } from 'naive-ui'
import { useSettingsStore } from '@/stores/settings'
import { useLibrariesStore } from '@/stores/libraries'
import { useSeriesStore } from '@/stores/series'
import { useTasksStore } from '@/stores/tasks'

const settingsStore = useSettingsStore()
const librariesStore = useLibrariesStore()
const seriesStore = useSeriesStore()
const tasksStore = useTasksStore()

const loading = ref(true)

const isEmbyConnected = computed(() => !!(settingsStore.embyConfig?.url && settingsStore.embyConfig?.apiKeySet))
const recentTasks = computed(() => tasksStore.tasks.slice(0, 5))

const columns = [
  { title: '状态', key: 'status' },
  { title: '剧集', key: 'series_name' },
  { title: '季', key: 'season' },
  { title: '集', key: 'episode' },
  { title: '标题', key: 'title' },
  { title: '创建时间', key: 'created_at' }
]

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([
      settingsStore.loadEmbyConfig(),
      librariesStore.loadLibraries(),
      seriesStore.loadSeries(),
      tasksStore.loadTasks({ status: 'staged' })
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
