# HubSpot Deals - Database Schema Documentation

## 1. Overview

This document defines the PostgreSQL database schema for the HubSpot Deals ETL service.

The database stores HubSpot Deal records extracted from the HubSpot CRM API and includes ETL metadata for tracking extraction runs, tenants, and timestamps.

### Database

- Database: PostgreSQL
- Service: `hubspot_deals`
- Project: `hubspot-deals-etl`

---

## 2. Database Tables

The schema contains two main tables:

1. `deals` - stores extracted HubSpot Deal records.
2. `deal_sync_runs` - stores ETL extraction run information.

Relationship:

```text
deal_sync_runs 1 ---- N deals