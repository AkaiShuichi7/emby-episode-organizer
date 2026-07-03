/**
 * 路由配置
 * 包含主布局和各个功能页面的路由定义
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '仪表盘' }
  },
  {
    path: '/emby-settings',
    name: 'EmbySettings',
    component: () => import('@/views/EmbySettings.vue'),
    meta: { title: 'Emby 设置' }
  },
  {
    path: '/libraries',
    name: 'LibraryMapping',
    component: () => import('@/views/LibraryMapping.vue'),
    meta: { title: '媒体库映射' }
  },
  {
    path: '/series',
    name: 'SeriesConfig',
    component: () => import('@/views/SeriesConfig.vue'),
    meta: { title: '剧集配置' }
  },
  {
    path: '/organize',
    name: 'OrganizePage',
    component: () => import('@/views/OrganizePage.vue'),
    meta: { title: '整理入库' }
  },
  {
    path: '/tasks',
    name: 'TaskList',
    component: () => import('@/views/TaskList.vue'),
    meta: { title: '任务列表' }
  },
  {
    path: '/tasks/:id',
    name: 'TaskDetail',
    component: () => import('@/views/TaskDetail.vue'),
    meta: { title: '任务详情' }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
