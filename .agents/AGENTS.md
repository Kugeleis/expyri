# Project Rules

- **Shell is fish**: All terminal/shell commands must use fish shell syntax (the user's interactive shell is fish). In particular:
  - Use `$status` instead of `$?` for exit codes.
  - No bash-only syntax: no heredocs (`<<EOF`), no `[[ ]]`, no `${VAR}` manipulation, no `export VAR=value` (use `env VAR=value cmd` or `set -x VAR value`).
  - Fine to use: `;`, `&&`, `||`, `>` / `>>` redirection, `$(...)` command substitution (fish ≥ 3.4), and piping into `grep`/`tail` etc.
  - Prefer redirecting output to a temp file and reading the file, since long terminal output is hard to capture.
- Use Playwright for user web browser UI tests.
- Test-Driven Development (TDD) is preferable. First write focused tests, then implement the actual code if this is feasible.
- Code files should not exceed 300 lines. Only in special cases code files can be larger. Readability is key! If code is too large it should be split in focused files named clearly.

## Design & Coding Philosophy (SOLID, DRY, SRP, KISS)

1. **SOLID Implementation**:
   - **Open-Closed (OCP)**: Use the extensible registry pattern (`app/core/registry.py`) to add new stats methods, plot types, or report formats without altering core runner logic.
   - **Dependency Inversion (DIP)**: Rely on abstract registries, interfaces, and FastAPI dependency injection (`Depends`) rather than tight coupling to concrete implementations.
2. **DRY (Don't Repeat Yourself)**:
   - Centralize shared helper utilities (e.g. `save_parquet_with_metadata`) and database access methods rather than duplicating logic inside routes.
3. **Single Responsibility (SRP)**:
   - Keep routers lightweight. Routers should handle HTTP request-response boundaries and delegate business logic to services (like `WizardService`) or plugins (like exporters).
4. **KISS (Keep It Simple)**:
   - Prefer simple, readable, and native standard-library features over complex third-party abstractions. Use HTMX for light DOM updates and avoid heavy SPA logic.

## Quality & Coverage Rules
- **Code Coverage**: Ensure test coverage is maintained above **90%** for all features.
- **Complexity Guard**: Keep functions and files focused; file length should generally remain under 300 lines.
