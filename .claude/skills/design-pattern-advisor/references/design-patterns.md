# Design Pattern Selection Notes

## Contents

- Strategy
- Factory
- Abstract Factory
- Observer
- Decorator
- Adapter
- Chain of Responsibility
- Template Method
- Command
- Singleton
- Smell To Pattern Map

## Strategy

Use when one algorithm or decision rule changes while the surrounding workflow stays stable.

Common triggers:

- Pricing, scoring, ranking, filtering, routing
- Different business rules by market, user tier, or environment
- Large conditional trees choosing one algorithm

Python-first implementations:

- Start with `callable` injection for simple cases
- Move to classes only when strategy needs state, shared configuration, or lifecycle hooks
- A dictionary of named callables is often enough

Avoid when:

- There are only one or two stable branches
- The rule difference is tiny and unlikely to grow

## Factory

Use when callers should ask for a capability, not know how to build it.

Common triggers:

- Provider selection from config
- Hidden initialization complexity
- Repeated `SomeClass(...)` construction logic across modules

Python-first implementations:

- A factory function is usually enough
- Use a registry dictionary for plugin-style selection
- Use factory classes only when creation itself has state or dependencies

Avoid when:

- Construction is trivial and local
- The caller already naturally owns the dependencies

## Abstract Factory

Use when you must create a compatible family of objects together.

Common triggers:

- Swapping database adapters plus query builders together
- UI themes or environment-specific component families
- Exchange-specific service bundles

Python-first implementations:

- One object or module that exposes a coherent family of builders
- Prefer composition over deep inheritance trees

Avoid when:

- You only create one object type
- Compatibility across the family is not a real concern

## Observer

Use when one event should notify multiple dependents without hard-coding all targets into the producer.

Common triggers:

- Order status changes trigger notifications, metrics, and audit logging
- Market data updates fan out to multiple consumers
- Domain events with many subscribers

Python-first implementations:

- Start with explicit callback lists or a small event bus
- Use async queues if timing and backpressure matter

Avoid when:

- There is only one consumer
- Execution order, failure handling, and delivery semantics are undefined

## Decorator

Use when behavior should wrap existing logic without changing its core implementation.

Common triggers:

- Logging, caching, retries, authorization, rate limiting
- Add optional behavior around handlers or services

Python-first implementations:

- Function decorators for call-level cross-cutting concerns
- Wrapper objects when stateful behavior must surround an object interface

Avoid when:

- A direct function call is clearer
- Stacked wrappers make control flow opaque

## Adapter

Use when an existing interface is almost right but not directly usable by your code.

Common triggers:

- Third-party SDK shape differs from local interface
- Legacy module must fit a new boundary
- Rename or normalize methods without changing callers

Python-first implementations:

- Thin wrapper object
- Function-level normalization when the mismatch is small

Avoid when:

- You really need a new abstraction, not just an interface bridge

## Chain of Responsibility

Use when requests pass through an ordered set of handlers that may accept, enrich, or reject them.

Common triggers:

- Validation pipeline
- Risk checks
- Request middleware
- Fallback resolution logic

Python-first implementations:

- A list of handler callables is often enough
- Short-circuit on first terminal result

Avoid when:

- Order is unstable or undocumented
- A simple loop with named steps is clearer

## Template Method

Use when the workflow is stable but some steps vary across subclasses or strategies.

Common triggers:

- Shared pipeline with customizable fetch, transform, persist steps
- Repeated workflow skeleton across similar processors

Python-first implementations:

- Prefer composition plus injected hooks in Python
- Use inheritance only when the template is truly stable and subclass variation is narrow

Avoid when:

- Inheritance starts carrying too many hidden assumptions

## Command

Use when actions need to be queued, logged, retried, scheduled, or undone as first-class objects.

Common triggers:

- Job queues
- Undo/redo actions
- Deferred execution
- Audit-ready action records

Python-first implementations:

- `dataclass` for command payload plus a handler function
- Separate command bus only when dispatch complexity is real

Avoid when:

- A direct function call already captures the action clearly

## Singleton

Use sparingly. Treat it as a last resort for a truly shared process-wide resource.

Common triggers:

- Configuration registry
- Global cache entry point
- Logger access facade

Safer Python alternatives:

- Module-level instance
- Explicit dependency injection
- Application context object

Main risk:

- Hidden global state makes testing and lifecycle management harder

## Smell To Pattern Map

- Repeated `if/elif` by algorithm: Strategy
- Repeated `if/elif` by object construction: Factory
- Caller knows too much about third-party API shape: Adapter
- One state change triggers many side effects: Observer
- Repeated wrapper concerns around core logic: Decorator
- Validation or routing needs ordered handlers: Chain of Responsibility
- Shared flow with variable steps: Template Method or Strategy
- Need to record and replay actions: Command
- Global uniqueness request: Challenge first, then maybe Singleton

## Final Check

Before recommending any pattern, ask:

1. What exact change are we insulating?
2. What is the smallest boundary we can stabilize?
3. Can a Python-native lightweight construct solve it first?
4. Will the next engineer understand the design without reading pattern theory?
