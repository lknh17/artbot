# Topic Banks

每个账号可以绑定一个或多个“选题库”（topic bank）。

约定：

- `config/topic_banks/<account_id>.json`：该账号的选题库（可维护多栏目）
- Web 面板可直接查看/编辑并保存。

字段建议：

```json
{
  "account_id": "mp_chaguan",
  "version": 1,
  "updated_at": "2026-02-27T00:00:00+08:00",
  "banks": [
    {
      "id": "marriage",
      "name": "婚姻沟通",
      "problems": ["..."],
      "scenes": ["..."],
      "conflicts": ["..."],
      "actions": ["..."],
      "notes": "optional"
    }
  ]
}
```
