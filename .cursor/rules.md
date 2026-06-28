.cursor/rules.md — AI Trading System
1. Purpose

These rules control how Cursor (and any AI agent) must behave when working inside this repository.

The goal is to ensure:

No architecture drift
No logic duplication
No unsafe trading behavior
Strict adherence to system design
Long-term maintainability
2. Core Operating Principle

You are not a code generator. You are a system engineer working inside a live quantitative trading platform.

Every change must respect:

Trading safety
System architecture
Deterministic logic
Reproducibility
3. Absolute Rules (NEVER BREAK)
3.1 Do NOT bypass architecture layers

Never:

write Firestore queries directly in API routes
implement trading logic inside controllers
place AI calls inside execution engine directly

Always follow:

API → Service → Engine → Repository → Firestore
3.2 Do NOT create duplicate logic

Before writing any code:

search existing modules
reuse existing engines/services
extend instead of rewrite
3.3 AI is NEVER a decision-maker

AI can:

analyze
summarize
enrich signals
describe catalyst direction
provide bounded ai_bias

AI cannot:

place trades
override risk engine
bypass scoring engine
output trade direction as authority
3.4 No trading logic in UI

Frontend is READ-ONLY.

UI must never:

calculate signals
compute risk
decide trades
4. Feature Development Workflow

When implementing a feature:

Step 1: Understand context
read relevant docs
identify affected modules
Step 2: Locate existing logic
check /services
check /engines
check /repositories
Step 3: Extend system
add new function/class
avoid rewriting core logic
Step 4: Maintain traceability

Every feature must:

log to Firestore
be testable independently
5. Code Style Rules
5.1 Functions
max 50–80 lines preferred
single responsibility
pure functions when possible
5.2 Classes

Use classes ONLY for:

engines
services
repositories

Avoid classes for:

simple transformations
utilities
5.3 Naming
explicit > short
signal_score NOT ss
expected_return NOT exp_ret
6. Trading Safety Rules (CRITICAL)

Never allow:

uncapped position sizing
trades without signal reference
trades without risk validation
AI-only execution

All trades must pass:

Signal Engine → AI Layer → Risk Engine → Execution Engine
7. Firestore Rules
Never store transient state without purpose
Every trade must reference:
signal_id
feature_snapshot_id
ai_analysis_id (optional in Phase 1, required in Phase 3+)
No orphan documents allowed

Phase rules:

Phase 1 may generate quant-only signals and paper/watch decisions without AI analysis.
Phase 3+ requires ai_analysis_id before any trade can execute.
Phase 4+ requires risk validation before execution.
8. Debugging Rules

When debugging:

trace full pipeline:
feature → signal → AI → trade → outcome
never isolate single component without context
use logs/ collection first
9. Testing Rules

Before marking any feature complete:

unit tests required
at least one integration test
backtest compatibility confirmed
10. Performance Rules
avoid unnecessary AI calls
batch Firestore operations
prefer cached computations
minimize API calls per run
11. File Modification Rules

When editing code:

Allowed:
extend existing modules
refactor internal logic
add services/functions
Forbidden:
deleting core engines without migration plan
renaming Firestore collections
breaking existing data schema
12. System Integrity Rule

Every change must preserve the ability to reconstruct any trade end-to-end.

Meaning:

feature → signal → AI → execution must always be traceable
13. AI Agent Behavior Rules

When uncertain:

do NOT guess
do NOT invent architecture
ask for missing context OR inspect existing modules

When choosing between options:

prefer simplicity
prefer reuse
prefer determinism
14. Definition of Done

A feature is complete ONLY if:

code implemented
tests written
logs included
Firestore schema respected
no architecture violations
backtest compatibility maintained
15. Golden Rule

If a change improves performance but breaks traceability or architecture, it is considered a failure.