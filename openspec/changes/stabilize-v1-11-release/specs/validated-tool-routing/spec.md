## ADDED Requirements

### Requirement: Tool catalog exposes executable contracts
The runtime tool catalog SHALL list only registered tools and SHALL describe each allowed action, its parameter object schema, default action, and authorization requirement.

#### Scenario: Registered tool with explicit actions
- **WHEN** a tool declares two executable actions
- **THEN** the catalog exposes exactly those actions and their parameter contracts to Planner and Router

#### Scenario: Legacy tool without action metadata
- **WHEN** a registered legacy tool declares no action contract
- **THEN** the catalog exposes only its compatible default action with an object parameter contract

### Requirement: Planner validates tool and action hints
The Planner SHALL reject or remove any model-generated tool/action combination that is absent from the current runtime catalog.

#### Scenario: Model invents an action
- **WHEN** a model plan names a registered tool but an action not allowed by that tool
- **THEN** the Planner uses the existing safe fallback plan and does not preserve the invented action

### Requirement: Router validates before execution
The Router MUST validate tool name, action name, and parameter shape against the current catalog before creating an executable action.

#### Scenario: Model returns invalid parameters
- **WHEN** a model selects an allowed tool/action but its parameters violate the declared schema
- **THEN** the Router SHALL use a validated deterministic fallback or return unsupported without invoking the tool

#### Scenario: Valid dynamic route
- **WHEN** the model selects a registered tool, allowed action, and valid parameter object
- **THEN** the Router creates the action and preserves the model reason and validated parameters

### Requirement: Edited steps are rebound to current intent
The system SHALL invalidate machine-selected routing metadata for each plan step whose goal was edited or newly added by the user.

#### Scenario: User changes a step goal
- **WHEN** the user changes a confirmed plan step from its original goal to a different goal
- **THEN** the system clears its old tool hint, action hint, inputs, success criteria, and cached authorization marker before execution

#### Scenario: Completed prefix is retained
- **WHEN** the user edits only pending steps during a Replan confirmation
- **THEN** completed steps, their results, and evidence remain unchanged while edited pending steps are rebound

### Requirement: Tool authorization remains authoritative
Model plans, model routes, and user-edited plans MUST NOT reduce the authorization requirement enforced by the selected runtime tool.

#### Scenario: Edited goal selects a dangerous tool
- **WHEN** a user-edited step is dynamically routed to a file-write, delete, Shell, Python, or directory-create tool
- **THEN** the normal single-operation authorization flow occurs before the tool can execute
