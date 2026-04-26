---
name: design-pattern-advisor
description: Evaluate whether a design pattern is warranted during feature design, refactoring, architecture changes, or code review, then choose a fitting pattern and a Python-idiomatic implementation. Use when code shows change pressure such as repeated if/elif branching, tangled object creation, oversized classes, mixed responsibilities, unstable dependencies, event fan-out, or requests to "apply a design pattern", "improve extensibility", "decouple modules", or "make this easier to evolve".
---

# Design Pattern Advisor

Treat design patterns as a way to organize sources of change, not as templates to paste in. Favor the lightest design that protects future evolution.

## Workflow

1. Identify the change pressure before naming any pattern.
2. Decide whether a pattern is necessary at all.
3. Choose the smallest pattern that stabilizes the right boundary.
4. Implement it in a Python-idiomatic way.
5. Verify that the result is easier to extend, test, and explain.

## Step 1: Identify The Change Pressure

Start from the concrete friction in the code or design:

- Many `if/elif` branches switching algorithms, rules, providers, or handlers
- Object creation logic spread across call sites
- One class doing orchestration, state, IO, and policy at the same time
- Many downstream consumers reacting to one event or state transition
- Need to adapt an incompatible API without touching the caller
- Request to add new variants frequently without editing core flow

Name three things explicitly:

- What is expected to vary?
- What should remain stable?
- What would become painful if we added one more variant next week?

If you cannot name the change, do not introduce a pattern yet.

## Step 2: Decide Whether To Use A Pattern

Prefer no explicit pattern when simple functions, a small dictionary, or one focused class already solve the problem cleanly.

Use a pattern only when it clearly improves at least one of these:

- Extension without modifying core flow
- Separation of construction from use
- Isolation of policy from orchestration
- Replacement of deep branching with pluggable behavior
- Reduction of coupling across modules or layers
- Testability of independent parts

Warning signs of over-design:

- Adding abstract base classes with only one implementation
- Creating factories for objects that are trivial to instantiate
- Turning a simple callback into a heavy observer framework
- Hiding straightforward code behind too many layers

## Step 3: Match The Pressure To A Pattern

Use this quick mapping first:

- Algorithm or rule varies, flow stays stable: Strategy
- Creation varies, caller should not know details: Factory
- A family of related objects must stay compatible: Abstract Factory
- One event notifies many downstream reactions: Observer
- Add behavior around existing logic without editing internals: Decorator
- Make an incompatible interface usable: Adapter
- Pass a request through ordered handlers: Chain of Responsibility
- Stable workflow with overridable steps: Template Method
- Wrap actions as objects for queueing, logging, or undo: Command
- Need one shared process-wide access point only with clear justification: Singleton

For richer cues and Python notes, read [references/design-patterns.md](references/design-patterns.md).

## Step 4: Translate The Pattern Into Python

Do not force Java-shaped implementations into Python. Prefer:

- First-class functions for lightweight strategies
- `dict[str, callable]` when behavior dispatch is simple
- Composition before inheritance
- `abc` only when an explicit protocol improves clarity
- `dataclass` for plain configuration or immutable command data
- Decorators and higher-order functions for cross-cutting behavior

When presenting a solution, include both:

- Why this pattern fits the change pressure
- Why a lighter alternative is insufficient or sufficient

## Step 5: Apply With Restraint

When editing code:

- Preserve existing project conventions unless they are the problem
- Refactor toward one clear seam at a time
- Avoid introducing multiple patterns in one pass unless the boundaries are already obvious
- Keep naming concrete and domain-based; do not create classes named only after the pattern unless that improves readability

## Output Shape

When advising or implementing, structure the response in this order:

1. Change pressure
2. Recommended pattern or "no pattern"
3. Python-specific implementation shape
4. Trade-offs and risks
5. Minimal verification plan

## Reference Usage

Read [references/design-patterns.md](references/design-patterns.md) when you need:

- Pattern-by-pattern selection help
- Python-specific implementation variants
- Examples of where patterns are often overused
- A compact mapping from code smell to design response
