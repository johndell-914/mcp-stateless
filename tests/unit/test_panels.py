from mcp_stateless_demo.client.runner import ActResult, RowResult
from mcp_stateless_demo.cloud.logs import LogLine, LogProof
from mcp_stateless_demo.ui import panels


def _sample(mode: str, ok: bool) -> ActResult:
    row = RowResult(
        n=1,
        tool="create_cart",
        ok=ok,
        served_by="legacy-a" if ok else None,
        cart=[] if ok else None,
        error=None if ok else "Session not found",
    )
    return ActResult(mode=mode, rows=[row])


def test_results_table_ok() -> None:
    html = panels.render_results_table(_sample("auto", True))
    assert "create_cart" in html and "OK" in html and "legacy-a" in html


def test_results_table_error() -> None:
    html = panels.render_results_table(_sample("legacy", False))
    assert "FAIL" in html and "Session not found" in html


def test_scenario_has_key_phrase_and_agent_framing() -> None:
    html = panels.render_scenario()
    assert "50,000 users" in html and "create_cart()" in html


def test_stepper_marks_active() -> None:
    html = panels.render_stepper(2)
    assert "The tax" in html and "Prove at scale" in html


def test_narrative_beats() -> None:
    assert "Session not found" in panels.render_narrative("scale")
    assert "Delete the" in panels.render_narrative("stateless")


def test_architecture_before_sticky_shows_tax_and_store() -> None:
    html = panels.render_architecture("before", ["legacy-a", "legacy-b"], sticky=True, store=True)
    assert "session store" in html and "tax" in html and "Sticky gateway" in html


def test_architecture_before_plain_is_round_robin() -> None:
    html = panels.render_architecture("before", ["legacy-a", "legacy-b"])
    assert "Round-robin LB" in html and "session store" not in html


def test_architecture_after_removes_them() -> None:
    html = panels.render_architecture("after", ["modern-a", "modern-b"])
    assert "removed" in html and "no sticky" in html


def test_architecture_scale_shows_autoscaling() -> None:
    html = panels.render_architecture(
        "scale", ["scale-1", "scale-2", "scale-3"], served=["scale-1"], scaling=True
    )
    assert "autoscaling" in html and "3 instances" in html


def test_architecture_shows_recycled_instance() -> None:
    html = panels.render_architecture(
        "before", ["legacy-a", "legacy-b"], sticky=True, down=["legacy-a"]
    )
    assert "recycled" in html


def test_blast_summary() -> None:
    html = panels.render_blast_summary(60, 60, ["scale-a", "scale-b"])
    assert "60/60" in html and "2</b> autoscaled" in html


def test_log_proof_states() -> None:
    assert "run a step" in panels.render_log_proof(None, headline="Logs")
    bad = LogProof(ok=False, service="s", lines=[], instances=[], error="no creds")
    assert "unavailable" in panels.render_log_proof(bad, headline="Logs")
    good = LogProof(
        ok=True,
        service="s",
        lines=[LogLine(ts="00:00:01", instance="abc123", text="POST /mcp 200")],
        instances=["abc123", "def456"],
    )
    html = panels.render_log_proof(good, headline="Logs")
    assert "2 distinct instances" in html and "POST /mcp" in html


def test_change_panel() -> None:
    html = panels.render_change_panel()
    assert "stateless_http=True" in html and "cart_token" in html
