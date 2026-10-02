# HealthSetu Phase 29: Notification & Communication API Specifications

## 1. Recipient In-App Inbox & Notification APIs

### `GET /api/v1/notifications`
- **Description**: List active notifications in authenticated user's inbox.
- **Required Permission**: `notification:read`
- **Query Parameters**:
  - `unread_only`: boolean (default `false`)
  - `limit`: int (default `50`, max `100`)
  - `offset`: int (default `0`)
  - `category`: optional string (`CLINICAL_WORKFLOW`, `OPERATIONAL`, `SECURITY`, `ADMINISTRATIVE`)
- **Response**: `NotificationListResponse`

### `POST /api/v1/notifications`
- **Description**: Issue a new notification event (restricted to authorized clinical and administrative roles).
- **Required Permission**: `notification:create`
- **Body**: `NotificationCreate`
- **Response**: `201 Created` (`NotificationRead`)

### `GET /api/v1/notifications/{notification_id}`
- **Description**: Get single notification detail (enforces recipient ownership / BOLA protection).
- **Required Permission**: `notification:read`
- **Response**: `NotificationRead`

### `POST /api/v1/notifications/{notification_id}/read`
- **Description**: Mark notification as read.
- **Required Permission**: `notification:read`
- **Response**: `NotificationRead`

### `POST /api/v1/notifications/{notification_id}/dismiss`
- **Description**: Dismiss notification from inbox.
- **Required Permission**: `notification:dismiss`
- **Response**: `NotificationRead`

### `GET /api/v1/notification-preferences`
- **Description**: Retrieve communication preferences for authenticated user.
- **Required Permission**: `notification_preference:read`
- **Response**: `NotificationPreferences`

### `PUT /api/v1/notification-preferences`
- **Description**: Update communication channels, quiet hours, and localization.
- **Required Permission**: `notification_preference:manage`
- **Body**: `NotificationPreferencesUpdate`
- **Response**: `NotificationPreferences`

### `GET /api/v1/notification-deliveries/{delivery_id}`
- **Description**: Query channel delivery attempt status and provider transaction reference.
- **Response**: `NotificationDelivery`

---

## 2. Administrative Notification & Governance APIs

### `GET /api/v1/admin/notifications`
- **Description**: View notifications across system with operational filters.
- **Required Permission**: `admin:notification_view`

### `GET /api/v1/admin/notification-providers`
- **Description**: List registered provider adapters, latency, and health state.
- **Required Permission**: `admin:notification_view`

### `POST /api/v1/admin/notification-providers/{provider}/test`
- **Description**: Diagnostic connectivity test ping against provider adapter.
- **Required Permission**: `admin:notification_provider_test`

### `GET /api/v1/admin/notification-failures`
- **Description**: Query recent failed delivery attempts for incident diagnostics.
- **Required Permission**: `admin:notification_view`

### `POST /api/v1/admin/notifications/bulk`
- **Description**: Rate-controlled administrative bulk notification dispatch.
- **Required Permission**: `admin:notification_manage`
