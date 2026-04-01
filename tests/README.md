# Tests

## 目录结构

```
tests/
├── unit/              # 单元测试
│   └── test_new_components.py
├── integration/       # 集成测试
├── e2e/              # 端到端测试
│   └── test_e2e.py
├── test.py           # 基础测试
├── test_cli.py       # CLI 测试
├── test_cli_scenarios.py
└── test_cli_simple.py
```

## 运行测试

### 单元测试
```bash
python3 tests/unit/test_new_components.py
```

### CLI 测试
```bash
python3 tests/test_cli_simple.py
```

### 端到端测试
```bash
# 需要先启动后端
python3 tests/e2e/test_e2e.py
```
