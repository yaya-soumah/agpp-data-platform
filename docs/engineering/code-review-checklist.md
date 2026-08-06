# Code Review Checklist

Every Pull Request should be reviewed using the following checklist.

---

## Architecture

- Project structure respected
- ADRs followed
- No unnecessary coupling
- Responsibilities clearly separated

---

## Code Quality

- Readable
- Maintainable
- No duplicated logic
- Appropriate abstractions

---

## Business Logic

- Business rules are correct
- Edge cases considered
- Validation implemented

---

## Error Handling

- Meaningful exceptions
- No silent failures
- Errors propagated correctly

---

## Logging

- Important events logged
- Appropriate log levels
- No sensitive information logged

---

## Testing

- Tests added where required
- Existing tests still pass

---

## Documentation

- Documentation updated
- ADR referenced if necessary
- README updated if applicable

---

## Git

- Branch name follows convention
- Commit messages follow Conventional Commits

---

## Final Decision

Approve only if:

- architecture remains consistent
- implementation is understandable
- changes are production-ready
