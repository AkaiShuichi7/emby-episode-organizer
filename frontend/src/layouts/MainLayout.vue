<template>
  <n-layout has-sider class="main-layout">
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="240"
      show-trigger
    >
      <div class="logo">
        <span class="logo-text">Emby Organizer</span>
      </div>
      <n-menu
        :options="menuOptions"
        :value="activeKey"
        @update:value="handleMenuClick"
      />
    </n-layout-sider>
    <n-layout>
      <n-layout-header bordered class="header">
        <div class="header-content">
          <h2 class="page-title">{{ currentRouteTitle }}</h2>
          <div class="status-indicator">
            <span class="status-dot" :class="{ 'is-connected': isEmbyConnected }"></span>
            <span class="status-text">{{ isEmbyConnected ? 'Emby 已连接' : 'Emby 未连接' }}</span>
          </div>
        </div>
      </n-layout-header>
      <n-layout-content class="content">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
/**
 * 主布局组件
 * 包含左侧导航菜单、顶部状态栏和主内容区
 */
import { computed, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NMenu } from 'naive-ui'
import type { MenuOption } from 'naive-ui'
import { useSettingsStore } from '@/stores/settings'

const route = useRoute()
const router = useRouter()
const settingsStore = useSettingsStore()

const activeKey = computed(() => route.path)
const currentRouteTitle = computed(() => route.meta.title as string || 'Emby Episode Organizer')

const isEmbyConnected = computed(() => {
  return !!(settingsStore.embyConfig?.url && settingsStore.embyConfig?.apiKeySet)
})

const menuOptions: MenuOption[] = [
  {
    label: '仪表盘',
    key: '/'
  },
  {
    label: 'Emby 设置',
    key: '/emby-settings'
  },
  {
    label: '媒体库映射',
    key: '/libraries'
  },
  {
    label: '剧集配置',
    key: '/series'
  },
  {
    label: '整理入库',
    key: '/organize'
  },
  {
    label: '任务列表',
    key: '/tasks'
  }
]

const handleMenuClick = (key: string) => {
  router.push(key)
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid var(--n-border-color);
}

.logo-text {
  font-size: 18px;
  font-weight: bold;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 0 16px;
}

.header {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 24px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #d03050; /* error color */
}

.status-dot.is-connected {
  background-color: #18a058; /* success color */
}

.content {
  padding: 24px;
  background-color: var(--n-color-modal);
}
</style>
