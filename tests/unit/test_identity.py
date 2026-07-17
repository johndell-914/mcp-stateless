"""The boot-id identity helper: fixed services keep clean names, scale services opt in."""

from __future__ import annotations

from mcp_stateless_demo.server.identity import BOOT_ID, resolve_instance_name


def test_fixed_service_keeps_clean_name() -> None:
    assert resolve_instance_name("legacy-a", append_boot_id=False) == "legacy-a"


def test_scale_service_appends_boot_id() -> None:
    name = resolve_instance_name("scale", append_boot_id=True)
    assert name == f"scale-{BOOT_ID}"
    assert name.startswith("scale-")


def test_boot_id_is_short_and_stable() -> None:
    assert len(BOOT_ID) == 4
    # Stable within a process: two reads return the same value.
    from mcp_stateless_demo.server.identity import BOOT_ID as again

    assert BOOT_ID == again
