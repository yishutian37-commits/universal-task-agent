## ADDED Requirements

### Requirement: Step criteria participate in completion
The system SHALL evaluate every declared `success_criteria` item for the current plan step before marking that step completed.

#### Scenario: All criteria pass
- **WHEN** a tool result passes the existing verifier and every declared step criterion is satisfied
- **THEN** the system marks the step completed and persists one passing result per criterion

#### Scenario: A criterion fails
- **WHEN** the existing verifier passes but at least one declared step criterion is not satisfied
- **THEN** the system SHALL keep the step incomplete and record the failed criterion, reason, and available evidence

### Requirement: Verification results are evidence-backed
The system MUST store the verification source and concrete evidence for each criterion result, and SHALL distinguish deterministic checks from semantic judgments.

#### Scenario: File mutation criterion
- **WHEN** a criterion concerns file creation, modification, deletion, directory creation, or another high-risk workspace effect
- **THEN** the system SHALL require deterministic filesystem or tool evidence and SHALL NOT accept a model-only judgment as proof

#### Scenario: Criterion cannot be determined
- **WHEN** available tool output and evidence cannot establish whether a criterion passed
- **THEN** the system SHALL record an indeterminate failure instead of assuming success

### Requirement: Replan receives criterion failures
The system SHALL include failed criteria, reasons, verification sources, and evidence in the failure context supplied to Replan while preserving completed steps.

#### Scenario: Replan after criterion failure
- **WHEN** a step exhausts its retry budget because a success criterion continues to fail
- **THEN** Replan receives the failed criterion details and resumes from the failed step without rerunning the completed prefix

### Requirement: Criterion state survives checkpoints
The system SHALL serialize and restore step criterion results without losing their association with task, plan, step, or evidence.

#### Scenario: Resume after verified step
- **WHEN** a task is restored from a checkpoint after one or more criteria were evaluated
- **THEN** the restored state contains the same criterion results and does not evaluate completed steps again

### Requirement: Steps without criteria remain compatible
The system SHALL preserve current verifier behavior for legacy plans and fallback plans that do not declare success criteria.

#### Scenario: Legacy checkpoint has no criteria
- **WHEN** an older checkpoint contains a plan step without success criteria or criterion results
- **THEN** the system loads it safely and applies the existing task-level verification behavior
