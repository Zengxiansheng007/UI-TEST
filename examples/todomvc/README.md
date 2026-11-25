# TodoMVC 项目入口

收到源用例 ID 后，从 `asset-paths.json` 取该用例的 `branch_root`。该目录的 `source/source-case.json` 是原业务要求。`regression-runners` 存放对应的 pytest 节点，`ui-test.project.yaml` 给出项目环境。以下命令在本目录使用本机已有 Python 与依赖。

```powershell
$case = 'TODO-P0-002'
$branch = (Get-Content asset-paths.json -Raw -Encoding utf8 | ConvertFrom-Json).$case.branch_root
$source = Get-Content (Join-Path $branch 'source/source-case.json') -Raw -Encoding utf8 | ConvertFrom-Json
$node = 'regression-runners/test_' + $case.ToLowerInvariant().Replace('-', '_') + '.py'
$run = 'TODO-' + [guid]::NewGuid().ToString('N')

$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m pytest -q $node --ui-run-id $run --ui-r2-approved --ui-execution-origin codex-cli
```

`--ui-r2-approved` 表示本次任务已授权在公开 TodoMVC 可见页面执行源用例规定的操作。每次新执行分配新 ID。已有运行的结果和回执按原 ID 读回。

```powershell
$roots = @('运行', (Join-Path $branch 'runs'), 'runs') | Where-Object { Test-Path -LiteralPath $_ }
$receipts = Get-ChildItem -LiteralPath $roots -Filter finalization-commit.json -Recurse
$match = @($receipts | Where-Object { (Get-Content $_.FullName -Raw -Encoding utf8 | ConvertFrom-Json).run_id -eq $run })
if ($match.Count -ne 1) { throw '未能定位唯一正式提交' }
$root = $match[0].Directory.Parent.FullName
$final = Join-Path $root 'finalization'
$commit = Get-Content (Join-Path $final 'finalization-commit.json') -Raw -Encoding utf8 | ConvertFrom-Json
$result = Get-Content (Join-Path $final $commit.run_result_ref) -Raw -Encoding utf8 | ConvertFrom-Json
$result.step_results | ConvertTo-Json -Depth 6
```

逐步核对 V5 的状态、截图和 evidence_refs。使用明细中的 `asset_id/version/sha256` 指向本次实际入口，`actual` 为当前页面读数，`experiences` 关联采用策略、候选和限定启用决定。向请求方返回本次 run ID、原断言观察值、实际资产版本、复用明细及 V5 路径。如提交结果未知，读回该次预算和证据。

The headed Windows example requires Python 3.11, pytest-playwright, Playwright Chromium, and the core Skill dependencies. Run from this directory. Public case inputs are included under cases/.

复制正式样例时请保留整个 `examples/todomvc/` 目录，包括与 `project_runtime.py` 同级的 `window_observation.py`。窗口观察使用当前 Python 解释器及 Windows 原生 API，核对当前 runner、Playwright 驱动、浏览器进程与可见窗口的归属。两个运行即使打开同名页面也分别记录 HWND。探测失败会在首次业务提交前终止。
