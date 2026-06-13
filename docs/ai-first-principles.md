# Making a Codebase AI-First — Principles & Playbook

*A review and adaptation of Seb (@plainionist)'s "How I Made My Brownfield
Codebase AI-First" (Jun 2026), distilled into principles that apply to **pySC**
and to other code I maintain.*

This document does two things:

1. **Reviews the source article from several angles** so the reasoning behind
   each principle is explicit (and so I can tell which parts are hype and which
   are durable).
2. **Distills portable principles** with concrete, prioritized next steps for
   pySC — a ~8k-LOC scientific Python package — and notes on how each
   generalizes to other projects.

The single most important takeaway, and the one the article ends on, is the
mindset, not the tooling:

> Turning a codebase AI-first is **less about the models and more about
> improving the environment around the agents.** It is continuous, not a
> one-time setup. ("Sharpen the saw.")

---

## Part 1 — The article from multiple angles

### Angle A: The solo / small-team maintainer
The author's real motivation is leverage: "I work on many things in parallel
and never have enough time." This is the dominant case for scientific and
research software too — often one or two domain experts who *know* the system
implicitly. The article's core insight is that **implicit knowledge is the
bottleneck**, not model capability. Everything that worked (docs, codex,
fitness functions) is a mechanism for externalizing what was only in the
maintainer's head.

*Relevance to me:* High. pySC has rich domain knowledge (accelerator physics,
the relationship to the original MATLAB `SC`) that currently lives in people,
docstrings, and tests — not in navigable docs.

### Angle B: Architecture & safety
The author succeeds largely because the **safety net already existed**: domain
rules encoded in F#'s type system, plus fast BDD/Gherkin acceptance tests. The
agents are allowed to move fast *because* a fast, meaningful test suite catches
regressions. The role separation (Implementer can't touch tests; Verifier
can't touch product code) is a structural guard against the classic agent
failure mode — "make the test pass by weakening the test."

*Relevance to me:* High and encouraging. pySC already has a near 1:1
test-to-source line ratio and pytest markers separating fast tests from `slow`
AT-tracking tests. The safety net exists; what's missing is **making it run
automatically** (CI runs only PyPI publish today).

### Angle C: Research / scientific software
This is where I must adapt rather than copy. The article's domain (backlog
planning) has crisp, enumerable business rules that fit Gherkin beautifully.
Scientific code instead has **numerical correctness, physical invariants, and
reproducibility** as its truth. The equivalent of a Gherkin spec here is:
- regression tests pinned to known-good numerical outputs (within tolerance),
- physical invariant checks (e.g., conservation, symmetry, units),
- seeded RNG for reproducibility (pySC already does `seed=42` in fixtures).

Gherkin/BDD is *optional* for me; the *principle* — "executable specifications
as the source of truth" — is not.

### Angle D: Economics / ROI
The author is honest about what didn't pay off: generic MCP servers (`serena`,
`fff`) made "no noticeable difference," while **cheap repo-specific shell
scripts** (`find-entry-points.sh`, `explain-area.sh`) did. Lesson: the highest
ROI is usually small, bespoke, legible tooling and *removing ambiguity*, not
adopting heavyweight frameworks. SwarmForge and a 3-role swarm are appropriate
for a 70k-LOC product with parallel feature streams; they are likely
**over-engineering for an 8k-LOC library**.

### Angle E: The skeptic
Worth naming the risks the article underplays:
- **Documentation drift.** A `Manual/` folder that lies is worse than none.
  This is why the author's move to *fitness functions* (executable rules)
  matters more than the prose docs.
- **Over-process.** Three agents, a constitution, handoff gates, and a swarm
  framework are real overhead. For most of my projects, *one* good guidance
  file + tests + a couple of scripts captures 80% of the value.
- **Reflection-in-tests anecdote** is the key tell: agents will exploit *any*
  rule you didn't write down. The defense isn't more vigilance — it's
  converting each "obvious to me" rule into an explicit, ideally *automated*,
  check the moment you notice it.

### What transfers vs. what doesn't (summary)

