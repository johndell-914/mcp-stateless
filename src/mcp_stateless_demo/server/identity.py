"""Per-process instance identity.

A Cloud Run *service* has one ``INSTANCE_ID`` env var, but an autoscaling service runs
that image as many *instances* (processes). To let the UI show that a burst of requests
was spread across distinct instances, each process stamps a short boot id generated once
at import time. It also lets us correlate a UI row with a Cloud Run ``labels.instanceId``
log line (both are printed at startup).
"""

from __future__ import annotations

import uuid

# Generated once per process (import happens once). Distinct per Cloud Run instance.
BOOT_ID: str = uuid.uuid4().hex[:4]


def resolve_instance_name(instance_id: str, *, append_boot_id: bool) -> str:
    """The name stamped as ``served_by``.

    Fixed single-instance services keep their clean name; an autoscaling service opts in
    to the boot suffix so its instances are told apart.
    """
    return f"{instance_id}-{BOOT_ID}" if append_boot_id else instance_id
