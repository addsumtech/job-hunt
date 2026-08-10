# discover：把已采集的偏好真正送进 adapter 的筛选条件

日期：2026-08-10
状态：已确认方向，待实施（排在计划 4 之后）

---

## 1. 问题

不是「缺功能」，是**已经问到的偏好没有被送进搜索**——这比缺功能糟，因为输出看起来就像是按用户条件搜的。

`references/discovery-sources.md` 里每个平台的搜索命令带的是**写死的示例值**：

```
boss     … --experience 3-5年 --degree 硕士 …
linkedin … --experience-level mid-senior --job-type full-time …
```

而 `search-preferences.yaml` 已经问了 8 个字段（`target_market` `locations` `seniority`
`work_models` `languages` `salary_floor` `avoid` `experience_track`）。用户答"应届"，命令照发
`3-5年 --degree 硕士`。

## 2. adapter 侧真实可用的条件

2026-08-10 用 `opencli <site> search --help` 实测，不是读文档：

| 站点 | 可用筛选 |
|---|---|
| `51job` | `--area` `--salary` `--experience` `--degree` `--companyType` `--companySize` `--sort` `--page` `--limit` |
| `boss` | `--city` `--experience` `--degree` `--salary` `--industry` `--jobType` `--page` `--limit` |
| `linkedin` | `--location` `--experience-level` `--job-type` `--date-posted` `--remote` `--company` `--details` `--start` `--limit` |
| `indeed` | `--location` `--fromage` `--sort` `--start` `--limit` |

各站取值词表不同且必须逐字匹配（boss 的 `1-3年`/`3-5年`、51job 的 `10-15k`/`1-1.5万`、
linkedin 的 `mid-senior`），所以映射必须是查表，不能是格式化字符串。

## 3. 决定

### D1 — 映射是代码，不是 prompt

不让模型临场想筛选值。理由和这个 skill 一贯防的是同一件事：模型编一个 `--salary 20-30K`
出来，输出完全正常，而用户从没说过这个数。

新建 `scripts/search_conditions.py`，一张 `preferences × site → flags` 的查表，带测试。
`seniority: mid → boss --experience 3-5年` 是一个可以被钉住的事实。

### D2 — 硬条件筛选，软条件标注

**这是本设计的核心取舍，也是最容易做错的地方。**

条件收得越紧，**假阴性越危险且不可见**：`--degree 硕士` 会把一个写着「本科及以上、硕士优先」
的合适岗位从结果里直接抹掉，而用户永远不会知道它存在过。搜索结果里没有的东西，没有任何闸门
能报告。

| 类别 | 处理 | 为什么 |
|---|---|---|
| **硬条件**：城市 / 职级 | 传给 adapter | 不匹配就是真的不相关，收窄是净收益 |
| **新鲜度**：`--date-posted week` / `--fromage 7` | 传给 adapter | 过期岗位是纯噪音，没有假阴性风险 |
| **软条件**：薪资 / 学历 / 公司性质 / 规模 | **默认不传**，拿回结果后**标注** | 让用户看见「这条低于你的薪资下限」，而不是让它消失 |
| **`avoid` 列表** | **永不作为搜索参数**，只做收到后过滤 + 写明理由 | 没有平台有「排除外包」的 flag；塞进关键词会连正常岗位一起打掉 |

软条件标注写进 shortlist 行，成为排序依据之一，但不删除行。

### D3 — 不支持的条件必须显式记录

indeed 没有薪资筛选。那么来源报告里必须写明「本站未按薪资下限过滤」。

否则用户会以为 30 条结果都过了薪资线——这正是本仓库反复出现的那类失败：**没做过的检查
看起来和通过了的检查一模一样**。

机制：`check_shortlist.py` 增加 `UNAPPLIED_CONDITION_UNRECORDED`——`brief.yaml` 里声明了某个
条件、而某站的来源报告既没说「已按此筛选」也没说「本站不支持」时判死。

## 4. 实施要点

1. `scripts/search_conditions.py`：`flags_for(site, prefs) -> (list[str], list[str])`
   返回（要传的 flag，本站不支持而被降级为标注的条件名）。纯函数，无 IO。
2. 每个站的取值词表逐字来自 `opencli <site> search --help`，并在测试里断言词表成员
   ——取值漂了要在测试里响，不要在搜索结果里静默失配。
3. `references/discovery-sources.md` 的写死示例值换成占位符，并写明哪些由映射填、哪些
   刻意不填。
4. `brief.yaml` 记录本轮**实际传出去的** flag 和**被降级为标注的**条件，这样这一轮可复现，
   也让 D3 的闸门有东西可查。
5. 软条件标注进 `shortlist.yaml` 行，例如 `below_salary_floor: true`，`shortlist.md` 里
   人可读地写出来。

## 5. 不做的

- 不让模型生成筛选值（D1）。
- 不把 `avoid` 变成搜索关键词（D2）。
- 不为了「结果更少更精准」而默认收紧软条件——少而错的结果比多而带标注的结果糟，
  因为前者的错误不可见。
