# HealthSetu Phase 28: Usage Governance & Cost Management

## 1. Overview & Objectives

Usage Governance guarantees that external integrations, platform compute, AI models, and asynchronous workers operate within safe capacity boundaries and financial quotas.

## 2. Resource & Cost Categorization

Consumption tracking divides infrastructure load into distinct operational categories:

| Category | Unit of Measure | Description |
|:---|:---|:---|
| **AI_INFERENCE** | Total Tokens ($Prompt + Completion$) | Telemetry for LLM calls (e.g. Gemini 1.5 Pro/Flash). Sanitized prompts only. |
| **OCR_DOCUMENT_PAGES** | Pages Processed | Scanned image/PDF pages passed through OCR engines. |
| **MEDICATION_SAFETY_CHECKS** | Safety Queries | Invocations of clinical interaction and contraindication engines. |
| **MEDICATION_TERMINOLOGY** | Concept Lookups | RxNorm and SNOMED CT terminology searches. |
| **INTEROPERABILITY_TRANSFERS** | FHIR/HL7 Bundles | Inbound/outbound clinical payload exchange volume. |
| **STORAGE_CONSUMPTION** | GB-Months | Encrypted object storage utilization. |
| **QUEUE_MESSAGING** | Ingested Messages | Background worker message ingestion volume. |
| **COMPUTE_API_VOLUME** | HTTP API Invocations | Base platform API throughput. |

## 3. Usage Governance Controls

1. **Threshold Warnings**: Invocations exceeding configured capacity trigger `UsageAnomaly` alerts.
2. **Rate Limit Analytics**: Invocations rejected by rate-limiting middleware (`HTTP 429`) are tracked under `RATE_LIMIT_TRIGGERED` to identify capacity saturation without exposing client tokens.
3. **Query Range Limits**: Analytical queries are restricted to a maximum historical window (`ANALYTICS_MAX_QUERY_RANGE_DAYS=90`) to prevent heavy unindexed queries from overloading the database.
4. **Data Retention**: Raw telemetry events are automatically pruned according to `ANALYTICS_RETENTION_DAYS=90` to conserve storage while maintaining aggregated time-series trends.
