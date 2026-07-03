# frontend

Emby Episode Organizer 前端应用。

## 技术栈

- 构建工具：Vite 5
- 框架：Vue 3 (Composition API)
- 语言：TypeScript
- UI 组件库：Naive UI
- 状态管理：Pinia
- 路由：Vue Router

## 目录结构

- `src/api`: API 客户端与类型定义
- `src/components`: 复用组件（NFO 编辑器、封面管理、文件浏览器等）
- `src/views`: 页面组件（整理向导、任务列表、设置等）
- `src/stores`: Pinia 状态存储
- `src/router`: 路由配置
- `src/layouts`: 页面布局

## 开发命令

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产产物
npm run build

# 运行单元测试
npm run test:unit -- --run

# 代码风格检查
npm run lint

# 代码格式化
npm run format
```

## 开发约定

- 代理说明：`vite.config.ts` 配置了 `/api` 自动代理到 `http://localhost:8899`。
- UI 规范：Naive UI 组件统一通过 `NConfigProvider` 包裹，确保全局样式一致。
- 类型安全：使用 `openapi-typescript` 根据后端接口自动生成 API 类型。
