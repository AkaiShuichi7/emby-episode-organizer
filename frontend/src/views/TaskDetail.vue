<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NCard,
  NButton,
  NSpace,
  NTag,
  NPopconfirm,
  useMessage,
  NGrid,
  NGridItem,
  NDescriptions,
  NDescriptionsItem,
  NSpin,
  NDivider,
  NEmpty
} from 'naive-ui'
import { useTasksStore, type Task, type TaskStatus } from '@/stores/tasks'
import NFOEditor from '@/components/NFOEditor.vue'
import CoverManager from '@/components/CoverManager.vue'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const tasksStore = useTasksStore()

const taskId = computed(() => Number(route.params.id))
const task = computed(() => tasksStore.currentTask)
const loading = computed(() => tasksStore.loading)
const localNfo = ref<Record<string, unknown>>({})

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

function formatTime(time: string | null) {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

async function refreshTask() {
  if (!taskId.value) return
  await tasksStore.loadTask(taskId.value)
  localNfo.value = task.value?.nfo_json ? { ...task.value.nfo_json } : {}
}

function handleCoverUpdated(updated: Task) {
  if (tasksStore.currentTask?.id === updated.id) {
    tasksStore.currentTask = updated
  }
}

async function handleSaveNfo(nfo: Record<string, unknown>) {
  const result = await tasksStore.updateNFO(taskId.value, nfo)
  if (result) {
    message.success('NFO 保存成功')
    localNfo.value = { ...result.nfo_json ?? {} }
  } else {
    message.error(tasksStore.error || 'NFO 保存失败')
  }
}

async function handleCommit() {
  const result = await tasksStore.commitTask(taskId.value)
  if (result) {
    message.success('任务已提交入库')
    await refreshTask()
  } else {
    message.error(tasksStore.error || '提交失败')
  }
}

async function handleDelete() {
  const result = await tasksStore.deleteTask(taskId.value)
  if (result !== null) {
    message.success('任务记录已删除')
    router.push('/tasks')
  } else {
    message.error(tasksStore.error || '删除失败')
  }
}

async function handleCancel() {
  if (!task.value) return
  const result = await tasksStore.cancelTask(task.value.id)
  if (result) {
    message.success('任务已取消')
    await refreshTask()
  } else {
    message.error(tasksStore.error || '取消失败')
  }
}

const canCommit = computed(() => task.value?.status === 'staged' || task.value?.status === 'ready_to_commit' || task.value?.status === 'nfo_edited')
const canDelete = computed(() => task.value?.status === 'failed' || task.value?.status === 'cancelled')
const canCancel = computed(() => task.value?.status === 'draft' || task.value?.status === 'staged' || task.value?.status === 'nfo_edited' || task.value?.status === 'failed')
const canEditNfo = computed(() => {
  const editable: TaskStatus[] = ['draft', 'staged', 'nfo_edited', 'failed']
  return editable.includes(task.value?.status as TaskStatus)
})

onMounted(() => {
  refreshTask()
})
</script>

<template>
  <div class="task-detail">
    <n-spin :show="loading">
      <template v-if="task">
        <n-card
          title="任务信息"
          :segmented="{ content: true }"
        >
          <n-descriptions :columns="3">
            <n-descriptions-item label="状态">
              <n-tag :type="getStatusType(task.status)">
                {{ getStatusLabel(task.status) }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="剧集">
              {{ task.series_name ?? '-' }}
            </n-descriptions-item>
            <n-descriptions-item label="季">
              {{ task.season_number }}
            </n-descriptions-item>
            <n-descriptions-item label="集">
              {{ task.episode_number }}
            </n-descriptions-item>
            <n-descriptions-item label="标题">
              {{ task.title ?? '-' }}
            </n-descriptions-item>
            <n-descriptions-item label="创建时间">
              {{ formatTime(task.created_at) }}
            </n-descriptions-item>
            <n-descriptions-item label="更新时间">
              {{ formatTime(task.updated_at) }}
            </n-descriptions-item>
            <n-descriptions-item
              v-if="task.error_message"
              label="错误信息"
            >
              {{ task.error_message }}
            </n-descriptions-item>
          </n-descriptions>

          <n-divider />

          <n-grid
            :cols="3"
            :x-gap="16"
            :y-gap="16"
          >
            <n-grid-item>
              <n-card
                title="源文件"
                size="small"
              >
                <p>视频: {{ task.source_file_path ?? '-' }}</p>
              </n-card>
            </n-grid-item>

            <n-grid-item>
              <n-card
                title="暂存区"
                size="small"
              >
                <p>视频: {{ task.staging_video_path ?? '-' }}</p>
                <p>NFO: {{ task.staging_nfo_path ?? '-' }}</p>
                <p>封面: {{ task.staging_cover_path ?? '-' }}</p>
              </n-card>
            </n-grid-item>

            <n-grid-item>
              <n-card
                title="目标区"
                size="small"
              >
                <p>视频: {{ task.target_video_path ?? '-' }}</p>
                <p>NFO: {{ task.target_nfo_path ?? '-' }}</p>
                <p>封面: {{ task.target_cover_path ?? '-' }}</p>
              </n-card>
            </n-grid-item>
          </n-grid>
        </n-card>

        <n-grid
          :cols="24"
          :x-gap="16"
          :y-gap="16"
          style="margin-top: 16px;"
        >
          <n-grid-item :span="16">
            <n-f-o-editor
              v-if="canEditNfo"
              v-model="localNfo"
              :loading="loading"
              @save="handleSaveNfo"
            />
            <n-empty
              v-else
              description="该任务状态不支持编辑 NFO"
            />
          </n-grid-item>

          <n-grid-item :span="8">
            <cover-manager
              :task="task"
              @updated="handleCoverUpdated"
            />

            <n-card
              title="操作"
              style="margin-top: 16px;"
            >
              <n-space vertical>
                <n-popconfirm
                  v-if="canCommit"
                  positive-text="确认"
                  negative-text="取消"
                  @positive-click="handleCommit"
                >
                  <template #trigger>
                    <n-button
                      type="primary"
                      block
                    >
                      确认提交入库
                    </n-button>
                  </template>
                  确认提交该任务？提交后将移动文件到目标目录。
                </n-popconfirm>

                <n-popconfirm
                  v-if="canDelete"
                  positive-text="确认"
                  negative-text="取消"
                  @positive-click="handleDelete"
                >
                  <template #trigger>
                    <n-button
                      type="error"
                      block
                    >
                      删除记录
                    </n-button>
                  </template>
                  确认删除该任务记录？
                </n-popconfirm>

                <n-popconfirm
                  v-if="canCancel"
                  positive-text="确认"
                  negative-text="取消"
                  @positive-click="handleCancel"
                >
                  <template #trigger>
                    <n-button
                      block
                    >
                      取消任务
                    </n-button>
                  </template>
                  确认取消该任务？取消后可删除记录。
                </n-popconfirm>
              </n-space>
            </n-card>
          </n-grid-item>
        </n-grid>
      </template>

      <p
        v-else
        style="text-align: center; padding: 48px; color: #999;"
      >
        任务不存在或加载失败
      </p>
    </n-spin>
  </div>
</template>

<style scoped>
.task-detail {
  padding: 16px;
}
</style>
