<script setup lang="ts">
import { ref, onMounted, computed, h } from 'vue'
import {
  NCard,
  NInput,
  NButton,
  NDataTable,
  NModal,
  NForm,
  NFormItem,
  NSelect,
  NInputNumber,
  NSwitch,
  NSpace,
  useMessage,
  NPopconfirm
} from 'naive-ui'
import { useSeriesStore } from '@/stores/series'
import { useLibrariesStore } from '@/stores/libraries'
import { api } from '@/api/client'

const message = useMessage()
const seriesStore = useSeriesStore()
const librariesStore = useLibrariesStore()

const keyword = ref('')
const showAddModal = ref(false)
const showEditModal = ref(false)

const addForm = ref({
  name: '',
  emby_series_id: '',
  library_id: null as number | null,
  staging_path: '',
  target_path: '',
  default_season: 1,
  enabled: true
})

const editForm = ref({
  id: 0,
  name: '',
  emby_series_id: '',
  library_id: null as number | null,
  staging_path: '',
  target_path: '',
  default_season: 1,
  enabled: true
})

onMounted(async () => {
  await Promise.all([
    seriesStore.loadSeries(),
    librariesStore.loadLibraries()
  ])
})

const handleSearch = async () => {
  if (!keyword.value.trim()) {
    message.warning('请输入搜索关键词')
    return
  }
  await seriesStore.loadEmbySeries(keyword.value)
}

