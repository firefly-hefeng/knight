# Knight System - 快速启动

## 前置要求

```bash
# 安装Claude Code
npm install -g @anthropic-ai/claude-code
```

## 使用方式

### 1. 基础测试
```bash
cd /path/to/knight
python3 test.py
```

### 2. 自定义使用
```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knight.core import AgentPool, StateManager, TaskCoordinator
# 使用模块...
```

## 路径说明
- 所有脚本自动处理路径
- 无需手动配置PYTHONPATH
- 支持任意目录运行
