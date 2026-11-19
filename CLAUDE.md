# construction-os-workbench

<!-- standard: design/_template/repo/CLAUDE.md v1
     Sections 1–6 are the standard: copy them unchanged, filling in only the <angle brackets>.
     Section 7 is this repository's own. To change a standard rule here, say so under
     "Overrides" in section 7, with the reason. -->

## 1. What this is

The Construction OS document workbench: the application that generates governed
construction documents from a company's package, and reads only that package. The first
package is `construction-os-corpus`, cloned next to this repository.
Status: active.

## 2. Design

The design docs for this repository are in the `design` repository, cloned next to this
one, at `../design/construction-os/document-workbench/`. Pull it before planning.

Before proposing work, read in this order (skip any the project doesn't have yet):

1. `../design/construction-os/brief.md`: why it exists and for whom
2. `../design/construction-os/product-spec.md`: what the product must do, by capability ID
3. `../design/construction-os/architecture.md` and `principles.md`: how the parts fit, and
   the rules every design decision follows
4. `../design/construction-os/corpus/spec.md`: the domain
5. `../design/construction-os/document-workbench/spec.md`: a pointer to the corpus spec, and
   this component's boundaries
6. `../design/construction-os/document-workbench/design.md`: how it works, and the decision log
7. `../design/construction-os/document-workbench/<slice>-design.md`: the build design for the slice
   the issue belongs to (today: `pco-design.md`)
8. `../design/construction-os/document-workbench/plan.md`: the milestones still ahead

- **Design leads, code follows.** Never edit design docs from this repository. If the
  work needs a change to what the product does, to a requirement or to the architecture,
  stop and propose the change. Don't build ahead of the design.
- **When the design is silent, ask.** Don't improvise behavior, copy or scope.
- **When the design and this repository disagree, say so.** Don't guess which is right.
- A synced design file starts with a header naming its Claude Doc. If the two differ,
  the Claude Doc is current.

## 3. How work happens

- **The issue is the plan.** Work only from a GitHub issue, and read it first
  (`gh issue view <N>`). The issue authorizes the work; the spec and design constrain
  how it's done. If they conflict, stop and say so. With no issue, write the work up as
  a proposed issue and wait.
- One issue, one branch, one pull request. Branch name: `issue-<N>-<short-description>`.
- Anything outside the issue gets a new issue. Don't widen the scope.
- Never commit to `main`. Never merge: Justin reviews and merges.

## 4. Checks

- Run the checks listed in section 7 before opening a pull request, and paste the
  results into it.
- A failure is never ignored. Either the change is wrong or the check is; say which.
- Never change an expected result to make a check pass. Report the mismatch and stop.

## 5. Every pull request

Fill in `.github/pull_request_template.md`:

- `Closes #<N>`, and what changed and why, in plain English.
- How each acceptance criterion in the issue was checked.
- **Decisions (proposed):** choices made while coding: the decision, the options, why,
  and what would change it. Merging the pull request approves them.
- **Build notes:** what you did, what broke, what it taught.

## 6. Roll-up, ask before, never

**Roll-up.** Ask "Roll up to design?" when a pull request you opened is merged, when an
issue or milestone is done, and about every ten turns of work since you last asked.

- On yes: collect Decisions and Build notes from pull requests merged since the last
  roll-up (the latest "Roll-up:" line in
  `../design/construction-os/document-workbench/build-log.md`). Propose decisions for the
  decision log in `../design/construction-os/document-workbench/design.md` and findings for
  `../design/construction-os/document-workbench/build-log.md`, ending with
  the line `Roll-up: <repo> #<first>–#<last>`. For files synced from Claude Docs, add
  them as suggestions in the Claude Doc if you have the Docs connector; otherwise give
  Justin the text to paste. For repo-authored files, open a pull request in `design`.
- On no: don't ask again for another ten turns.
- Nothing enters the design record until Justin approves it.

**Ask before:**

- adding a dependency
- changing a prompt, tool description, rubric, or anything else that changes what a
  model decides
- anything not in the issue

**Never:**

- read, print or edit `.env`. Secrets live only there; `.env.example` holds key names only
- commit secrets, API keys or real customer data
- rewrite git history

## 7. This repository

- **Layout:** `src/construction_os/` is the package: `drafting/`, `pricing/`, `rendering/`,
  `projects/` (the project store), `acceptance.py` (grading against the package's
  acceptance cases), `conditions.py`, `draft.py` (the drafting CLI) and
  `validate.py` (the package validator);
  `schemas/` holds JSON schemas; `scripts/` holds tools that are never run in CI
  (`live_eval.py`); `tests/` holds the tests and `tests/fixtures/`, a fictional company.
  README.md describes the same folders for people; when a folder is added, moved or
  retired, update both.
- **Run:** `python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"`, then
  `cp .env.example .env`. Drafting, rendering and validation commands are in README.md.
- **Checks:** every pull request runs `.venv/bin/pytest` and
  `.venv/bin/python -m construction_os.validate --corpus ../construction-os-corpus`.
- **Conventions:**
  - **No company content, ever.** No company names, rates, rules, clause text or
    templates. Everything company-specific is read from the package. Test fixtures use
    clearly fictional companies. Pointed at another company's package, the same code
    produces that company's documents.
  - Code computes every amount; the model never writes a price.
  - The Python package is still named `construction_os`; renaming it is its own issue.
- **Overrides:** section 2 adds the corpus spec to the reading list and section 6 names the
  roll-up files by path, because the corpus is its own component (design PR #25) and its
  spec is specific to Construction OS, not the template.
