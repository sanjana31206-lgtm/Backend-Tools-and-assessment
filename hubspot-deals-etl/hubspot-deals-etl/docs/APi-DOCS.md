# HubSpot Deals - API Documentation

## 📋 Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Base URL](#base-url)
4. [Deals API Endpoint](#deals-api-endpoint)
5. [Query Parameters](#query-parameters)
6. [Response Structure](#response-structure)
7. [Pagination](#pagination)
8. [Deal Properties](#deal-properties)
9. [Error Handling](#error-handling)
10. [Rate Limiting](#rate-limiting)
11. [Examples](#examples)
12. [Changelog](#changelog)

---

## 🔍 Overview

The HubSpot Deals API is used to retrieve deal records from HubSpot CRM.

The `hubspot_deals` extraction service connects to the HubSpot CRM API and extracts deal information for downstream processing and storage.

### API Version

* **API:** HubSpot CRM API
* **CRM Object:** Deals
* **Endpoint:** `/crm/v3/objects/deals`
* **HTTP Method:** `GET`
* **Content Type:** `application/json`
* **Base URL:** `https://api.hubapi.com`

### Key Features

* Retrieve HubSpot deal records.
* Request specific deal properties.
* Support pagination for large result sets.
* Include or exclude archived deals.
* Authenticate using a HubSpot Service Key / access token.
* Handle API errors and rate limiting.

---

## 🔐 Authentication

HubSpot API requests require authentication using a valid access token.

For this integration, the credential is stored outside the source code and supplied through an environment variable.

### Environment Variable

```text
HUBSPOT_ACCESS_TOKEN
```

### Authentication Header

```http
Authorization: Bearer YOUR_HUBSPOT_ACCESS_TOKEN
```

The actual access token must never be committed to Git or included in this documentation.

### Required Permission

The integration requires permission to read HubSpot deal records:

```text
crm.objects.deals.read
```

### Example

```http
GET https://api.hubapi.com/crm/v3/objects/deals
Authorization: Bearer YOUR_HUBSPOT_ACCESS_TOKEN
Content-Type: application/json
```

HubSpot's current Service Keys provide scoped account-level API access and are intended as the modern replacement for legacy private-app credentials.

---

## 🌐 Base URL

All requests to the HubSpot CRM API use:

```text
https://api.hubapi.com
```

### Deals API Base Endpoint

```text
https://api.hubapi.com/crm/v3/objects/deals
```

### Endpoint

```http
GET /crm/v3/objects/deals
```

---

## 📊 Deals API Endpoint

### Get Deals

**GET**

```text
/crm/v3/objects/deals
```

Retrieves a collection of HubSpot deal records.

### Request

```http
GET https://api.hubapi.com/crm/v3/objects/deals
```

### Example Request With Parameters

```http
GET https://api.hubapi.com/crm/v3/objects/deals?limit=10&properties=dealname,amount,dealstage,pipeline,closedate
```

### Required Headers

```http
Authorization: Bearer YOUR_HUBSPOT_ACCESS_TOKEN
Content-Type: application/json
```

---

## 🔎 Query Parameters

| Parameter    | Type    | Required | Description                                                |
| ------------ | ------- | -------- | ---------------------------------------------------------- |
| `limit`      | integer | No       | Maximum number of records returned in one request          |
| `after`      | string  | No       | Pagination cursor used to retrieve the next set of records |
| `properties` | string  | No       | Comma-separated list of deal properties to return          |
| `archived`   | boolean | No       | Controls whether archived records are included             |

### `limit`

Controls the number of deals requested.

Example:

```text
?limit=10
```

### `after`

Used for pagination.

Example:

```text
?limit=10&after=10
```

The value should be taken from the pagination information returned by the previous API response.

### `properties`

Specifies which deal properties should be returned.

Example:

```text
?properties=dealname,amount,dealstage,pipeline,closedate
```

### `archived`

Controls whether archived records are included.

Example:

```text
?archived=true
```

### Combined Example

```text
https://api.hubapi.com/crm/v3/objects/deals?limit=10&properties=dealname,amount,dealstage,pipeline,closedate&archived=false
```

---

## 📦 Response Structure

A successful request returns a JSON object containing a `results` array.

### Example Response

```json
{
  "results": [
    {
      "id": "123456789",
      "properties": {
        "dealname": "Example Deal",
        "amount": "5000",
        "dealstage": "contractsent",
        "pipeline": "default",
        "closedate": "2026-10-15T00:00:00Z"
      },
      "createdAt": "2026-10-01T10:30:00Z",
      "updatedAt": "2026-10-03T12:00:00Z",
      "archived": false
    }
  ],
  "paging": {
    "next": {
      "after": "123456789",
      "link": "https://api.hubapi.com/crm/v3/objects/deals?after=123456789"
    }
  }
}
```

### Response Fields

| Field                  | Type    | Description                                            |
| ---------------------- | ------- | ------------------------------------------------------ |
| `results`              | array   | Collection of returned deal records                    |
| `results[].id`         | string  | Unique HubSpot deal record ID                          |
| `results[].properties` | object  | Requested deal property values                         |
| `results[].createdAt`  | string  | Deal creation timestamp                                |
| `results[].updatedAt`  | string  | Last update timestamp                                  |
| `results[].archived`   | boolean | Indicates whether the deal is archived                 |
| `paging`               | object  | Pagination information when more records are available |
| `paging.next.after`    | string  | Cursor for the next page                               |
| `paging.next.link`     | string  | URL for retrieving the next page                       |

---

## 📄 Pagination

HubSpot returns pagination information when additional records are available.

The integration should use the `after` value from the response to retrieve the next page.

### First Request

```http
GET https://api.hubapi.com/crm/v3/objects/deals?limit=10
```

### Next Request

```http
GET https://api.hubapi.com/crm/v3/objects/deals?limit=10&after=123456789
```

### Pagination Example

```json
{
  "results": [
    {
      "id": "123456789",
      "properties": {
        "dealname": "Example Deal"
      }
    }
  ],
  "paging": {
    "next": {
      "after": "123456790",
      "link": "https://api.hubapi.com/crm/v3/objects/deals?after=123456790"
    }
  }
}
```

The extraction service should continue requesting pages until the response no longer contains a `paging.next` object.

---

## 🧾 Deal Properties

HubSpot Deals contain standard/default properties as well as potentially account-specific custom properties.

The exact complete property set can vary between HubSpot accounts because administrators can create custom deal properties. Therefore, the integration should not assume that a fixed list represents every property available in every account.

### Common Deal Properties

| Property                               | Description                                              |
| -------------------------------------- | -------------------------------------------------------- |
| `dealname`                             | Name of the deal                                         |
| `amount`                               | Monetary value associated with the deal                  |
| `dealstage`                            | Current stage of the deal                                |
| `pipeline`                             | Pipeline containing the deal                             |
| `closedate`                            | Expected or actual close date                            |
| `hubspot_owner_id`                     | HubSpot owner associated with the deal                   |
| `createdate`                           | Date the deal was created                                |
| `hs_lastmodifieddate`                  | Date the deal was last modified                          |
| `hs_object_id`                         | HubSpot object identifier                                |
| `dealtype`                             | Type/category of the deal                                |
| `description`                          | Description of the deal                                  |
| `hs_priority`                          | Deal priority                                            |
| `hs_forecast_amount`                   | Forecast amount                                          |
| `hs_forecast_category`                 | Forecast category                                        |
| `hs_manual_forecast_category`          | Manually selected forecast category                      |
| `hs_deal_stage_probability`            | Probability associated with the current deal stage       |
| `hs_is_closed`                         | Indicates whether the deal is closed                     |
| `hs_is_closed_won`                     | Indicates whether the deal is closed and won             |
| `hs_is_open_count`                     | Indicates whether the deal is counted as open            |
| `hs_num_associated_contacts`           | Number of contacts associated with the deal              |
| `hs_num_associated_deal_registrations` | Number of associated deal registrations                  |
| `hs_num_of_sales_activities`           | Number of sales activities                               |
| `hs_num_target_accounts`               | Number of target accounts                                |
| `hs_sales_email_last_replied`          | Information related to the most recent sales email reply |

### Retrieving the Available Properties

For a complete and account-specific list of deal properties, the integration can retrieve the Deals property definitions through HubSpot's CRM Properties API.

```http
GET https://api.hubapi.com/crm/v3/properties/deals
```

Example:

```powershell
$headers = @{
    Authorization = "Bearer $env:HUBSPOT_ACCESS_TOKEN"
}

$properties = Invoke-RestMethod `
    -Uri "https://api.hubapi.com/crm/v3/properties/deals" `
    -Method Get `
    -Headers $headers

$properties | ConvertTo-Json -Depth 20
```

This approach is important because HubSpot accounts may contain custom deal properties in addition to the standard/default properties.

HubSpot's developer documentation provides searchable CRM object-definition information for Deals, including default property definitions.

---

## ⚠️ Error Handling

The integration should handle common HTTP errors returned by HubSpot.

### 400 — Bad Request

Occurs when the request contains invalid parameters or property names.

Example:

```json
{
  "status": "error",
  "message": "Invalid request",
  "correlationId": "example-correlation-id"
}
```

**Action:** Check the endpoint, query parameters, and requested properties.

---

### 401 — Unauthorized

Occurs when the authentication credential is missing, invalid, or expired/revoked.

Example:

```json
{
  "status": "error",
  "message": "Authentication credentials not found",
  "correlationId": "example-correlation-id"
}
```

**Action:** Verify `HUBSPOT_ACCESS_TOKEN` and the Authorization header.

---

### 403 — Forbidden

Occurs when the authenticated credential does not have sufficient permission.

**Action:** Verify that the integration has:

```text
crm.objects.deals.read
```

---

### 404 — Not Found

Occurs when a requested resource or endpoint does not exist.

**Action:** Verify the API URL and object identifier.

---

### 429 — Too Many Requests

Occurs when API rate limits are exceeded.

**Action:**

1. Stop sending requests temporarily.
2. Respect the `Retry-After` response information when provided.
3. Retry using controlled backoff.
4. Avoid unnecessary repeated requests.

---

### 500 — Internal Server Error

Indicates an unexpected server-side problem.

**Action:** Retry the request with appropriate backoff and log the error/correlation information.

---

## 🚦 Rate Limiting

HubSpot APIs enforce rate limits to protect the platform and maintain service availability.

The integration should therefore:

* Avoid unnecessary API requests.
* Process records in pages.
* Respect HTTP `429` responses.
* Implement retry/backoff logic.
* Log API failures.
* Avoid tight retry loops.

Rate limits can vary depending on the HubSpot account/subscription and authentication/application configuration. HubSpot has changed API limits over time, so the integration should not hard-code an assumed universal rate limit.

---

## 💻 Examples

### PowerShell

```powershell
$headers = @{
    Authorization = "Bearer $env:HUBSPOT_ACCESS_TOKEN"
}

$response = Invoke-RestMethod `
    -Uri "https://api.hubapi.com/crm/v3/objects/deals?limit=10&properties=dealname,amount,dealstage,pipeline,closedate" `
    -Method Get `
    -Headers $headers

$response | ConvertTo-Json -Depth 10
```

### Python

```python
import os
import requests

access_token = os.environ["HUBSPOT_ACCESS_TOKEN"]

url = "https://api.hubapi.com/crm/v3/objects/deals"

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

params = {
    "limit": 10,
    "properties": "dealname,amount,dealstage,pipeline,closedate",
    "archived": "false"
}

response = requests.get(
    url,
    headers=headers,
    params=params,
    timeout=30
)

response.raise_for_status()

data = response.json()

print(data)
```

### cURL

```bash
curl --request GET \
  --url "https://api.hubapi.com/crm/v3/objects/deals?limit=10&properties=dealname,amount,dealstage,pipeline,closedate" \
  --header "Authorization: Bearer YOUR_HUBSPOT_ACCESS_TOKEN" \
  --header "Content-Type: application/json"
```

---

## 🧪 API Integration Test

The HubSpot Deals endpoint was tested using PowerShell.

### Test Request

```text
GET /crm/v3/objects/deals?limit=10&properties=dealname,amount,dealstage,pipeline,closedate
```

### Test Result

```json
{
  "results": []
}
```

### Interpretation

The API request was successfully authenticated and processed, but the HubSpot account returned no deal records.

An empty `results` array means that no deal records were returned for the account at the time of testing.

---

## 🔒 Security Guidelines

* Never commit the HubSpot access token to Git.
* Never place the real access token inside documentation.
* Store credentials in environment variables or an approved secret-management system.
* Do not print credentials in application logs.
* Rotate credentials if they are accidentally exposed.
* Use the minimum required HubSpot permissions.

---

## 🔌 Service REST API Endpoints

The `hubspot_deals` service exposes REST endpoints for controlling and monitoring extraction jobs.

### Start Extraction

**POST**

```text
/scan/start

## 📌 API Summary

| Item            | Value                             |
| --------------- | --------------------------------- |
| Service         | `hubspot_deals`                   |
| API             | HubSpot CRM API                   |
| Object          | Deals                             |
| Version         | v3                                |
| Method          | `GET`                             |
| Endpoint        | `/crm/v3/objects/deals`           |
| Base URL        | `https://api.hubapi.com`          |
| Authentication  | Bearer access token / Service Key |
| Required Scope  | `crm.objects.deals.read`          |
| Pagination      | Cursor-based using `after`        |
| Response Format | JSON                              |

---

## 📝 Changelog

### 2026-10-04

* Replaced generic calendar extraction API documentation with HubSpot Deals API documentation.
* Added HubSpot Deals authentication details.
* Added Deals API endpoint and query parameters.
* Added response and pagination documentation.
* Added deal property documentation.
* Added error handling and rate-limiting guidance.
* Added PowerShell, Python, and cURL examples.
* Added API integration test result.
* Added security guidelines.
