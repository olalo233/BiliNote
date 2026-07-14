import json

from app.routers import config as config_router
from app.gpt.prompt_builder import generate_base_prompt
from app.services.prompt_library_manager import PromptLibraryManager


def response_body(response):
    return json.loads(response.body)


def test_prompt_library_initializes_defaults_and_supports_upsert_delete(tmp_path, monkeypatch):
    manager = PromptLibraryManager(str(tmp_path / "config" / "prompts.json"))
    monkeypatch.setattr(config_router, "prompt_library_manager", manager)

    initial = response_body(config_router.list_prompts())
    assert {item["name"] for item in initial["data"]} >= {
        "做饭主厨",
        "技术教程 · 两段式",
        "播客访谈",
        "论文精读",
    }

    saved = response_body(
        config_router.save_prompt(config_router.PromptRequest(name="自定义", content="先看内容"))
    )
    assert saved["data"] == {"name": "自定义", "content": "先看内容"}
    assert response_body(config_router.list_prompts())["data"][0] == saved["data"]

    config_router.save_prompt(config_router.PromptRequest(name="自定义", content="已覆盖"))
    prompts = response_body(config_router.list_prompts())["data"]
    assert [item for item in prompts if item["name"] == "自定义"] == [
        {"name": "自定义", "content": "已覆盖"}
    ]

    assert response_body(config_router.delete_prompt("自定义"))["code"] == 0
    assert all(item["name"] != "自定义" for item in response_body(config_router.list_prompts())["data"])
    assert json.loads((tmp_path / "config" / "prompts.json").read_text()) == response_body(
        config_router.list_prompts()
    )["data"]


def test_saved_prompt_content_is_appended_to_final_prompt_builder(tmp_path, monkeypatch):
    manager = PromptLibraryManager(str(tmp_path / "config" / "prompts.json"))
    monkeypatch.setattr(config_router, "prompt_library_manager", manager)
    saved = response_body(
        config_router.save_prompt(
            config_router.PromptRequest(
                name="测试风格",
                content="输出必须分为结论和可执行步骤两部分。",
            )
        )
    )["data"]

    final_prompt = generate_base_prompt(
        title="测试视频",
        segment_text="视频正文",
        tags=[],
        extras=saved["content"],
    )

    assert final_prompt.endswith("\n输出必须分为结论和可执行步骤两部分。")
