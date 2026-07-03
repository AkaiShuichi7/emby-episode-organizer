
## F1 Plan Compliance Audit
- Must Have 2 FAIL: commit endpoint awaits commit_to_target directly; no FastAPI BackgroundTasks/add_task/asyncio.create_task. mover uses .tmp + os.rename, but commit is not background async.
- Must Have 4 FAIL: URL cover download enforces 20MB/http(s), but local UploadFile cover path writes await file.read() without 20MB limit.
- Evidence coverage issue: 30 evidence files exist, but distinct task prefixes cover 27/30; missing task-22, task-23, task-28.

## F3 Real Manual QA - 2026-07-02
- Console error 3 个：favicon.ico 404、/api/v1/settings/emby 404、/api/v1/tasks/42 404。按验收规则 console error 存在，最终 REJECT。
- /settings 直连只显示默认标题；通过导航进入实际路由 /emby-settings 后表单可见。
