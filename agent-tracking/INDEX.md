# Agent Tracking Index

One row per task. Newest at the bottom. Keep status current at every phase change.

Status: `scoping` · `researching` · `awaiting-approval` · `approved` · `in-progress` · `done` · `blocked` · `cancelled`

| Date | Slug | Type | Status | Summary | Report |
|------|------|------|--------|---------|--------|
| 2026-09-25 | 2026-09-25-security-api-logging | security | done | Security audit of API layer, logging and API-reachable webhook/SSRF path (ASVS L2, standard depth) | [report](reports/2026-09-25-security-api-logging.html) |
| 2026-09-25 | 2026-09-25-feature-secret-redaction | feature | done | Fix S-004 (mask webhook headers in reads) and S-005 (redact payload/URL from logs, run records, notify) | [report](reports/2026-09-25-feature-secret-redaction.html) |
