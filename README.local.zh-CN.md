# 本地二次开发：Rubric 双模型评分对比

这是公开项目 DeepEval 的本地扩展，不是从未公开的原创私有仓库，
不满足此次 RL env collection 的仓库来源要求。
来源、固定 commit、压缩包校验值见 `UPSTREAM_PROVENANCE.md`。
上游许可证 `LICENSE.md` 保留不变。初始来源是源码快照，没有完整上游 Git 历史；
本仓库新建的下游提交仅记录本项目实际发生的工作，不代表上游开发历史。

## 第一版做什么

读取已经由人工或其他流程完成的两份模型评分，按题号及评分点对比。
本工具不读取答案并自动评分，不调用大模型，不替代人工评审。

- 校验重复评分点、空评分、错列、无效编码、非数字和越界分数。
- 支持中文、UTF-8 BOM、CSV 引号与多行备注。
- 每题按权重归一化为百分制，再对各题等权平均。
- 输出总分、每题分数、逐点评分、加权贡献、差值、胜负和备注。
- 输入不完整时整体报错，不将漏评当作零分，不生成部分报告。
- 不覆盖输入或已有输出；CSV 模式无新增依赖，Excel 导入使用可选依赖。

## Windows 快速运行

在本项目目录运行。首次安装需要联网；之后评分计算不需要网络。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\run_rubric.ps1
.\run_rubric.ps1 -OutputPath .\my-report.json
```

已有评分文件的用法：

```powershell
.\run_rubric.ps1 -Scores C:\data\scores.csv -ModelA Baseline -ModelB Candidate -OutputPath C:\data\comparison.json
```

输出目录须已存在，输出文件须不存在。需要再次输出时使用新文件名。
本地启动脚本关闭上游遥测、更新查询、dotenv 自动加载和自动打开浏览器，
并启用上游配置只读模式；不自动加载 `.env` 文件、不执行模型调用。
DeepEval 初始化仍可能读取其现有本地配置；建议在本项目目录运行。
直接使用原生 CLI 时应自行设置这些环境变量。

原生命令：`deepeval rubric compare scores.csv --output report.json`。
输出扩展名须为 `.json` 或 `.xlsx`；后者生成 Excel 对比报告。
不传 `--output` 时输出 JSON 到标准输出；校验或文件错误退出码为 2。

## Excel 评分表导入

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-rubric-excel.txt
.\run_rubric.ps1 -Scores C:\data\scores.xlsx -Sheet Scores -OutputPath C:\data\comparison.json
```

Excel 第一行为与 CSV 相同的英文列名。只支持 `.xlsx`，不支持 `.xls` 或 `.xlsm`。
只有一个工作表时可省略 `-Sheet`，有多个工作表时必须明确选择。
题号、评分点编号和描述需存为文本，避免数值格式导致前导零丢失；分数可为数值。
公式单元格和 Excel 错误值会被拒绝，不读取可能过期的公式缓存，也不执行公式。
完全空白行忽略；部分填写的行仍做完整性检查。
文件限制为 50 MiB，解压总量不超过 200 MiB、10000 个 ZIP 条目，最多 100000 行数据。
导入只读，不会修改源工作簿；不解析外部链接。

## Excel 对比报告导出

安装 `requirements-rubric-excel.txt` 后，输出文件扩展名改为 `.xlsx` 即可：

```powershell
.\run_rubric.ps1 -OutputPath .\comparison.xlsx -Manifest .\examples\rubric\expected_criteria.csv
```

报告包含 `Summary` 汇总及来源、`Cases` 逐题对比、`Criteria` 逐点评分和加权贡献。
Excel 内保留数值精度，只在显示时使用两位小数。输出是计算结果快照，不是可重算模型；
修改评分后应重新运行比较，而不是修改报告。报告带筛选器，题号按文本保留前导零。
模型名、评分说明及备注都写成文本，不会作为 Excel 公式执行；超长文本和非法字符会报错，
不会静默截断。输出文件必须不存在；导出不会覆盖已有文件或源评分表。

## 完整评分点清单核对

当两个模型都缺少同一个评分点时，仅检查评分表无法发现遗漏。
现在可以从独立的题库/Rubric 定义提供完整清单，通过 `-Manifest` 核对：

