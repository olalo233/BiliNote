"""Persistent reusable prompt templates for the note extras field."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_PROMPTS: list[dict[str, str]] = [
    {
        "name": "做饭主厨",
        "content": """# Role
你是一名经验丰富、表达清晰的明星主厨。

# Instructions
请把视频中的食材、用量、火候和操作顺序整理成可复现的菜谱；指出关键技巧、常见失败原因和可替代方案。不要补写视频没有提到的具体信息。""",
    },
    {
        "name": "技术教程 · 两段式",
        "content": """# Role
你是一名严谨的技术教程作者。

# Instructions
输出分为两部分：第一部分用简洁语言说明概念、目标和适用场景；第二部分按前置条件、操作步骤、验证结果和常见问题给出可执行教程。保留命令、参数和重要限制，不要虚构运行结果。""",
    },
    {
        "name": "播客访谈",
        "content": """# Role
你是一名擅长提炼对话的播客编辑。

# Instructions
围绕讨论主题、嘉宾观点、论据、分歧和可执行启发组织笔记。区分主持人与嘉宾的观点；不确定的内容标注为不确定，不要把闲聊或推测写成事实。""",
    },
    {
        "name": "论文精读",
        "content": """# Role
你是一名面向研究者的论文阅读助理。

# Instructions
按研究问题、背景、方法、数据、实验、结果、局限和可复现线索整理内容。保留术语、指标与因果边界；区分论文明确结论、作者解释和你的归纳，不要补造论文未提供的数据。""",
    },
]


class PromptLibraryManager:
    """Read and write the prompt list on every operation for volume persistence."""

    def __init__(self, filepath: str = "config/prompts.json"):
        self.path = Path(filepath)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(DEFAULT_PROMPTS)

    def _read(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        try:
            raw: Any = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("读取提示词库失败，按空库处理: %s", exc)
            return []
        if not isinstance(raw, list):
            logger.warning("提示词库格式不是列表，按空库处理")
            return []
        prompts: list[dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            content = item.get("content")
            if isinstance(name, str) and name.strip() and isinstance(content, str):
                prompts.append({"name": name, "content": content})
        return prompts

    def _write(self, prompts: list[dict[str, str]]) -> None:
        self.path.write_text(
            json.dumps(prompts, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def list(self) -> list[dict[str, str]]:
        return self._read()

    def upsert(self, name: str, content: str) -> dict[str, str]:
        name = name.strip()
        if not name:
            raise ValueError("模板名称不能为空")
        prompts = [prompt for prompt in self._read() if prompt["name"] != name]
        prompt = {"name": name, "content": content}
        prompts.insert(0, prompt)
        self._write(prompts)
        return prompt

    def delete(self, name: str) -> bool:
        prompts = self._read()
        remaining = [prompt for prompt in prompts if prompt["name"] != name]
        if len(remaining) == len(prompts):
            return False
        self._write(remaining)
        return True
