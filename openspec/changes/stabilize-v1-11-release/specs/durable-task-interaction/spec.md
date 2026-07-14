## ADDED Requirements

### Requirement: Pending interactions are checkpointed before display
The system SHALL persist a pending interaction with stable request id, task id, kind, payload, status, and creation time before emitting it to the desktop UI.

#### Scenario: Missing information request is displayed
- **WHEN** a task cannot proceed without user information
- **THEN** the checkpoint contains the pending request before the UI receives the `waiting_user` event

#### Scenario: Plan confirmation is displayed
- **WHEN** a complex or high-risk plan requires confirmation
- **THEN** the checkpoint contains the plan snapshot and stable request id before the confirmation modal opens

### Requirement: Pending interactions resume with the same task
The system SHALL restore a pending interaction from checkpoint, re-register its wait state, and re-emit it using the original task id and request id.

#### Scenario: Application restarts while waiting
- **WHEN** the desktop application exits while a task is waiting and the user later resumes that checkpoint
- **THEN** the same pending question or plan is shown and an accepted response continues the same task without rerunning completed steps

### Requirement: Interaction decisions are idempotent
The system MUST apply at most one accepted or rejected decision for a request id and SHALL prevent decisions from affecting a different task.

#### Scenario: Duplicate response
- **WHEN** the frontend submits the same interaction decision more than once
- **THEN** the first valid decision is retained and later submissions do not advance the task again

#### Scenario: Request belongs to another task
- **WHEN** a response references a request id that does not belong to the active task
- **THEN** the system rejects the response without changing either task

### Requirement: Rejection, cancellation, and timeout are not completion
The system SHALL give rejected, cancelled, and timed-out interactions explicit non-completed outcomes and SHALL preserve their reason in task history.

#### Scenario: User cancels plan confirmation
- **WHEN** the user rejects or cancels a pending plan
- **THEN** the plan and task are not marked completed and no pending tool executes

#### Scenario: Interaction times out
- **WHEN** a pending interaction reaches its configured timeout without a response
- **THEN** the task remains recoverable or enters an explicit timed-out state according to policy, with no false completion

### Requirement: Frontend interaction rendering is replay-safe
The desktop UI SHALL deduplicate pending interaction events by request id and SHALL keep reply controls bound to the active task.

#### Scenario: Waiting event is replayed
- **WHEN** the backend re-emits a pending interaction during checkpoint recovery
- **THEN** the UI shows one modal for that request and does not create duplicate pending state
