<script setup lang="ts">
import {
  NCard,
  NTable,
  NText,
  NTag
} from 'naive-ui'
import type { TaskPreview } from '@/stores/tasks'

defineProps<{
  preview: TaskPreview | null
}>()
</script>

<template>
  <n-card
    title="任务预览"
    size="small"
  >
    <div v-if="preview">
      <n-table
        :bordered="false"
        :single-line="false"
        size="small"
      >
        <thead>
          <tr>
            <th>类型</th>
            <th>路径</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="preview.staging_video_path">
            <td>
              <n-tag
                size="small"
                type="info"
              >
                Staging Video
              </n-tag>
            </td>
            <td>
              <n-text code>
                {{ preview.staging_video_path }}
              </n-text>
            </td>
          </tr>
          <tr v-if="preview.staging_nfo_path">
            <td>
              <n-tag
                size="small"
                type="info"
              >
                Staging NFO
              </n-tag>
            </td>
            <td>
              <n-text code>
                {{ preview.staging_nfo_path }}
              </n-text>
            </td>
          </tr>
          <tr v-if="preview.staging_cover_path">
            <td>
              <n-tag
                size="small"
                type="info"
              >
                Staging Cover
              </n-tag>
            </td>
            <td>
              <n-text code>
                {{ preview.staging_cover_path }}
              </n-text>
            </td>
          </tr>
          <tr v-if="preview.target_video_path">
            <td>
              <n-tag
                size="small"
                type="success"
              >
                Target Video
              </n-tag>
            </td>
            <td>
              <n-text code>
                {{ preview.target_video_path }}
              </n-text>
            </td>
          </tr>
          <tr v-if="preview.target_nfo_path">
            <td>
              <n-tag
                size="small"
                type="success"
              >
                Target NFO
              </n-tag>
            </td>
            <td>
              <n-text code>
                {{ preview.target_nfo_path }}
              </n-text>
            </td>
          </tr>
          <tr v-if="preview.target_cover_path">
            <td>
              <n-tag
                size="small"
                type="success"
              >
                Target Cover
              </n-tag>
            </td>
            <td>
              <n-text code>
                {{ preview.target_cover_path }}
              </n-text>
            </td>
          </tr>
        </tbody>
      </n-table>
    </div>
    <div v-else>
      <n-text depth="3">
        填写表单以预览任务路径
      </n-text>
    </div>
  </n-card>
</template>
