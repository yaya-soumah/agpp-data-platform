# Branching Strategy

## Purpose

This document defines the Git branching strategy used by the AGPP Data Platform.

The objective is to maintain a stable `main` branch while allowing new work to be developed, reviewed, and tested independently.

---

## Branch Types

### Main

The `main` branch represents the production-ready state of the repository.

Rules:

- Direct commits are prohibited.
- Every change must arrive through a Pull Request.
- The branch should always remain stable.

---

### Feature Branches

New work is developed in feature branches.

Naming convention:

feature/<short-description>

Examples:

feature/repository-initialization

feature/logging-platform

feature/configuration-loader

---

### Bug Fix Branches

Bug fixes use the following naming convention:

fix/<short-description>

Example:

fix/database-timeout

---

### Documentation Branches

Documentation improvements use:

docs/<short-description>

Example:

docs/update-readme

---

### Refactoring Branches

Internal improvements that do not change behavior use:

refactor/<short-description>

Example:

refactor/configuration-service

---

## Development Workflow

Every feature follows the same lifecycle:

Main
↓
Feature Branch
↓
Implementation
↓
Commit
↓
Push
↓
Pull Request
↓
Code Review
↓
Approval
↓
Merge into Main

---

## Branch Lifetime

Feature branches should be short-lived.

Once merged:

- delete the remote branch
- delete the local branch

---

## Goals

This strategy ensures:

- stable production history
- isolated development
- easier reviews
- traceable engineering decisions
