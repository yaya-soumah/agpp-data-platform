# Commit Convention

## Purpose

Commit messages document the evolution of the AGPP Data Platform.

Every commit should describe one logical change.

---

## Standard

AGPP follows the Conventional Commits specification.

Format:

<type>: <description>

---

## Commit Types

### feat

New functionality.

Example:

feat: add supplier product extractor

---

### fix

Bug correction.

Example:

fix: prevent duplicate inventory records

---

### docs

Documentation only.

Example:

docs: add ADR-006

---

### refactor

Internal improvement without behavior change.

Example:

refactor: simplify configuration loading

---

### test

Tests only.

Example:

test: add transformer unit tests

---

### chore

Repository maintenance.

Example:

chore: initialize repository

---

### ci

Continuous Integration changes.

Example:

ci: add GitHub Actions workflow

---

## Guidelines

Commit messages should:

- use the imperative mood
- describe one logical change
- remain concise
- avoid vague wording

Avoid:

update

fix stuff

misc changes

Good examples:

feat: add warehouse loader

docs: update branching strategy

fix: handle missing supplier identifier
