import json

from app.routers import config as config_router
from app.services.cookie_manager import CookieConfigManager


def response_body(response):
    return json.loads(response.body)


def test_cookie_delete_route_is_idempotent(monkeypatch, tmp_path):
    manager = CookieConfigManager(str(tmp_path / 'downloader.json'))
    monkeypatch.setattr(config_router, 'cookie_manager', manager)

    config_router.update_cookie(
        config_router.CookieUpdateRequest(platform='youtube', cookie='a' * 12)
    )
    assert response_body(config_router.get_cookie('youtube'))['data']['cookie'] == 'a' * 12

    first_delete = response_body(config_router.delete_cookie('youtube'))
    second_delete = response_body(config_router.delete_cookie('youtube'))
    assert first_delete['code'] == 0
    assert second_delete['code'] == 0
    assert response_body(config_router.get_cookie('youtube'))['msg'] == '未找到Cookies'
    assert json.loads((tmp_path / 'downloader.json').read_text()) == {}
