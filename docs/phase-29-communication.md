# HealthSetu Phase 29: Communication Service & Multi-Channel Dispatch

## 1. Overview & Architecture

The `CommunicationService` coordinates outbound dispatches across physical transport channels while abstracting external vendor protocols behind the `NotificationProvider` interface.

```
                    ┌────────────────────────┐
                    │   NotificationService  │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │  CommunicationService  │
                    └───────────┬────────────┘
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  EmailProvider   │  │   SMSProvider    │  │   PushProvider   │
│ (Mock / SendGrid)│  │ (Mock / Twilio)  │  │   (Mock / FCM)   │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 2. Invariants & Controls

### 2.1 Contact Target Validation
- **Email**: Strict regex verification (`^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$`).
- **SMS**: E.164 phone formatting compliance with international prefix support.
- **Push**: Minimum 16-character hardware/APNS/FCM device registration token.

### 2.2 Rate Limiting
- Default rate limit: 30 requests per minute per recipient.
- Sliding window algorithm rejects bursts exceeding threshold with HTTP 429 (`RATE_LIMIT_EXCEEDED`).

### 2.3 Provider Failover
- Configurable failover (`NOTIFICATION_PROVIDER_FAILOVER_ENABLED`).
- When primary provider returns transient 5xx or connection timeout, automatically attempts secondary provider while preserving idempotency.

---

## 3. Normalized Delivery States

Provider-specific statuses (e.g., SMTP 250, Twilio queued, FCM 200) are normalized into standard HealthSetu `DeliveryStatus`:

- `QUEUED`: Enqueued for dispatch.
- `SENDING`: Currently in transit to upstream gateway.
- `SENT`: Gateway acknowledged receipt and accepted message.
- `DELIVERED`: Confirmed delivered to recipient endpoint.
- `FAILED`: Terminal or transient failure.
- `CANCELLED`: Aborted prior to transmission.
