<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import {
  NCard,
  NSelect,
  NButton,
  NSpace,
  NDataTable,
  NTag,
  NPopconfirm,
  useMessage,
  NPagination
} from 'naive-ui'
import { useTasksStore, type Task, type TaskStatus } from '@/stores/tasks'
import { useSeriesStore } from '@/stores/series'

const router = useRouter()
const message = useMessage()
const tasksStore = useTasksStore()
const seriesStore = useSeriesStore()

const statusFilter = ref<TaskStatus | null>(null)
const seriesFilter = ref<number | null>(null)
const sortDirection = ref<'desc' | 'asc'>('desc')
const currentPage = ref(1)
const pageSize = ref(10)

import type { SelectMixedOption } from 'naive-ui/es/select/src/interface'

const statusOptions: SelectMixedOption[] = [
  { label: '全部', value: null as unknown as string },
  { label: '已暂存', value: 'staged' },
  { label: '已提交', value: 'committed' },
  { label: '失败', value: 'failed' },
  { label: '已取消', value: 'cancelled' },
]

const seriesOptions = computed<SelectMixedOption[]>(() => [
  { label: '全部剧集', value: null as unknown as number },
  ...seriesStore.series.map((s) => ({
    label: s.name,
    value: s.id,
  })),
])

const filteredTasks = computed(() => {
  let result = [...tasksStore.tasks]

  if (statusFilter.value) {
    result = result.filter((t) => t.status === statusFilter.value)
  }

  if (seriesFilter.value) {
    result = result.filter((t) => t.series_id === seriesFilter.value)
  }

  result.sort((a, b) => {
    const timeA = new Date(a.created_at).getTime()
    const timeB = new Date(b.created_at).getTime()
    return sortDirection.value === 'desc' ? timeB - timeA : timeA - timeB
  })

  return result
})

const pagedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredTasks.value.slice(start, start + pageSize.value)
})

const pageCount = computed(() => Math.ceil(filteredTasks.value.length / pageSize.value) || 1)
const cancellableStatuses: TaskStatus[] = ['draft', 'staged', 'nfo_edited', 'failed']

function canCancel(row: Task) {
  return cancellableStatuses.includes(row.status)
}

function getStatusType(status: TaskStatus) {
  switch (status) {
    case 'committed': return 'success'
    case 'staged': return 'warning'
    case 'failed': return 'error'
    case 'cancelled': return 'default'
    default: return 'info'
  }
}

function getStatusLabel(status: TaskStatus) {
  switch (status) {
    case 'committed': return '已提交'
    case 'staged': return '已暂存'
    case 'failed': return '失败'
    case 'cancelled': return '已取消'
    case 'draft': return '草稿'
    case 'nfo_edited': return 'NFO 已编辑'
    case 'ready_to_commit': return '待提交'
    default: return status
  }
}

function formatTime(time: string) {
  return new Date(time).toLocaleString('zh-CN')
}

async function applyFilters() {
  currentPage.value = 1
  const filters: { status?: TaskStatus; series_id?: number } = {}
  if (statusFilter.value) filters.status = statusFilter.value
  if (seriesFilter.value) filters.series_id = seriesFilter.value
  await tasksStore.loadTasks(filters)
}

function toggleSort() {
  sortDirection.value = sortDirection.value === 'desc' ? 'asc' : 'desc'
}

async function deleteTask(id: number) {
  const success = await tasksStore.deleteTask(id)
  if (success !== null) {
    message.success('删除成功')
  } else {
    message.error(tasksStore.error || '删除失败')
  }
}

async function cancelTask(id: number) {
  const success = await tasksStore.cancelTask(id)
  if (success !== null) {
    message.success('取消成功')
  } else {
    message.error(tasksStore.error || '取消失败')
  }
}

function openDetail(row: Task) {
  router.push(`/tasks/${row.id}`)
}

const columns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '剧集', key: 'series_name' },
  {
    title: '季×集',
    key: 'season_episode',
    render(row: Task) {
      return `S${String(row.season_number).padStart(2, '0')}E${String(row.episode_number).padStart(2, '0')}`
    }
  },
  { title: '标题', key: 'title' },
  {
    title: '状态',
    key: 'status',
    render(row: Task) {
      return h(NTag, { type: getStatusType(row.status) }, { default: () => getStatusLabel(row.status) })
    }
  },
  {
    title: '创建时间',
    key: 'created_at',
    render(row: Task) {
      return formatTime(row.created_at)
    }
  },
  {
    title: '操作',
    key: 'actions',
    render(row: Task) {
      const buttons = [
        h(
          NButton,
          { size: 'small', onClick: () => openDetail(row) },
          { default: () => '查看' }
        ),
      ]

      if (canCancel(row)) {
        buttons.push(
          h(
            NPopconfirm,
            {
              positiveText: '确认',
              negativeText: '取消',
              onPositiveClick: () => cancelTask(row.id)
            },
            {
              trigger: () => h(
                NButton,
                {
                  size: 'small',
                  onClick: (e: MouseEvent) => e.stopPropagation()
                },
                { default: () => '取消任务' }
              ),
              default: () => '确认取消该任务？取消后可删除记录。'
            }
          )
        )
      }

      buttons.push(
        h(
          NPopconfirm,
          {
            positiveText: '确认',
            negativeText: '取消',
            onPositiveClick: () => deleteTask(row.id)
          },
          {
            trigger: () => h(
              NButton,
              {
                size: 'small',
                type: 'error',
                onClick: (e: MouseEvent) => e.stopPropagation()
              },
              { default: () => '删除' }
            ),
            default: () => '确认删除该任务记录？已提交的任务仅删除记录，不影响已入库的文件。'
          }
        )
      )

      return h(NSpace, {}, {
        default: () => buttons
      })
    }
  }
]

onMounted(async () => {
  await Promise.all([
    tasksStore.loadTasks({ status: statusFilter.value ?? undefined }),
    seriesStore.loadSeries(),
  ])
})

function handlePageChange(page: number) {
  currentPage.value = page
}

function handlePageSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
}
</script>

<template>
  <div class="task-list">
    <n-card title="任务列表">
      <n-space
        align="center"
        style="margin-bottom: 16px;"
      >
        <n-select
          v-model:value="statusFilter"
          :options="statusOptions"
          placeholder="状态筛选"
          style="width: 140px;"
          clearable
          @update:value="applyFilters"
        />

        <n-select
          v-model:value="seriesFilter"
          :options="seriesOptions"
          placeholder="剧集筛选"
          style="width: 200px;"
          clearable
          filterable
          @update:value="applyFilters"
        />

        <n-button
          @click="toggleSort"
        >
          时间 {{ sortDirection === 'desc' ? '降序' : '升序' }}
        </n-button>
      </n-space>

      <n-data-table
        :columns="columns"
        :data="pagedTasks"
        :loading="tasksStore.loading"
        :row-props="(row) => ({ style: 'cursor: pointer;', onClick: () => openDetail(row) })"
      />

      <n-space
        justify="end"
        style="margin-top: 16px;"
      >
        <n-pagination
          v-model:page="currentPage"
          v-model:page-size="pageSize"
          :page-count="pageCount"
          :page-sizes="[10, 20, 50]"
          show-size-picker
          @update:page="handlePageChange"
          @update:page-size="handlePageSizeChange"
        />
      </n-space>
    </n-card>
  </div>
</template>

<style scoped>
.task-list {
  padding: 16px;
}
</style>
