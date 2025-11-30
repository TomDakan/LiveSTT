# AI Collaboration Workflow: "Guide-not-Drive"

This document defines the standard operating procedure for collaboration between the User (Developer) and the AI Agent (Tech Lead/Architect).

## Core Philosophy
-   **Agent as Architect**: High-level specifications have already been written in the roadmap and design docs. The Agent's role is to provide guidance and scaffolding.
-   **User as Developer**: The User writes the actual logic, tests, and implementation details.
-   **Code is Truth**: The codebase is the final authority. Design discussions happen via code reviews.

## The Workflow Loop

### 1. Spec (Agent)
The Agent analyzes the requirements and creates a guide in `docs/implementation_guides/`. The agent must ensure that it reviews any/all .md files that may be relevant to the current task.
-   **Content**: Objectives, Interface Definitions (Protocols), Testing Strategy, Tricky Concepts.
-   **Output**: `docs/implementation_guides/XX_feature_name.md`

### 2. Scaffold (Agent)
The Agent creates the initial Python files.
-   **Imports**: Necessary libraries and typing.
-   **Signatures**: Strictly typed function/method signatures (`def foo(x: int) -> str:`).
-   **Docstrings**: Detailed behavior descriptions.
-   **The "Hole"**: Bodies are left as `raise NotImplementedError` or `pass`.
-   **Tests**: Empty test files are created.

### 3. Review & Refine (User + Agent)
**Critical Step**: Before implementing, the User reviews the scaffold.
-   **Direct Edit**: The User is encouraged to modify signatures, rename methods, or change types directly in the file.
-   **Sync**: The User notifies the Agent of changes. The Agent reads the updated file to align its context.

### 4. Implement (User)
The User writes the code.
-   **Tests First**: Implement the Mocks and Unit Tests as described in the Guide.
-   **Logic Second**: Implement the concrete classes to pass the tests.

### 5. Verify (User)
The User runs the project's standard verification tools.
-   `just test`: Ensure all tests pass.
-   `just lint`: Ensure code style compliance.
-   `just type-check`: Ensure strict type safety.

## Design Standards
-   **Object-Oriented**: Prioritize Object-Oriented Design (Classes, Interfaces/Protocols) over functional patterns where idiomatic.
-   **Encapsulation**: Use classes to bundle state and behavior.
-   **Interfaces**: Use `typing.Protocol` or `abc.ABC` to define clear contracts between components.
-   **Data Models**: Use standard library `@dataclass` (prefer `frozen=True`, `slots=True`) for value objects. Avoid heavy validation libraries like Pydantic unless necessary for edge I/O.
-   **Dependency Injection**: Pass dependencies via `__init__` rather than instantiating them inside classes.
-   **Immutability**: Prefer immutable state for events and messages to ensure thread-safety in async contexts.

## Toolchain Constraints
-   **Linting**: Ruff
-   **Typing**: MyPy (Strict)
-   **Tasks**: Just
-   **Package Manager**: uv
-   **Commits**: Conventional Commits (via `commitizen`)
