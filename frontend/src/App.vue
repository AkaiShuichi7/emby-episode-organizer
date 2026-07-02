<template>
  <n-config-provider :theme="null">
    <n-message-provider>
      <n-dialog-provider>
        <n-loading-bar-provider>
          <main-layout />
        </n-loading-bar-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { NConfigProvider, NDialogProvider, NMessageProvider, NLoadingBarProvider } from 'naive-ui'
import MainLayout from '@/layouts/MainLayout.vue'
</script>
