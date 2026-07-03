<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NButton, NCard, NForm, NFormItem, NInput, NSpace, NSwitch, useMessage } from 'naive-ui'
import { useSettingsStore } from '@/stores/settings'

const MASKED_API_KEY = '************'
const MASKED_API_KEY_PREFIX = 'xxxx****'

const message = useMessage()
const settingsStore = useSettingsStore()

const serverUrl = ref('')
const apiKey = ref('')
const autoRefresh = ref(false)

const isTesting = ref(false)
const isSaving = ref(false)

onMounted(async () => {
  await settingsStore.loadSettings()
  serverUrl.value = (settingsStore.allSettings['emby.server_url'] as string) || ''
  const savedKey = settingsStore.allSettings['emby.api_key'] as string
  if (savedKey?.startsWith(MASKED_API_KEY_PREFIX)) {
    apiKey.value = savedKey
  }
  autoRefresh.value = (settingsStore.allSettings['emby.auto_refresh'] as boolean) || false
})

async function handleTest() {
  const trimmedApiKey = apiKey.value.trim()

  if (!serverUrl.value || !trimmedApiKey) {
    message.warning('请先填写服务器地址和 API Key')
    return
  }
  
  isTesting.value = true
  const result = await settingsStore.testEmbyConnection({
    server_url: serverUrl.value,
    api_key: trimmedApiKey
  })
  isTesting.value = false

  if (result?.success) {
    message.success(result.message || '连接成功')
  } else {
    message.error(result?.message || settingsStore.error || '连接失败')
  }
}

async function handleSave() {
  if (!serverUrl.value) {
    message.warning('请填写服务器地址')
    return
  }

  isSaving.value = true
  const payload: Record<string, unknown> = {
    'emby.server_url': serverUrl.value,
    'emby.auto_refresh': autoRefresh.value
  }

  const trimmedApiKey = apiKey.value.trim()
  if (trimmedApiKey && trimmedApiKey !== MASKED_API_KEY && !trimmedApiKey.startsWith(MASKED_API_KEY_PREFIX)) {
    payload['emby.api_key'] = trimmedApiKey
  }

  const result = await settingsStore.saveSettings(payload)
  isSaving.value = false

  if (result) {
    message.success('保存成功')
  } else {
    message.error(settingsStore.error || '保存失败')
  }
}
</script>

<template>
  <div class="emby-settings">
    <n-card title="Emby 服务器设置">
      <n-form
        label-placement="left"
        label-width="120"
      >
        <n-form-item label="服务器地址">
          <n-input
            v-model:value="serverUrl"
            placeholder="http://192.168.1.100:8096"
          />
        </n-form-item>
        <n-form-item label="API Key">
          <n-input 
            v-model:value="apiKey" 
            type="password" 
            show-password-on="click"
            :placeholder="MASKED_API_KEY" 
          />
        </n-form-item>
        <n-form-item label="自动刷新">
          <n-switch v-model:value="autoRefresh" />
          <span class="ml-2 text-gray-500">整理完成后自动触发 Emby 媒体库扫描</span>
        </n-form-item>
        <n-form-item>
          <n-space>
            <n-button
              type="primary"
              :loading="isSaving"
              @click="handleSave"
            >
              保存
            </n-button>
            <n-button
              :loading="isTesting"
              @click="handleTest"
            >
              测试连接
            </n-button>
          </n-space>
        </n-form-item>
      </n-form>
    </n-card>
  </div>
</template>

<style scoped>
.emby-settings {
  max-width: 800px;
  margin: 0 auto;
}
.ml-2 {
  margin-left: 8px;
}
.text-gray-500 {
  color: #6b7280;
}
</style>