```powershell
.\run_rubric.ps1 -Manifest .\examples\rubric\expected_criteria.csv
.\run_rubric.ps1 -Scores C:\data\scores.xlsx -Sheet Scores -Manifest C:\data\expected.csv -OutputPath C:\data\checked-report.json
```

清单是 UTF-8 CSV，仅两列 `case_id,criterion_id`，每个组合必须唯一且非空。
清单顺序不限；缺少任何条目、整题，或者评分表出现清单外条目，都报错且不生成报告。
错误信息列出缺失/额外条目数量及各自前 20 个编号，便于定位。
通过后报告新增 `manifest_check` 记录清单来源和核对数量，评分公式保持不变。
清单应来自独立的完整题库，不能从待检查的评分表直接生成，否则无法发现双方共同漏项。
不提供清单时沿用原逻辑，不宣称已验证评分点全集。

## CSV 格式与评分口径

必填列如下，可增加 `notes` 备注列；不接受其他列，避免列名拼错后静默丢失数据。

| 列 | 含义 |
| --- | --- |
| case_id | 题目编号，同一题的各评分点使用同一编号 |
| criterion_id | 评分点编号，与 case_id 组合后必须唯一 |
| criterion | 评分点内容，不得为空 |
| weight | 正数，相对权重，不要求合计等于 100 |
| max_score | 该评分点满分，必须为正数 |
| model_a_score | A 的已有评分，范围为 0 至 max_score |
| model_b_score | B 的已有评分，范围为 0 至 max_score |
| notes | 可选的已有评审理由或证据说明 |

```text
单题总分 = 100 × Σ[(权重 / 本题总权重) × (得分 / 满分)]
总体得分 = 各题总分的等权平均
差值 = A - B（百分点）
```

权重仅在同一题内有效，不跨题加权。不同题的评分点数可以不同。
同一 CSV 行里的 A/B 必须针对相同题目和同一评分标准。
不支持负权重、扣分型条目、N/A、漏评或多评审员汇总；此类数据须先明确口径。
不提供 `-Manifest` 时，不能发现双方同时漏掉的整题或评分点；提供独立完整清单后可核对编号全集。
清单仅核对编号，不核验评分标准内容、权重或人工判断本身是否正确。
胜负仅反映已有评分；不是统计显著性结论，也不计算评审员一致性系数。
平局容差为 1e-9 个百分点；计算不逐步取整。

`examples/rubric/paired_scores.csv` 是明确标注的合成演示数据，
不是用户真实评分或可提交的项目材料。预期 A=83.75、B=63.75，A 高 20 个百分点。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-rubric-excel.txt pytest-socket ruff
$env:DEEPEVAL_TELEMETRY_OPT_OUT='1'
$env:DEEPEVAL_DISABLE_DOTENV='1'
$env:DEEPEVAL_UPDATE_WARNING_OPT_IN='0'
$env:CONFIDENT_OPEN_BROWSER='0'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$rubricTests = (Get-ChildItem tests/test_core/test_rubric*.py).FullName
.\.venv\Scripts\python.exe -m pytest -o addopts= -p pytest_asyncio.plugin -p pytest_socket --disable-socket @rubricTests
$rubricModules = (Get-ChildItem deepeval/rubric*.py).FullName
.\.venv\Scripts\python.exe -m ruff check --target-version py39 @rubricModules deepeval/cli/rubric.py @rubricTests
```

测试覆盖计算口径、异常输入、UTF-8 中文、文件保护以及 CLI 禁网运行。
上游包含依赖外部服务和密钥的测试，不承诺在本地运行全部测试。
截至 2026-10-14，CSV、Excel 导入导出、完整清单与相邻 CLI、test-run 回归合计 **199 项通过**，
具体环境、命令范围、两条上游警告与验证限制见 `VERIFICATION.md`。

## 后续真实开发方向

1. 已支持固定列名的 XLSX 导入；下一步待取得实际交付模板后增加明确的列名映射，不猜测评分字段。
2. 已支持完整评分点编号清单；下一步待用户提供真实 Rubric 定义后扩展标准内容和权重版本核验。
3. 把单列 notes 扩展成 A/B 独立证据与来源位置；需先明确现有评审材料的证据格式。
4. 增加多评审员记录与一致性分析；当前只有两模型评分，没有评审员身份和重复标注。
5. 支持经用户确认的扣分项与不适用项政策；当前采用严格正权重规则，避免未经确认改变评分口径。
