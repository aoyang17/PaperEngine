# 用户手册

## 启动工作台

新建 topic 时，先从父目录启动浏览器工作台：

```bash
cd /path/to/PaperEngine
./bin/paper_engine start --base-dir <parent-dir> --host 0.0.0.0 --port 10005
```

然后在浏览器里填写 title、direction 和可选 seed paper。初始化 job 会让 Codex 调用 `paper_engine init`，不会读取父目录下其他 topic 作为模板。如果初始化失败，Create Topic 页面会在 Recent Jobs 和页面状态中显示真实错误。

如果 topic 已经存在，直接启动该 topic：

```bash
cd /path/to/PaperEngine
./bin/paper_engine start --root <topic> --host 0.0.0.0 --port 10005
```

浏览器访问：

```text
http://<server-ip>:10005/dashboard.html
```

浏览器工作台是默认用户界面。每个 topic 页面右侧都有一个持续存在的 Codex 操作员。外部 Codex 只作为高级维护或调试 fallback，不是日常操作 topic 的入口。

每个 topic 页面都有 Language、Codex model 和 Effort 选择框。自然语言消息、快捷命令和表格按钮都会进入同一个持续 Codex session。

新 session 默认使用 GPT-5.6 Sol 和 medium 推理强度。Terra 适合平衡性能与用量的日常任务，Luna 适合更快、更低成本的明确任务；GPT-5.5 和 Codex Spark 继续作为兼容及快速选项。浏览器只提供 low 到 xhigh，Max 和 Ultra 保留为高级 CLI 选项。

`paper_engine start` 默认会在本次 serverlet 进程里关闭 Codex runtime sandbox，因为 Docker user namespace sandbox 可能阻止 Codex 执行 `paper_engine`。安全边界仍然是 topic `policy.yml` 和 `paper_engine` CLI 的受控写入。只有在确认当前环境支持 Codex workspace sandbox、并且想调试 sandbox 行为时，才使用 `--codex-sandbox`。

## 用 CLI 初始化 Topic

脚本化或调试时，如果 title 和 direction 已经明确，可以直接用 CLI：

```bash
./bin/paper_engine init --base-dir <parent-dir> --title "<topic title>" --direction "<one paragraph research direction>"
```

高级维护或调试 fallback：如果你希望 Codex 帮忙整理粗略方向，可以把项目 README 附给 Codex，让它运行 `paper_engine init`。它不应该读取父目录下其他 topic 作为模板。

## 检索论文

在右侧 Codex 操作员里：

- 点击“检索 +30”做一次快速检索；或者
- 输入自然语言命令，例如“检索 50 篇高质量候选，并排除已有文献”。

Codex 会使用 topic skills 和 `paper_engine` 命令执行。切换页面后仍然是同一个 session。

## 筛选候选论文

在“文献列表 / List”页面：

- 这里只显示已入队候选；不满足本轮检索硬条件的搜索命中不会进入 All；
- 使用筛选、排序和摘要展开查看候选；
- 标记 Relevant、Irrelevant 或 Dismiss；
- 勾选候选后点击 Download Selected PDFs。

偏好标注是确定性动作，会立即写回候选状态并刷新页面。下载所选 PDF 也是确定性动作：serverlet 会先做 metadata enrich，再下载开放 PDF、入库 BibTeX，并自动刷新 HTML。检索、候选打分和复杂自然语言任务仍由右侧持续 Codex session 执行。

## 解读论文

在 Library 页面：

- 通过标题行的 PDF 或 Knowledge 链接查看结果；
- 勾选论文后点击 Read Paper。

Codex 会执行 topic 内的 paper-reading skill，写入结构化阅读结果，校验后重建 note/report。多选论文时，后台使用 `paper_engine read-many`：每篇论文都有独立 reader session 和独立 reviewer session。
阅读相关产物放在同一个 paper 目录下：`papers/<bibkey>/paper.pdf`、`parsed.md`、`visual_index.md`、`page_images/`、`note.md` 和 `reading_result.html`。Library 里的 Knowledge 链接会打开 `reading_result.html`。

如果已有解读质量不好，在 Codex 操作员里直接说：

```text
使用 paper_reread skill 重新解读 <bibkey>，覆盖旧 knowledge card，不要复用已有 deep_read/note/html 作为证据。
```

`paper_reread` 会先把旧 reading artifacts 当成待覆盖目标，而不是证据来源；多论文重读走 `read-many`，单论文重读仍由 `paper_deep_read` 生成新的 `source_map.json`、`note_plan.json` 和 `deep_read.json`，并运行 validate、quality-audit 和 rebuild-note。

如果只想验证下载链路，可以在已有候选上勾选一篇并点击 Download Selected PDFs；成功后 Library 会出现该文献，标题旁会有 PDF 链接。

## 从另一个 Topic 导入单篇论文

必须明确给出源 topic 路径和源 bibkey：

```bash
./bin/paper_engine library import-from-topic --root <target-topic> --source-root <source-topic> --source-bibkey <bibkey> --json
```

如果只知道标题，Codex 会先在这个明确指定的源 topic 中运行 `library find`，只有恰好匹配一篇时才继续。命令会清楚报告 `imported`、`already_exists` 或 skipped/error。导入后目标 topic 会有一条 `in_library`、`relevant` 的 candidate，但不会立刻刷新 `preferences.yml`。此功能没有浏览器按钮，也没有批量导入接口。

## 检查状态

日常检查优先点击 Codex 操作员里的“工作状态”。调试时可用：

```bash
./bin/paper_engine status --root <topic> --json
./bin/paper_engine bib check --root <topic>
./bin/paper_engine pdf check --root <topic>
./bin/paper_engine html build --root <topic>
```

## 边界规则

不要复制其他 topic 作为模板。初始化模板已经内置在工具里。除非你明确要求迁移、比较或引用某个路径，否则父目录下其他 topic 都不属于当前任务上下文。
