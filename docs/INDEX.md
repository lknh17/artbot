# artbot 文档入口（唯一入口）

目标：**所有公众号发文/写作/上传/排版/故障排查**相关资料，统一在 `~/.openclaw/workspace/artbot/` 下管理。

> 使用建议（给 agent / 人）：
> - 不要把所有文档一次性塞进上下文。
> - 先从本入口定位需要的 1-2 份文档，再按需读取。

---

## A. 公众号发文（最常用）

- 发文流水线概览：见 `docs/USAGE.md`
- 配置项说明：见 `docs/CONFIG.md`
- 写作/排版常见问题：见 `docs/WRITING_FAQ.md`
- 故障排查：见 `docs/TROUBLESHOOTING.md`

## B. Web 面板与任务机制（chengong.net/artbot）

- 任务提交：Web 面板写入 `output/pending_task.json`
- worker：`worker/worker.py`（轮询 pending + 推草稿箱）

建议排查顺序：
1) `output/pending_task.json` 任务状态
2) `output/worker.log` / `output/notify.log` / `output/web.log`
3) 微信草稿箱是否出现（注意主体/账号）

## C. OpenClaw / 公众号部署&桥接文档（历史文档已归档到 artbot 下）

这些文档原先在 `~/.openclaw/workspace/docs/`，已移动到：`artbot/docs/workspace/`

- `docs/workspace/MP_WECHAT_GUIDE.md`
- `docs/workspace/MP_SERVER_GUIDE.md`
- `docs/workspace/WECHAT_BRIDGE_GUIDE.md`
- `docs/workspace/BROWSER_SETUP.md`
- `docs/workspace/DEPLOYMENT_GUIDE.md`
- `docs/workspace/DEPLOYMENT_COMPLETE.md`

## D. 图片生成/供应商

- `docs/IMAGE_PROVISIONERS.md`

---

## 快速搜索（少读文档，多定位）

在 `artbot/` 根目录执行：

```bash
grep -RIn "关键词" docs scripts web worker | head
```

推荐关键词：
- `errcode=40007`（media_id 无效）
- `create_draft` / `upload_image`
- `pending_task.json` / `worker.log`
