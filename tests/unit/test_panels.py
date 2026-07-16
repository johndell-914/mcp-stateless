from mcp_stateless_demo.client.runner import ActResult, RowResult
from mcp_stateless_demo.ui import panels


def _sample(mode: str, ok: bool) -> ActResult:
    row = RowResult(
        n=1,
        tool="create_cart",
        ok=ok,
        served_by="inst-0" if ok else None,
        cart=[] if ok else None,
        error=None if ok else "Session not found",
    )
    return ActResult(mode=mode, rows=[row])


def test_results_table_ok() -> None:
    html = panels.render_results_table(_sample("auto", True))
    assert "create_cart" in html and "OK" in html and "inst-0" in html


def test_results_table_error() -> None:
    html = panels.render_results_table(_sample("legacy", False))
    assert "FAIL" in html and "Session not found" in html


def test_architecture_before_has_redis_and_sticky() -> None:
    html = panels.render_architecture("before", ["inst-0", "inst-1"])
    assert "Redis" in html and "Sticky LB" in html and "the tax" in html


def test_architecture_after_removes_them() -> None:
    html = panels.render_architecture("after", ["inst-0", "inst-1"])
    assert "Round-robin LB" in html and "removed" in html


def test_architecture_shows_down_instance() -> None:
    html = panels.render_architecture("after", ["inst-0", "inst-1"], down=["inst-0"])
    assert "down" in html


def test_whats_missing() -> None:
    html = panels.render_whats_missing(sticky=False, instances=10)
    assert "sticky routing" in html and "10" in html


def test_change_panel() -> None:
    html = panels.render_change_panel()
    assert "stateless_http=True" in html and "cart_token" in html
