from pathlib import Path
import subprocess
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_node(source: str) -> None:
    result = subprocess.run(
        ["node", "-e", textwrap.dedent(source)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_requesting_phase_rejects_a_second_request_before_api_return():
    run_node(
        """
        const assert = require("node:assert/strict");
        const { createRunLifecycle } = require("./desktop/frontend/shell.js");
        const lifecycle = createRunLifecycle();

        const first = lifecycle.beginRequest({
          conversationId: "conversation-a",
          conversationRevision: 4,
          assistantId: "assistant-a"
        });

        assert.ok(first);
        assert.equal(lifecycle.getPhase(), "requesting");
        assert.equal(lifecycle.beginRequest({ conversationId: "conversation-b" }), null);
        assert.equal(lifecycle.getPhase(), "requesting");
        """
    )


def test_early_events_are_buffered_by_task_until_the_api_binds_context():
    run_node(
        """
        const assert = require("node:assert/strict");
        const { createRunLifecycle } = require("./desktop/frontend/shell.js");
        const lifecycle = createRunLifecycle();
        const request = lifecycle.beginRequest({
          conversationId: "conversation-a",
          conversationRevision: 7,
          assistantId: "assistant-a"
        });

        const early = lifecycle.routeEvent({
          task_id: "task-a",
          type: "task_received",
          data: {}
        });
        assert.equal(early.disposition, "buffered");
        assert.equal(lifecycle.getCurrentTaskId(), null);

        const bound = lifecycle.bindTask(request.requestId, {
          taskId: "task-a",
          conversationId: "conversation-a"
        });
        assert.equal(bound.ok, true);
        assert.equal(bound.events.length, 1);
        assert.equal(bound.events[0].task_id, "task-a");
        assert.equal(bound.context.taskId, "task-a");
        assert.equal(bound.context.conversationId, "conversation-a");
        assert.equal(bound.context.conversationRevision, 7);
        assert.equal(bound.context.assistantId, "assistant-a");
        assert.equal(Object.isFrozen(bound.context), true);
        """
    )


def test_old_task_events_cannot_become_the_current_task():
    run_node(
        """
        const assert = require("node:assert/strict");
        const { createRunLifecycle } = require("./desktop/frontend/shell.js");
        const lifecycle = createRunLifecycle();

        const first = lifecycle.beginRequest({ conversationId: "conversation-a" });
        lifecycle.bindTask(first.requestId, { taskId: "task-a", conversationId: "conversation-a" });
        lifecycle.routeEvent({ task_id: "task-a", type: "task_completed", data: {} });

        const second = lifecycle.beginRequest({ conversationId: "conversation-b" });
        lifecycle.bindTask(second.requestId, { taskId: "task-b", conversationId: "conversation-b" });
        const stale = lifecycle.routeEvent({
          task_id: "task-a",
          type: "step_started",
          data: { step_id: "old-step" }
        });

        assert.equal(stale.disposition, "ignored");
        assert.equal(lifecycle.getCurrentTaskId(), "task-b");
        assert.equal(lifecycle.getTaskPhase("task-b"), "running");
        """
    )


def test_terminal_transition_uses_the_event_task_id():
    run_node(
        """
        const assert = require("node:assert/strict");
        const { createRunLifecycle } = require("./desktop/frontend/shell.js");
        const lifecycle = createRunLifecycle();
        const request = lifecycle.beginRequest({ conversationId: "conversation-event" });
        lifecycle.bindTask(request.requestId, {
          taskId: "task-event",
          conversationId: "conversation-event"
        });

        const routed = lifecycle.routeEvent({
          task_id: "task-event",
          type: "task_completed",
          data: { status: "completed" }
        });

        assert.equal(routed.taskId, "task-event");
        assert.equal(routed.context.taskId, "task-event");
        assert.equal(routed.phase, "completed");
        assert.equal(lifecycle.getTaskPhase("task-event"), "completed");
        """
    )


def test_cancel_response_after_cancelled_event_cannot_replace_terminal_phase():
    run_node(
        """
        const assert = require("node:assert/strict");
        const { createRunLifecycle } = require("./desktop/frontend/shell.js");
        const lifecycle = createRunLifecycle();
        const request = lifecycle.beginRequest({ conversationId: "conversation-a" });
        lifecycle.bindTask(request.requestId, { taskId: "task-a", conversationId: "conversation-a" });

        assert.equal(lifecycle.beginCancel("task-a"), true);
        lifecycle.routeEvent({ task_id: "task-a", type: "cancelled", data: {} });

        assert.equal(lifecycle.confirmCancel("task-a"), false);
        assert.equal(lifecycle.getTaskPhase("task-a"), "cancelled");
        """
    )


def test_completion_wins_when_cancel_promise_resolves_late():
    run_node(
        """
        const assert = require("node:assert/strict");
        const { createRunLifecycle } = require("./desktop/frontend/shell.js");
        const lifecycle = createRunLifecycle();
        const request = lifecycle.beginRequest({ conversationId: "conversation-a" });
        lifecycle.bindTask(request.requestId, { taskId: "task-a", conversationId: "conversation-a" });

        assert.equal(lifecycle.beginCancel("task-a"), true);
        lifecycle.routeEvent({
          task_id: "task-a",
          type: "task_completed",
          data: { status: "completed" }
        });

        assert.equal(lifecycle.confirmCancel("task-a"), false);
        assert.equal(lifecycle.failCancel("task-a"), false);
        assert.equal(lifecycle.getTaskPhase("task-a"), "completed");
        """
    )