| Article element | Transfers to pySC? | Why |
|---|---|---|
| Make implicit knowledge explicit (docs) | **Yes — top priority** | No architecture/domain docs exist today |
| Strong, fast test safety net | **Already have it** | ~7.4k LOC tests, fast/slow split |
| Run the safety net automatically (CI) | **Yes — top priority** | CI only publishes; tests never run on push/PR |
| Engineering codex / single guidance file | **Yes** | No `CLAUDE.md`/codex exists |
| Architecture fitness functions | **Yes, lightweight** | Enforce layering & import boundaries cheaply |
| Repo-specific helper scripts | **Yes, selectively** | High ROI, low cost |
| Skills for repeated workflows | **Maybe, later** | Only once a workflow repeats |
| 3-role agent swarm / SwarmForge | **No (for now)** | Over-engineered at 8k LOC |
| Gherkin/BDD specifically | **Adapt** | Numerical regression tests are my equivalent |
| Retrospective-as-habit | **Yes** | Cheap, compounding |

---

## Part 2 — The principles (portable)

These are ordered by leverage. Each is stated generally, then applied to pySC.

### Principle 1 — Make implicit knowledge explicit
Agents (and new humans) cannot infer what only lives in your head. Write
concept- and background-oriented docs: *why* the architecture is shaped this
way, what the domain terms mean, what the invariants are. Keep each doc small
(~200 lines), concept-focused, and **point to executable artifacts** (tests,
specs) for the precise behavior rather than duplicating it.

> **pySC:** Create a small `docs/` (or `Manual/`) knowledge base:
> - `architecture.md` — the layering (`core → configuration → control_system →
>   apps → tuning → utils`), what each layer may depend on, and the
>   circular-import workaround in `__init__.py` (pydantic `model_rebuild`).
> - `domain.md` — accelerator-commissioning vocabulary (BPM, orbit/trajectory,
>   BBA, ORM/response matrix, dispersion, LOCO, RDT, tune/chromaticity) and the
>   lineage from the MATLAB `SC` toolkit.
> - `testing.md` — fixtures (`hmba_ring`, `sc`), the `slow`/`regression`
>   markers, tolerance conventions, and how reproducibility is guaranteed
>   (seeded RNG).
> - `development.md` — install/build (hatch), import conventions from the
>   README, how to add an app vs. a core type.

### Principle 2 — A fast, meaningful test suite is the precondition for agent autonomy
Agents are safe to act independently only in proportion to how well your tests
catch their mistakes. Prefer tests that are **loosely coupled to
implementation** (behavioral/acceptance-style) and **fast enough to run in the
loop.** Keep slow tests separable so the fast feedback loop stays fast.

> **pySC:** Already strong. Preserve the `slow`/`regression` marker split so
> agents can run `pytest -m "not slow"` for fast feedback and the full suite
> before handoff. Continue pinning regression tests to known-good numerical
> values with explicit tolerances.

### Principle 3 — If the safety net isn't enforced automatically, it doesn't fully count
A test suite that only runs when someone remembers is not a guardrail for an
agent. Wire tests into CI on every push/PR.

> **pySC:** *Gap.* The only workflow publishes to PyPI on tags. Add a CI job
> that runs `pytest` (at least the fast subset) on push and PR across the
> supported Python versions (3.9–3.12). This is arguably the highest-leverage
> single change for AI-first readiness.

### Principle 4 — One guidance file (the "engineering codex") for rules that apply to everyone
Capture project-wide rules in one place: acceptable size of a change, code
sharing vs. coupling, safe-refactor rules, readability conventions, and **stop
conditions** (when an agent should halt and ask rather than guess). This is the
`CLAUDE.md` / Copilot-instructions equivalent.

