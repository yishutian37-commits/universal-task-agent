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


def test_memory_view_helpers_cover_tabs_keyboard_and_content_organization():
    run_node(
        """
        const assert = require("node:assert/strict");

        function createElement(dataset) {
          const classes = new Set();
          return {
            dataset,
            attributes: {},
            hidden: false,
            tabIndex: -1,
            classList: {
              toggle(name, enabled) {
                if (enabled) classes.add(name);
                else classes.delete(name);
              },
              contains(name) {
                return classes.has(name);
              }
            },
            setAttribute(name, value) {
              this.attributes[name] = String(value);
            },
            getAttribute(name) {
              return this.attributes[name] || null;
            },
            focus() {
              document.activeElement = this;
            }
          };
        }

        const tabs = ["long-term", "session", "learning", "archive"].map((tabName) =>
          createElement({ memoryTab: tabName })
        );
        const panels = ["long-term", "session", "learning", "archive"].map((tabName) =>
          createElement({ memoryPanel: tabName })
        );
        global.document = {
          activeElement: null,
          querySelectorAll(selector) {
            if (selector === "[data-memory-tab]") return tabs;
            if (selector === "[data-memory-panel]") return panels;
            return [];
          }
        };

        const {
          activateMemoryTab,
          handleMemoryTabKeydown,
          groupMemoryFacts,
          compactMemoryText,
          dedupeMemoryLessons
        } = require("./desktop/frontend/shell.js");

        assert.equal(activateMemoryTab("invalid"), "long-term");
        ["long-term", "session", "learning", "archive"].forEach((tabName) => {
          assert.equal(activateMemoryTab(tabName), tabName);
        });
        assert.equal(tabs[3].classList.contains("active"), true);
        assert.equal(tabs[3].getAttribute("aria-selected"), "true");
        assert.equal(tabs[3].tabIndex, 0);
        assert.equal(panels[3].hidden, false);
        assert.equal(panels[3].getAttribute("aria-hidden"), "false");
        assert.equal(panels[0].hidden, true);
        assert.equal(panels[0].getAttribute("aria-hidden"), "true");

        function keydown(key, currentTarget) {
          let prevented = false;
          const result = handleMemoryTabKeydown({
            key,
            currentTarget,
            preventDefault() { prevented = true; }
          });
          assert.equal(prevented, true);
          return result;
        }

        assert.equal(keydown("ArrowRight", tabs[3]), "long-term");
        assert.equal(document.activeElement, tabs[0]);
        assert.equal(keydown("ArrowLeft", tabs[0]), "archive");
        assert.equal(keydown("Home", tabs[3]), "long-term");
        assert.equal(keydown("End", tabs[0]), "archive");

        assert.equal(
          compactMemoryText("## 标题\\n- **`内容`**\\n```text\\n代码\\n```", 20),
          "标题 内容 代码"
        );
        assert.equal(
          compactMemoryText("1. first\\n2、 second\\n3) third\\n__bold__", 60),
          "first second third bold"
        );
        assert.equal(compactMemoryText("**一二三四五六七**", 6), "一二三...");
        assert.equal(compactMemoryText("abcdef", 0), "");
        assert.equal(compactMemoryText("abcdef", 1), ".");
        assert.equal(compactMemoryText("abcdef", 2), "..");
        assert.equal(compactMemoryText("abcdef", 3), "...");
        assert.deepEqual(
          groupMemoryFacts([
            { kind: "preference", content: "中文" },
            { kind: "preference", content: "简洁" },
            { kind: "fact", content: "测试" }
          ]),
          {
            preference: [
              { kind: "preference", content: "中文" },
              { kind: "preference", content: "简洁" }
            ],
            fact: [{ kind: "fact", content: "测试" }]
          }
        );
        assert.deepEqual(dedupeMemoryLessons([
          { task_type: "summarize", content: "复用流程", source: "old" },
          { task_type: "summarize", content: "复用流程", source: "new" },
          { task_type: "review", content: "独立复查" }
        ]), [
          { task_type: "summarize", content: "复用流程", source: "new", occurrence_count: 2 },
          { task_type: "review", content: "独立复查", occurrence_count: 1 }
        ]);
        const unorderedLessons = dedupeMemoryLessons([
          {
            task_type: "summarize",
            content: "按时间保留",
            source: "newest-updated",
            updated_at: "2026-07-11T09:00:00Z"
          },
          {
            task_type: "summarize",
            content: "按时间保留",
            source: "oldest-updated",
            updated_at: "2026-07-10T09:00:00Z"
          },
          {
            task_type: "review",
            content: "按创建时间保留",
            source: "newest-created",
            created_at: "2026-07-11T09:00:00Z"
          },
          {
            task_type: "review",
            content: "按创建时间保留",
            source: "oldest-created",
            created_at: "2026-07-10T09:00:00Z"
          }
        ]);
        assert.deepEqual(unorderedLessons, [
          {
            task_type: "summarize",
            content: "按时间保留",
            source: "newest-updated",
            updated_at: "2026-07-11T09:00:00Z",
            occurrence_count: 2
          },
          {
            task_type: "review",
            content: "按创建时间保留",
            source: "newest-created",
            created_at: "2026-07-11T09:00:00Z",
            occurrence_count: 2
          }
        ]);
        assert.deepEqual(dedupeMemoryLessons([
          {
            task_type: "review",
            content: "同一时间取后项",
            source: "first",
            updated_at: "2026-07-11T09:00:00Z"
          },
          {
            task_type: "review",
            content: "同一时间取后项",
            source: "later",
            updated_at: "2026-07-11T09:00:00Z"
          }
        ]), [
          {
            task_type: "review",
            content: "同一时间取后项",
            source: "later",
            updated_at: "2026-07-11T09:00:00Z",
            occurrence_count: 2
          }
        ]);
        """
    )