const sanitizeSeriesName = (name: string) => {
  return name
    .replace(/[\\/:*?"<>|]/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\./g, '')
}

const libraryOptions = computed(() => {
  return librariesStore.libraries.map(lib => ({
    label: lib.name,
    value: lib.id
  }))
})

const handleLibraryChange = (libraryId: number | null, form: typeof addForm.value) => {
  if (!libraryId) return
  const library = librariesStore.libraries.find(l => l.id === libraryId)
  if (!library) return

  const sanitized = sanitizeSeriesName(form.name)
  if (library.staging_root) {
    form.staging_path = `${library.staging_root}/${sanitized}`
  }
  if (library.target_root) {
    form.target_path = `${library.target_root}/${sanitized}`
  }
}

const openAddModal = (row: any) => {
  addForm.value = {
    name: row.Name || '',
    emby_series_id: row.Id || '',
    library_id: null,
    staging_path: '',
    target_path: '',
    default_season: 1,
    enabled: true
  }
  showAddModal.value = true
}

const submitAdd = async () => {
  if (!addForm.value.library_id) {
    message.error('请选择媒体库')
    return
  }
  const success = await seriesStore.createSeriesConfig({
    name: addForm.value.name,
    emby_series_id: addForm.value.emby_series_id,
    library_id: addForm.value.library_id,
    staging_path: addForm.value.staging_path,
    target_path: addForm.value.target_path,
    default_season: addForm.value.default_season,
    enabled: addForm.value.enabled
  })
  if (success) {
    message.success('添加成功')
    showAddModal.value = false
    await seriesStore.loadSeries()
  }
}

const openEditModal = (row: any) => {
  editForm.value = {
    id: row.id,
    name: row.name,
    emby_series_id: row.emby_series_id || '',
    library_id: row.library_id,
    staging_path: row.staging_path || '',
    target_path: row.target_path || '',
    default_season: row.default_season,
    enabled: row.enabled
  }
  showEditModal.value = true
}

const submitEdit = async () => {
  if (!editForm.value.library_id) {
    message.error('请选择媒体库')
    return
  }
  const success = await seriesStore.updateSeriesConfig(editForm.value.id, {
    name: editForm.value.name,
    emby_series_id: editForm.value.emby_series_id,
    library_id: editForm.value.library_id,
    staging_path: editForm.value.staging_path,
    target_path: editForm.value.target_path,
    default_season: editForm.value.default_season,
    enabled: editForm.value.enabled
  })
  if (success) {
    message.success('更新成功')
    showEditModal.value = false
    await seriesStore.loadSeries()
  }
}

const toggleEnabled = async (row: any) => {
  const success = await seriesStore.updateSeriesConfig(row.id, {
    enabled: !row.enabled
  })
  if (success) {
    message.success(row.enabled ? '已禁用' : '已启用')
    await seriesStore.loadSeries()
  }
}

const deleteSeries = async (row: any) => {
  try {
    await api.delete(`/series/${row.id}`)
    message.success('删除成功')
    await seriesStore.loadSeries()
  } catch (e: any) {
    message.error(e.message || '删除失败')
  }
}

const searchColumns = [
  { title: 'Emby ID', key: 'Id' },
  { title: '剧集名称', key: 'Name' },
  { title: '年份', key: 'ProductionYear' },
  {
    title: '操作',
    key: 'actions',
    render(row: any) {
      return h(
        NButton,
        {
          size: 'small',
          type: 'primary',
          onClick: () => openAddModal(row)
        },
        { default: () => '添加为配置' }
      )
    }
  }
]

const configColumns = [
  { title: '剧集名称', key: 'name' },
  { title: 'Emby ID', key: 'emby_series_id' },
  { title: '媒体库', key: 'library_name' },
  { title: '整理目录', key: 'staging_path' },
  { title: '目标目录', key: 'target_path' },
  { title: '默认季', key: 'default_season' },
  {
    title: '状态',
    key: 'enabled',
    render(row: any) {
      return h(
        NSwitch,
        {
          value: row.enabled,
          onUpdateValue: () => toggleEnabled(row)
        }
      )
    }
  },
  {
    title: '操作',
    key: 'actions',
    render(row: any) {
      return h(NSpace, {}, {
        default: () => [
          h(
            NButton,
            {
              size: 'small',
              onClick: () => openEditModal(row)
            },
            { default: () => '编辑' }
          ),
          h(
            NPopconfirm,
            {
              onPositiveClick: () => deleteSeries(row)
            },
            {
              trigger: () => h(
                NButton,
                {
                  size: 'small',
                  type: 'error'
                },
                { default: () => '删除' }
              ),
              default: () => '确认删除该剧集配置？'
            }
          )
        ]
      })
    }
  }
]
</script>

<template>
  <div class="series-config">
    <n-space vertical size="large">
      <n-card title="搜索 Emby 剧集">
        <n-space>
          <n-input
            v-model:value="keyword"
            placeholder="输入剧集名称"
            @keyup.enter="handleSearch"
          />
          <n-button
            type="primary"
            :loading="seriesStore.loading"
            @click="handleSearch"
          >
            搜索
          </n-button>
        </n-space>
        
        <n-data-table
          v-if="seriesStore.embySearchResults.length > 0"
          :columns="searchColumns"
          :data="seriesStore.embySearchResults"
          :loading="seriesStore.loading"
          style="margin-top: 16px;"
        />
      </n-card>

      <n-card title="已配置剧集">
        <n-data-table
          :columns="configColumns"
          :data="seriesStore.series"
          :loading="seriesStore.loading"
        />
      </n-card>
    </n-space>

    <n-modal v-model:show="showAddModal" preset="card" title="添加为配置" style="width: 600px">
      <n-form :model="addForm" label-placement="left" label-width="100">
        <n-form-item label="剧集名称">
          <n-input v-model:value="addForm.name" readonly />
        </n-form-item>
        <n-form-item label="媒体库" required>
          <n-select
            v-model:value="addForm.library_id"
            :options="libraryOptions"
            @update:value="(val) => handleLibraryChange(val, addForm)"
          />
        </n-form-item>
        <n-form-item label="整理目录">
          <n-input v-model:value="addForm.staging_path" />
        </n-form-item>
        <n-form-item label="目标目录">
          <n-input v-model:value="addForm.target_path" />
        </n-form-item>
        <n-form-item label="默认季">
          <n-input-number v-model:value="addForm.default_season" :min="1" />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="addForm.enabled" />
        </n-form-item>
        <n-space justify="end">
          <n-button @click="showAddModal = false">取消</n-button>
          <n-button type="primary" @click="submitAdd">确定</n-button>
        </n-space>
      </n-form>
    </n-modal>

    <n-modal v-model:show="showEditModal" preset="card" title="编辑配置" style="width: 600px">
      <n-form :model="editForm" label-placement="left" label-width="100">
        <n-form-item label="剧集名称">
          <n-input v-model:value="editForm.name" />
        </n-form-item>
        <n-form-item label="媒体库" required>
          <n-select
            v-model:value="editForm.library_id"
            :options="libraryOptions"
            @update:value="(val) => handleLibraryChange(val, editForm)"
          />
        </n-form-item>
        <n-form-item label="整理目录">
          <n-input v-model:value="editForm.staging_path" />
        </n-form-item>
        <n-form-item label="目标目录">
          <n-input v-model:value="editForm.target_path" />
        </n-form-item>
        <n-form-item label="默认季">
          <n-input-number v-model:value="editForm.default_season" :min="1" />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="editForm.enabled" />
        </n-form-item>
        <n-space justify="end">
          <n-button @click="showEditModal = false">取消</n-button>
          <n-button type="primary" @click="submitEdit">确定</n-button>
        </n-space>
      </n-form>
    </n-modal>
  </div>
</template>
