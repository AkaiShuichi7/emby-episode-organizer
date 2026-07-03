<script setup lang="ts">
import { computed, ref, onMounted, h } from 'vue'
import { NButton, NCard, NDataTable, NForm, NFormItem, NInput, NModal, NPopconfirm, NSpace, NSwitch, NSelect, useMessage } from 'naive-ui'
import { useLibrariesStore, type Library, type LibraryCreatePayload } from '@/stores/libraries'
import { api } from '@/api/client'

interface EmbyLibrary {
  ItemId: string
  Name: string
  CollectionType?: string | null
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '刷新 Emby 媒体库失败'
}

const message = useMessage()
const librariesStore = useLibrariesStore()

const showModal = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const isSubmitting = ref(false)
const isRefreshingEmby = ref(false)

const embyLibraries = ref<EmbyLibrary[]>([])
const libraryOptions = computed(() =>
  embyLibraries.value.map((library) => ({
    label: library.Name,
    value: library.Name
  }))
)

const formData = ref<LibraryCreatePayload>({
  name: '',
  staging_root: '',
  target_root: '',
  enabled: true
})

const columns = [
  { title: '名称', key: 'name' },
  { title: 'Emby 库 ID', key: 'emby_library_id' },
  { title: '整理源目录', key: 'staging_root' },
  { title: '目标目录', key: 'target_root' },
  { 
    title: '启用', 
    key: 'enabled',
    render(row: Library) {
      return h(NSwitch, {
        value: row.enabled,
        onUpdateValue: (value: boolean) => handleToggleEnabled(row, value)
      })
    }
  },
  {
    title: '操作',
    key: 'actions',
    render(row: Library) {
      return h(NSpace, {}, {
        default: () => [
          h(NButton, { size: 'small', onClick: () => handleEdit(row) }, { default: () => '编辑' }),
          h(NPopconfirm, {
            onPositiveClick: () => handleDelete(row.id)
          }, {
            trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
            default: () => '确认删除此映射？'
          })
        ]
      })
    }
  }
]

onMounted(async () => {
  await librariesStore.loadLibraries()
})

async function handleRefreshEmby() {
  isRefreshingEmby.value = true
  try {
    const libs = await api.get<EmbyLibrary[]>('/emby/libraries')
    embyLibraries.value = libs
    message.success('刷新 Emby 媒体库成功')
  } catch (error: unknown) {
    message.error(getErrorMessage(error))
  } finally {
    isRefreshingEmby.value = false
  }
}

function handleAdd() {
  isEditing.value = false
  editingId.value = null
  formData.value = {
    name: '',
    staging_root: '',
    target_root: '',
    enabled: true
  }
  showModal.value = true
}

function handleEdit(row: Library) {
  isEditing.value = true
  editingId.value = row.id
  formData.value = {
    name: row.name,
    staging_root: row.staging_root || '',
    target_root: row.target_root || '',
    enabled: row.enabled
  }
  showModal.value = true
}

async function handleToggleEnabled(row: Library, enabled: boolean) {
  const result = await librariesStore.updateLibrary(row.id, { enabled })
  if (result) {
    message.success('状态已更新')
  } else {
    message.error(librariesStore.error || '更新失败')
  }
}

async function handleDelete(id: number) {
  await librariesStore.deleteLibrary(id)
  if (!librariesStore.error) {
    message.success('删除成功')
  } else {
    message.error(librariesStore.error || '删除失败')
  }
}

async function handleSubmit() {
  if (!formData.value.name || !formData.value.staging_root || !formData.value.target_root) {
    message.warning('请填写完整信息')
    return
  }

  isSubmitting.value = true
  let result
  const selectedEmbyLibrary = embyLibraries.value.find((library) => library.Name === formData.value.name)
  const payload: LibraryCreatePayload = {
    name: formData.value.name,
    staging_root: formData.value.staging_root,
    target_root: formData.value.target_root,
    enabled: formData.value.enabled,
    ...(selectedEmbyLibrary?.CollectionType ? { collection_type: selectedEmbyLibrary.CollectionType } : {})
  }
  
  if (isEditing.value && editingId.value) {
    result = await librariesStore.updateLibrary(editingId.value, formData.value)
  } else {
    result = await librariesStore.createLibrary(payload)
  }
  
  isSubmitting.value = false

  if (result) {
    message.success(isEditing.value ? '更新成功' : '创建成功')
    showModal.value = false
  } else {
    message.error(librariesStore.error || (isEditing.value ? '更新失败' : '创建失败'))
  }
}
</script>

<template>
  <div class="library-mapping">
    <n-card title="媒体库映射">
      <template #header-extra>
        <n-space>
          <n-button
            :loading="isRefreshingEmby"
            @click="handleRefreshEmby"
          >
            刷新 Emby 媒体库
          </n-button>
          <n-button
            type="primary"
            @click="handleAdd"
          >
            添加映射
          </n-button>
        </n-space>
      </template>

      <n-data-table
        :columns="columns"
        :data="librariesStore.libraries"
        :loading="librariesStore.loading"
      />
    </n-card>

    <n-modal
      v-model:show="showModal"
      preset="card"
      :title="isEditing ? '编辑映射' : '添加映射'"
      style="width: 600px"
    >
      <n-form
        label-placement="left"
        label-width="100"
      >
        <n-form-item
          label="名称"
          required
        >
          <n-select
            v-if="!isEditing"
            v-model:value="formData.name"
            :options="libraryOptions"
            placeholder="先刷新 Emby 媒体库后选择"
            filterable
            clearable
          />
          <n-input
            v-else
            v-model:value="formData.name"
            placeholder="例如：动画"
          />
        </n-form-item>
        <n-form-item
          label="整理源目录"
          required
        >
          <n-input
            v-model:value="formData.staging_root"
            placeholder="例如：/data/downloads/anime"
          />
        </n-form-item>
        <n-form-item
          label="目标目录"
          required
        >
          <n-input
            v-model:value="formData.target_root"
            placeholder="例如：/data/media/anime"
          />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="formData.enabled" />
        </n-form-item>
        <n-form-item>
          <n-space
            justify="end"
            style="width: 100%"
          >
            <n-button @click="showModal = false">
              取消
            </n-button>
            <n-button
              type="primary"
              :loading="isSubmitting"
              @click="handleSubmit"
            >
              确定
            </n-button>
          </n-space>
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<style scoped>
.library-mapping {
  max-width: 1200px;
  margin: 0 auto;
}
</style>
