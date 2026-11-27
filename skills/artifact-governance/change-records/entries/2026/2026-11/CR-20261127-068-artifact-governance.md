# CR-20261127-068 Artifact governance ownership

| Field | Value |
| --- | --- |
| Status | applied |
| Target Skill | artifact-governance |
| Issue | #68 |

## Summary

Transfer inventory, preview, archive verification, release, scheduling and restoration to the selected artifact-governance capability.

## Context And Problem

Baseline 1850854 only offered governance from the main Skill.

## Sections Changed

core-skill-md, scripts-and-validation, agent-metadata.

## Decision And Alternatives

Move the existing transaction and archive reader implementations. Retain the main command and original Python module imports as forwarding paths to the selected owner.

## Detailed Change

The inventory reads current asset declarations and effective revisions, as well as actual run originals. The schedule definition retains the selected main command path for startup without an inherited Python path.

## Impact Analysis

Existing approval digests, archive files, report links and per-file restart journals retain their formats.

## Validation Evidence

The independent entry test invokes inventory by both command paths. The inventory, retention, schedule XML, archive, release, resume and historical restoration tests cover existing transaction behavior.

## Safety And Privacy

Actual release exercises use isolated project copies. The source public run and historical versions remain in place.

## Risks And Follow-up

Changing an operating system schedule requires separate action authorization. This migration exercises schedule definition compatibility.
