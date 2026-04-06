"""
JSON Extraction — 健壮的 JSON 提取工具

从 LLM 响应中提取 JSON 对象。LLM 经常在 JSON 前后附加自然语言文本、
代码围栏标记或解释，本模块处理所有这些情况。

所有需要从 LLM 响应中解析 JSON 的模块都应使用此函数，
而不是自己做 text.index("{") 式的脆弱解析。
"""
import json
import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# 匹配 ```json ... ``` 或 ``` ... ``` 围栏块
_FENCED_JSON_RE = re.compile(
    r'```(?:json)?\s*\n?\s*(\{[\s\S]*?\})\s*\n?\s*```',
    re.DOTALL,
)

# 匹配从 { 开始到最后一个 } 的最大 JSON 候选
_BRACE_BLOCK_RE = re.compile(r'(\{[\s\S]*\})', re.DOTALL)


def extract_json(text: str) -> Optional[dict]:
    """
    从 LLM 响应文本中提取 JSON 对象。

    优先级：
    1. 如果文本本身就是合法 JSON → 直接解析
    2. 如果包含 ```json ... ``` 围栏 → 提取围栏内的 JSON
    3. 如果包含 { ... } → 找到最外层的大括号对，尝试解析
    4. 全部失败 → 返回 None

    Returns:
        解析后的 dict，或 None（解析失败时）
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # 策略 1：整个文本就是 JSON
    if text.startswith('{'):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # 策略 2：提取 ``` 围栏中的 JSON
    fence_match = _FENCED_JSON_RE.search(text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # 策略 3：提取平衡 { ... } 块，尝试每一个直到成功
    for candidate in _extract_all_balanced_braces(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # 策略 4：暴力匹配（regex 取最大 { ... } 块）
    brace_match = _BRACE_BLOCK_RE.search(text)
    if brace_match:
        try:
            return json.loads(brace_match.group(1))
        except json.JSONDecodeError:
            pass

    return None


def _extract_balanced_braces(text: str) -> Optional[str]:
    """
    提取第一个平衡的 { ... } 块。

    比 text.index('{') / text.rindex('}') 更健壮：
    - 处理嵌套大括号
    - 跳过字符串中的大括号
    - 跳过 JSON 前的自然语言文本中的 {
    """
    results = _extract_all_balanced_braces(text)
    return results[0] if results else None


def _extract_all_balanced_braces(text: str) -> list:
    """
    提取所有平衡的 { ... } 块。

    用于处理自然语言中的 {curly braces} 后面跟着真正 JSON 的情况：
    逐个尝试每个平衡块，直到找到合法 JSON。
    """
    results = []
    i = 0
    while i < len(text):
        if text[i] == '{':
            block = _extract_one_balanced(text, i)
            if block:
                results.append(block)
                i += len(block)
                continue
        i += 1
    return results


def _extract_one_balanced(text: str, start: int) -> Optional[str]:
    """从 start 位置提取一个平衡的 { ... } 块"""
    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        ch = text[i]

        if escape_next:
            escape_next = False
            continue

        if ch == '\\' and in_string:
            escape_next = True
            continue

        if ch == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    return None


def extract_json_or_text(text: str) -> Tuple[Optional[dict], str]:
    """
    提取 JSON，如果失败则返回原始文本。

    Returns:
        (parsed_dict, raw_text) — parsed_dict 为 None 表示解析失败
    """
    result = extract_json(text)
    return result, text
