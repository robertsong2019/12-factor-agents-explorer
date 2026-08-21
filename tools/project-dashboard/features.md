# project-dashboard features.md

Scan a workspace of projects → unified health/status dashboard (Markdown/JSON).

## F1 扫描与识别
- [x] 项目识别（package.json/pyproject/Cargo/go.mod/.git/Makefile 等 indicators）F1
- [x] 忽略隐藏目录与 IGNORE_DIRS（node_modules/.git 等）F1
- [x] 语言检测（按扩展名计数取最大）F1

## F2 Git 状态
- [x] clean/dirty/untracked 三态检测（porcelain）F1

## F3 测试检测（真实性修复 2026-08-21）
- [x] 配置文件直接证明：pytest.ini/conftest.py/jest.config/mocharc/vitest F2
- [x] pyproject.toml 仅当内含 pytest 配置才算 F2（修复：打包-only pyproject 曾白送 has_tests）
- [x] Cargo.toml 需伴随 tests/ 目录 F2（修复：裸 Cargo 曾白送）
- [x] go.mod 需真实 *_test.go 文件（os.walk）F2（修复：裸 go.mod 曾白送）
- [x] 通用 tests/test/__tests__/spec 目录 → generic F1

## F4 文档与代码质量
- [x] 根目录 doc 文件清点（README/CHANGELOG/CONTRIBUTING 等）F1
- [x] TODO/FIXME 计数（大小写不敏感）F1
- [x] 文件数/行数/last_modified 统计 F1
- [x] 依赖计数（npm/pip/cargo/go）F1

## F5 健康分（0-100）
- [x] docs 30 / tests 25 / git 20 / todo 15 / activity 10 F1

## F6 输出与 CLI
- [x] Markdown 仪表盘（概览表+项目表+Needs Attention+Recently Active）F1
- [x] JSON 输出（summary+projects，按健康分降序）F1
- [x] --min-health 过滤 F1
- [x] -o 文件输出 F1
- [x] workspace 不存在 → 友好报错 exit 1（修复：曾直接 traceback）F2

## 测试
- tests/test_dashboard.py — hermetic（tmp fixtures + 真实 git init/commit），11 tests，`python3 -m pytest tests/ -q`
