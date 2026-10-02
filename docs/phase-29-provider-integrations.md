# HealthSetu Phase 29: Provider Integrations & Adapters

## 1. Provider Adapter Architecture

HealthSetu utilizes vendor-neutral adapters adhering to the `NotificationProvider` abstract base class (`app/integrations/notifications/base.py`):

```python
class NotificationProvider(ABC):
    @abstractmethod
    async def send(self, request: ProviderDeliveryRequest) -> ProviderDeliveryResult: ...
    @abstractmethod
    async def check_status(self, provider_message_id: str) -> DeliveryStatus: ...
    @abstractmethod
    async def cancel(self, provider_message_id: str) -> bool: ...
    @abstractmethod
    def validate_configuration(self) -> bool: ...
```

---

## 2. Integrated Adapters

### 2.1 Email Adapter (`MockEmailNotificationProvider`)
- **Channel**: `EMAIL`
- **Guards**:
  - Validates RFC-5322 email syntax.
  - Rejects CRLF characters in subjects to protect against SMTP header injection.
  - Normalizes gateway timeouts, rate limits (HTTP 429), and upstream SMTP 5xx errors.

### 2.2 SMS Adapter (`MockSMSNotificationProvider`)
- **Channel**: `SMS`
- **Guards**:
  - Validates E.164 phone number formatting.
  - **Strict PHI Filter**: Scans message content for sensitive clinical keywords (diagnosis, dosage, oncology narrative) and blocks raw transmission over unencrypted cellular networks.

### 2.3 Push Adapter (`MockPushNotificationProvider`)
- **Channel**: `PUSH`
- **Guards**:
  - Enforces minimum 16-character hardware/APNS/FCM device token length.
  - Handles `UNREGISTERED_TOKEN` failures when user uninstalls app or invalidates device token.

---

## 3. Diagnostic & Monitoring Commands

Admins and SREs can inspect provider health via:
- `GET /api/v1/admin/notification-providers`
- `POST /api/v1/admin/notification-providers/{provider}/test`
