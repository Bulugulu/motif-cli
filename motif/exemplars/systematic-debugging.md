---
name: systematic-debugging
description: "Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes"
source: antigravity-awesome-skills (MIT)
---

# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work

**Don't skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)

## The Four Phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Read Error Messages Carefully**
   - Don't skip past errors or warnings
   - Read stack traces completely
   - Note line numbers, file paths, error codes

2. **Reproduce Consistently**
   - Can you trigger it reliably?
   - What are the exact steps?
   - If not reproducible, gather more data -- don't guess

3. **Check Recent Changes**
   - What changed that could cause this?
   - Git diff, recent commits
   - New dependencies, config changes

4. **Gather Evidence in Multi-Component Systems**
   - Log what data enters/exits each component boundary
   - Verify environment/config propagation
   - Run once to gather evidence showing WHERE it breaks
   - THEN investigate that specific component

5. **Trace Data Flow**
   - Where does bad value originate?
   - What called this with bad value?
   - Keep tracing up until you find the source
   - Fix at source, not at symptom

### Phase 2: Pattern Analysis

1. **Find Working Examples** -- Locate similar working code in same codebase
2. **Compare Against References** -- Read reference implementation COMPLETELY
3. **Identify Differences** -- List every difference, however small
4. **Understand Dependencies** -- What other components does this need?

### Phase 3: Hypothesis and Testing

1. **Form Single Hypothesis** -- "I think X is the root cause because Y"
2. **Test Minimally** -- Smallest possible change, one variable at a time
3. **Verify Before Continuing** -- Didn't work? Form NEW hypothesis. Don't stack fixes.
4. **When You Don't Know** -- Say so. Don't pretend.

### Phase 4: Implementation

1. **Create Failing Test Case** -- Simplest possible reproduction
2. **Implement Single Fix** -- ONE change at a time, no "while I'm here" improvements
3. **Verify Fix** -- Test passes? No other tests broken?
4. **If 3+ Fixes Failed** -- STOP. Question the architecture. Discuss before attempting more fixes.

## Red Flags -- STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- Proposing solutions before tracing data flow

**ALL of these mean: STOP. Return to Phase 1.**

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, gather evidence | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare | Identify differences |
| **3. Hypothesis** | Form theory, test minimally | Confirmed or new hypothesis |
| **4. Implementation** | Create test, fix, verify | Bug resolved, tests pass |
