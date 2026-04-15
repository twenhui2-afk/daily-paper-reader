## 当前任务

- 任务：修复论文页两个新回归问题：
  - 标题栏右侧中文标题空白 / 错位；
  - 中文一句话总结、摘要、速览在回退路径下被生成成同一套泛化空话。
- 本质问题：
  - 当前页面在 `title_zh` 缺失时没有正确处理标题栏展示。
  - `src/6.generate_docs.py` 的启发式回退过于模板化，导致不同区块复用同一批句子，信息密度很低。
- 这是我的假设：
  - 当前目标仓库是 `/Users/nicai/Documents/daily-paper-reader`。
  - 用户希望标题栏保留双语结构，其中右侧是中文标题；如果没有中文标题，也不能留出误导性的空白栏。

## 边界条件

- 只做最小必要修改，不改检索、排序、聊天链路。
- 优先改论文页展示和生成内容，不引入新服务或新配置项。

## Done when

- 论文页标题栏的左右内容和语义一致：
  - 左侧保留英文原题；
  - 右侧显示中文标题；若缺失中文标题，不出现误导性的空白占位。
- 中文一句话总结、摘要、速览不再全都复用同一套模板句。
- 对于无 LLM 的回退场景，中文内容仍能从摘要里提取出真实信息，而不是“目标任务 / 新方法 / 正向结果”这类泛化表述。
- 至少对当前报错样例文档完成一轮回填验证。
- 有对应验证，至少覆盖文档生成逻辑。

## 当前状态

- 已完成代码修复：
  - `app/docsify-plugin.js` 的标题栏改成“左英文原题、右中文标题”；如果只有一个标题，会直接显示单栏，不再留半边空白。
  - `src/6.generate_docs.py` 的启发式回退不再输出“目标任务 / 新方法 / 正向结果”模板句，而是从摘要里提取不同句子生成 TLDR、摘要、速览。
  - `should_refresh_existing_markdown()` 现在会识别旧的模板化内容，后续回填时会自动刷新。
- 已完成验证：
  - `python -m py_compile src/6.generate_docs.py`
  - `node --check app/docsify-plugin.js`
  - `python -m unittest tests.test_generate_docs_meta_parse`
- 已回填样例文档：
  - `/Users/nicai/Documents/daily-paper-reader/docs/202604/14/2604.10574v1-tiles-from-projections-of-the-root-and-weight-lattices-of-an.md`

## 下一步

1. 提交并推送到远端 `main`，让 GitHub Pages 重新构建。
2. 用户刷新站点，验证标题栏和样例页面是否符合预期。
