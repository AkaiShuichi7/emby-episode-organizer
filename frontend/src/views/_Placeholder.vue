<template>
  <div class="placeholder-view">
    <n-empty description="开发中" />
  </div>
</template>

<script setup lang="ts">
import { NEmpty } from 'naive-ui'
</script>

<style scoped>
.placeholder-view {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  min-height: 400px;
}
</style>
