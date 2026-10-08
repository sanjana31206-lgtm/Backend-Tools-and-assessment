# HubSpot Deals ETL - Test Results

## Test Environment
- Service: hubspot_deals
- Environment: Development
- API: HubSpot CRM v3 Deals
- Destination: PostgreSQL

## Test Results

| Test | Result |
|---|---|
| Service Health Check | PASS - HTTP 200 |
| HubSpot API Authentication | PASS |
| Scan Start API | PASS - HTTP 202 |
| HubSpot Deals Extraction | PASS |
| Records Extracted | 5 |
| PostgreSQL Records | 5 |
| Checkpoint Completion | PASS |
| Scan Status | completed |

## Scan
- Scan ID: dlt-test-scan-005
- Status: completed
- Records Extracted: 5
- Total Pages: 1
- Completion Status: success
- Destination: PostgreSQL

## Conclusion
The HubSpot Deals ETL service successfully authenticated with HubSpot, extracted all 5 test deals, completed the scan, and stored 5 records in PostgreSQL.
