from pathlib import Path


STATIC_DIR = Path(__file__).parents[1] / "physical_agent" / "gui" / "static"


def _asset(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_gui_index_keeps_required_dom_contract():
    html = _asset("index.html")

    for selector in [
        'id="chat-input"',
        'id="send-chat"',
        'id="chat-planner"',
        'id="chat-auto-step"',
        'id="timeline"',
        'id="world-robots"',
        'id="world-objects"',
        'id="integrate-source"',
        'id="integrate-mode"',
        'id="integrate"',
    ]:
        assert selector in html


def test_gui_index_loads_static_assets_in_order():
    html = _asset("index.html")

    expected = [
        "/static/styles.css",
        "/static/i18n.js",
        "/static/api.js",
        "/static/render.js",
        "/static/app.js",
    ]
    positions = [html.index(path) for path in expected]
    assert positions == sorted(positions)


def test_gui_app_keeps_enter_to_send_contract():
    app_js = _asset("app.js")

    assert 'event.key === "Enter"' in app_js
    assert "!event.shiftKey" in app_js
    assert "event.preventDefault()" in app_js
    assert "sendChat()" in app_js


def test_gui_i18n_keeps_chinese_labels():
    i18n_js = _asset("i18n.js")

    for text in ["硬件接入", "发送", "执行时间线", "世界状态", "生成驱动"]:
        assert text in i18n_js


def test_gui_renderer_keeps_major_render_entrypoints():
    render_js = _asset("render.js")

    for name in [
        "createGuiRenderer",
        "renderChat",
        "renderWorld",
        "renderTimeline",
        "renderIntegrationResult",
    ]:
        assert name in render_js
