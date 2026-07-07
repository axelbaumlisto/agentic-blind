# Test fixture for sanitize.py (all 4 leak classes + 3 false-positive stems)

## Class 1: review trail
Budget raised to $50 (fixed by review #4). REVISION 3 applied.
This was flagged in round #2 of the blind run.

## Class 2: resolution markers
Threshold ≥14 days — СОГЛАСОВАНО со step 1.
VERIFIED via API: both campaigns budget-bound. Dispute settled by query.

## Class 3: intent justifications
Buffer set to 20% (intentional buffer). Value corrected to 35 (corrected to match).

## Class 4: provenance headers
Sources: BLIND_review_1.md, CLEAN_review_2.md
Changelog: r1 fixed math, r2 reverted geo change.

## False positives (must survive via --allow)
Task 7: сквозная согласованность plan schema.
The DNS query returned unresolved hostnames.
Icons are left-aligned in the sidebar.