> **pySC:** Create a `CLAUDE.md` codex covering: the public API surface defined
> in `pySC/__init__.py` (don't break it), the import style from the README,
> "never weaken a test to make it pass," numerical-tolerance discipline, when
> to add a `regression` marker, and a stop condition for physics assumptions
> the agent isn't sure about.

### Principle 5 — When knowledge becomes explicit, ask if it can become an automated check
This is the article's most durable pattern. Prose rules drift and get ignored;
**executable rules don't.** "Architecture fitness functions" can be dead-simple
scripts (even regex/AST checks) with their own tests. The escalation ladder is:
*implicit → documented → automated.*

> **pySC:** Lightweight, high-value fitness functions:
> - **Layering / import boundaries:** assert `core` does not import from `apps`
>   or `tuning`; `utils` imports from nobody internal; etc. (a small AST/regex
>   test under `tests/`).
> - **Public API stability:** a test that the names in `pySC/__init__.py`'s
>   exports still import.
> - **No reflection / no test-weakening smells** (the article's exact lesson):
>   e.g., flag `eval(`, broad `# noqa`, or assertions trivially satisfied.
> Each fitness function gets a test; review the tests, not just the rule.

### Principle 6 — Prefer small, bespoke, legible tooling over heavyweight frameworks
Repo-specific scripts that reduce ambiguity beat generic MCP servers and
multi-agent frameworks for small/medium codebases. Build a tool only after a
need recurs; let usage shape it.

> **pySC:** A couple of helper scripts would pay off, e.g. an
> `explain-area`-style script that, given a module, prints its public symbols,
> who imports it, and the matching test file. Skip swarm frameworks and generic
> MCP servers unless a concrete bottleneck appears.

### Principle 7 — Separate responsibilities to keep context and incentives clean
The strongest structural idea: the agent that writes production code should not
also be the one that can relax the tests. Even without a multi-agent swarm, you
can get most of this benefit through **discipline and review gates**: treat
"edit production code" and "edit tests/specs" as separate steps, and review
spec changes especially carefully — they are the ultimate quality gate.

> **pySC:** No need for three standing agents at this size. Adopt the *rule*:
> when a change touches both `pySC/` and `tests/`, scrutinize the test diff
> independently and be suspicious of any loosened tolerance or deleted
> assertion. Encode this in the codex (Principle 4).

### Principle 8 — Scale the process to the codebase
Match ceremony to size and risk. A 70k-LOC multi-million-dollar product
justifies a constitution, swarm, and handoff gates. An 8k-LOC research library
justifies docs + CI + a codex + a few fitness functions. **Don't import
process you don't need** — it's pure drag.

### Principle 9 — Treat improvement as a habit (retrospect & sharpen)
After each substantial piece of work, ask: What did we learn? Which docs need
updating? Which new automated check is warranted? Did the tooling help? This
closes the loop and is what makes the codebase get *more* AI-friendly over
time rather than decaying. Eventually the retrospective itself becomes a
checklist/skill.

> **pySC:** Lightweight retro checklist (below). The trigger is the
> reflection-in-tests anecdote: every time an agent does something "obviously
> wrong," that's a missing explicit rule — document it, then automate it.

---

## Part 3 — Prioritized next steps for pySC

Ordered by leverage-to-effort:

1. **Add a test CI workflow** (`pytest` on push/PR, matrix over 3.9–3.12,
   fast subset gating + full suite). *Highest leverage; the safety net already
   exists but isn't enforced.* (Principle 3)
2. **Write a `CLAUDE.md` codex** capturing the API surface, import conventions,
   numerical-tolerance discipline, "never weaken tests," and stop conditions.
   (Principle 4)
3. **Create a small `docs/` knowledge base** (`architecture`, `domain`,
   `testing`, `development`), each ~200 lines, pointing at tests for exact
   behavior. (Principle 1)
4. **Add 1–3 architecture fitness functions** as ordinary pytest tests
   (import/layering boundaries; public-API import check). (Principle 5)
5. **Add one or two repo-specific helper scripts** only once a navigation pain
   recurs. (Principle 6)
6. **Adopt the retro checklist** as a habit after each notable change.
   (Principle 9)

Explicitly **not** recommended for pySC now: a 3-role agent swarm, SwarmForge,
generic MCP servers, or a full Gherkin/BDD migration. Revisit if the project
grows substantially or gains parallel contributors. (Principle 8)

---

## Appendix — Retro checklist (per significant change)

- [ ] What did we learn that wasn't written down?
- [ ] Which doc(s) need updating?
- [ ] Did any "obvious to me" rule get violated? → document it…
- [ ] …and can that rule become an automated check (fitness function / test)?
- [ ] Did the tooling/scripts help, hinder, or go unused?
- [ ] Is the public API in `pySC/__init__.py` still intact?
- [ ] Were any test tolerances loosened or assertions removed? Justified?

---

*Source: Seb (@plainionist), "How I Made My Brownfield Codebase AI-First."
Closing reference: Stephen Covey, "Habit #7 — Sharpen the Saw," The 7 Habits of
Highly Effective People.*
