AI Trading System — CODING_STANDARDS.md
1. Purpose

This document defines strict engineering rules for all code generated in this repository.

It ensures:

Consistency across AI-generated code (Cursor, agents, contributors)
Maintainability over time
Testability of every component
Clean separation of concerns
2. Core Engineering Philosophy
2.1 Deterministic > Clever

Prefer:

explicit logic
readable flows
simple functions

Avoid:

over-engineered abstractions
hidden side effects
"magic" behavior
2.2 AI-generated code must be predictable

Every AI-generated module must:

have clear inputs
have clear outputs
be independently testable
avoid global state
2.3 No business logic inside controllers

FastAPI controllers must ONLY:

validate input
call service layer
return response
3. Project Structure
backend/
    app/
        api/
            routes/
        services/
        engines/
        workers/
        models/
        repositories/
        utils/
        config/

frontend/
    app/
    components/
    lib/
    hooks/
    styles/

docs/
4. Backend Architecture Rules
4.1 Layer separation
Layer	Responsibility
API	HTTP interface only
Services	business logic
Engines	trading logic / AI logic
Repositories	Firestore access
Workers	scheduled/background jobs
4.2 Example flow
API → Service → Engine → Repository → Firestore
5. Firestore Rules
5.1 Never access Firestore directly in business logic

All DB access MUST go through repositories:

class SignalRepository:
    def get_signal(self, id: str):
        ...
5.2 No raw queries in services

Bad:

db.collection("signals").where(...)

Good:

signal_repo.get_top_signals()
6. Naming Conventions
6.1 Python
snake_case for functions
PascalCase for classes
uppercase constants
6.2 Files
feature_engine.py
signal_engine.py
risk_engine.py
6.3 Firestore collections
lowercase plural:
signals/
trades/
features/
7. Trading Engine Rules
No direct API calls inside engine logic
No side effects inside scoring functions
All decisions must be pure functions when possible
8. AI Integration Rules
8.1 AI is a service, not logic

AI must always be called via:

AIService.analyze_news()
AIService.analyze_catalyst()
8.2 AI output must be structured

Never use free-text outputs in production logic.

Always enforce:

JSON schema validation
fallback handling
confidence scoring

AI must not output trade direction as authority.
Use catalyst_direction and ai_bias for analysis only; execution approval belongs to deterministic engines.
9. Error Handling Rules
Never fail silently
Always log to Firestore logs/
Retry only idempotent operations
Execution engine must be crash-safe
10. Testing Rules
Required tests:
unit tests for engines
integration tests for API routes
mock tests for IBKR
backtest validation tests
Testing philosophy:
Backtests are first-class citizens
Every strategy change must be testable historically
11. Performance Rules
Prefer Polars over Pandas for large datasets
Avoid unnecessary API calls
Cache repeated computations
Batch Firestore writes
12. Anti-Patterns (STRICTLY FORBIDDEN)
12.1 Forbidden patterns
Business logic in API routes
AI deciding trades directly
Direct Firestore access everywhere
Hardcoded trading rules in multiple files
Circular dependencies
Global mutable state
12.2 Forbidden trading behavior
Intraday scalping logic
Unbounded position sizing
Trades without signal reference
AI-only decision making
13. Logging Standards

Every important operation must log:

{
  "service": "signal_engine",
  "event": "signal_created",
  "ticker": "NVDA",
  "timestamp": "...",
  "metadata": {}
}
14. Code Quality Tools

Required:

ruff (linting)
black (formatting)
mypy (type checking)
pytest (testing)
15. Cursor AI Rules

When using Cursor:

Always prefer existing modules over creating new ones
Never duplicate logic
Always check repositories before writing DB access
Respect architecture layers strictly
Keep functions small (< 50 lines preferred)
16. System Design Principle

Every line of code must map to a traceable trading decision or system function.

If it doesn’t:

it does not belong in the system