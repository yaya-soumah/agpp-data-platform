# Release Process

## Purpose

This document defines how AGPP releases are prepared and documented.

---

## Release Workflow

1. Complete implementation.

2. Verify tests.

3. Complete code review.

4. Merge into `main`.

5. Update release notes.

6. Create Git tag.

---

## Versioning

AGPP follows Semantic Versioning.

Format:

MAJOR.MINOR.PATCH

Examples:

0.1.0

0.2.0

1.0.0

---

## Version Meaning

### MAJOR

Breaking architectural or public API changes.

---

### MINOR

New functionality without breaking compatibility.

---

### PATCH

Bug fixes and small improvements.

---

## Release Notes

Each release documents:

- Summary
- Features
- Fixes
- Documentation
- Breaking Changes (if any)

---

## Goals

A release should represent a stable milestone that another engineer can check out, build, and understand.
