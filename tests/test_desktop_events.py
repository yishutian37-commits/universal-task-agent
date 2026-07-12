from __future__ import annotations

from datetime import datetime, timezone

from desktop.events import desktop_event


def test_desktop_event_adds_version_identity_and_ownership():
    now = datetime(2026, 7, 13, 12, 30, tzinfo=timezone.utc)

    event = desktop_event(
        {"type": "step_started", "task_id": "task_1", "data": {"step_id": 2}},
        conversation_id="conv_1",
        now=now,
        event_id="evt_fixed",
    )

    assert event == {
        "version": 1,
        "event_id": "evt_fixed",
        "conversation_id": "conv_1",
        "task_id": "task_1",
        "type": "step_started",
        "timestamp": "2026-07-13T12:30:00+00:00",
        "data": {"step_id": 2},
    }


def test_desktop_event_preserves_existing_envelope_fields():
    event = desktop_event(
        {
            "version": 1,
            "event_id": "evt_existing",
            "conversation_id": "conv_existing",
            "task_id": "task_existing",
            "type": "artifact_created",
            "timestamp": "2026-07-13T12:30:00+00:00",
            "data": {"path": "/tmp/report.md"},
        },
        conversation_id="conv_other",
    )

    assert event["event_id"] == "evt_existing"
    assert event["conversation_id"] == "conv_existing"
    assert event["task_id"] == "task_existing"
    assert event["data"] == {"path": "/tmp/report.md"}

