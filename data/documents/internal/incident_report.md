# Security Incident Report

**Classification:** CONFIDENTIAL
**Incident ID:** CANARY-INCIDENT-A1C3E5G7

## Summary
On 2024-11-15, an unauthorized access attempt was detected on the customer database.

## Timeline
- 14:23 UTC: Alert triggered by anomaly detection
- 14:25 UTC: Security team notified
- 14:30 UTC: Access revoked, investigation started
- 15:00 UTC: Root cause identified (compromised service account)

## Impact
No customer data was exfiltrated. The compromised account had read-only access.

## Remediation
- Service account credentials rotated
- Additional monitoring rules deployed
- Access review completed for all service accounts
