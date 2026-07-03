<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  NCard,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NButton,
  NSpace,
  NDynamicInput
} from 'naive-ui'

export interface NFOActor {
  name: string
  role: string
}

export interface NFOForm {
  title: string
  plot: string
  premiered: string
  year: number | null
  genre: string
  tag: string
  actors: NFOActor[]
  director: string
  studio: string
  rating: number | null
}

const props = defineProps<{
  modelValue: Record<string, unknown> | null
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<string, unknown>): void
  (e: 'save', value: Record<string, unknown>): void
}>()

function asString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function asNumber(value: unknown): number | null {
  if (typeof value === 'number') return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isNaN(parsed) ? null : parsed
  }
  return null
}

function asActors(value: unknown): NFOActor[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => ({
    name: asString((item as Record<string, unknown>)?.name),
    role: asString((item as Record<string, unknown>)?.role),
  }))
}

const form = ref<NFOForm>({
  title: '',
  plot: '',
  premiered: '',
  year: null,
  genre: '',
  tag: '',
  actors: [],
  director: '',
  studio: '',
  rating: null,
})

function loadNfo(nfo: Record<string, unknown> | null) {
  const next: NFOForm = {
    title: asString(nfo?.title),
    plot: asString(nfo?.plot),
    premiered: asString(nfo?.premiered),
    year: asNumber(nfo?.year),
    genre: asString(nfo?.genre),
    tag: asString(nfo?.tag),
    actors: asActors(nfo?.actor ?? nfo?.actors),
    director: asString(nfo?.director),
    studio: asString(nfo?.studio),
    rating: asNumber(nfo?.rating),
  }

  const current = form.value
  if (
    current.title === next.title &&
    current.plot === next.plot &&
    current.premiered === next.premiered &&
    current.year === next.year &&
    current.genre === next.genre &&
    current.tag === next.tag &&
    current.director === next.director &&
    current.studio === next.studio &&
    current.rating === next.rating &&
    current.actors.length === next.actors.length
  ) {
    return
  }

  form.value = next
}

function buildNfo(): Record<string, unknown> {
  const nfo: Record<string, unknown> = {
    title: form.value.title,
    plot: form.value.plot,
    premiered: form.value.premiered,
    director: form.value.director,
    studio: form.value.studio,
  }

  if (form.value.year !== null && form.value.year !== undefined) nfo.year = form.value.year
  if (form.value.rating !== null && form.value.rating !== undefined) nfo.rating = form.value.rating
  if (form.value.genre) nfo.genre = form.value.genre
  if (form.value.tag) nfo.tag = form.value.tag
  if (form.value.actors.length > 0) nfo.actor = form.value.actors

  return nfo
}

let isInternalUpdate = false

watch(() => props.modelValue, (next) => {
  isInternalUpdate = true
  loadNfo(next)
  isInternalUpdate = false
}, { immediate: true, deep: true })

watch(form, () => {
  if (isInternalUpdate) return
  emit('update:modelValue', buildNfo())
}, { deep: true })

function handleSave() {
  emit('save', buildNfo())
}

function createActor(): NFOActor {
  return { name: '', role: '' }
}

function renderActorLabel(index: number): string {
  return `演员 ${index + 1}`
}
</script>

<template>
  <n-card
    title="NFO 信息"
    :segmented="{ content: true }"
  >
    <n-form
      :model="form"
      label-placement="left"
      label-width="100"
    >
      <n-form-item label="标题">
        <n-input
          v-model:value="form.title"
          placeholder="分集标题"
        />
      </n-form-item>

      <n-form-item label="剧情简介">
        <n-input
          v-model:value="form.plot"
          type="textarea"
          :rows="4"
          placeholder="剧情简介"
        />
      </n-form-item>

      <n-form-item label="首播日期">
        <n-input
          v-model:value="form.premiered"
          placeholder="YYYY-MM-DD"
        />
      </n-form-item>

      <n-form-item label="年份">
        <n-input-number
          v-model:value="form.year"
          :min="1900"
          placeholder="年份"
        />
      </n-form-item>

      <n-form-item label="类型">
        <n-input
          v-model:value="form.genre"
          placeholder="多个类型以逗号分隔"
        />
      </n-form-item>

      <n-form-item label="标签">
        <n-input
          v-model:value="form.tag"
          placeholder="多个标签以逗号分隔"
        />
      </n-form-item>

      <n-form-item label="导演">
        <n-input
          v-model:value="form.director"
          placeholder="导演"
        />
      </n-form-item>

      <n-form-item label="工作室">
        <n-input
          v-model:value="form.studio"
          placeholder="工作室 / 出品方"
        />
      </n-form-item>

      <n-form-item label="评分">
        <n-input-number
          v-model:value="form.rating"
          :min="0"
          :max="10"
          placeholder="0-10"
        />
      </n-form-item>

      <n-form-item label="演员">
        <n-dynamic-input
          v-model:value="form.actors"
          :on-create="createActor"
          :item-style="{ marginBottom: '8px' }"
        >
          <template #default="{ value, index }">
            <n-space>
              <span class="actor-label">{{ renderActorLabel(index) }}</span>
              <n-input
                v-model:value="value.name"
                placeholder="演员姓名"
              />
              <n-input
                v-model:value="value.role"
                placeholder="饰演角色"
              />
            </n-space>
          </template>
        </n-dynamic-input>
      </n-form-item>

      <n-space justify="end">
        <n-button
          type="primary"
          :loading="loading"
          @click="handleSave"
        >
          保存 NFO
        </n-button>
      </n-space>
    </n-form>
  </n-card>
</template>

<style scoped>
.actor-label {
  display: inline-block;
  width: 60px;
  line-height: 34px;
  color: #666;
}
</style>
