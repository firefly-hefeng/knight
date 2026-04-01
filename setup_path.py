#!/usr/bin/env python3
"""Knight 通用启动器 - 自动处理路径"""
import sys
import os

# 获取knight目录的绝对路径
KNIGHT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(KNIGHT_DIR)

# 添加到Python路径
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

# 现在可以导入knight模块
__all__ = ['setup_path']

def setup_path():
    """设置Python路径"""
    return KNIGHT_DIR, PARENT_DIR
