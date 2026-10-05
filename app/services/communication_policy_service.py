"""Communication Policy, Rate Limiting, and Abuse Prevention Service (Phase 41).

Enforces:
- Actor-level message flooding protection
- Conversation creation rate limits
- Payload size boundaries (max 10,000 chars)
- Attachment validation (max 10MB, safe MIME types)
- Abuse detection
"""

from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

from app.core.exceptions import (
    AttachmentInvalidException,
    CommunicationRateLimitExceededException,
    MessageInvalidException,
    MessageTooLargeException,
)
from app.schemas.message import AttachmentReference


class CommunicationPolicyService:
    """Manages rate limits, size constraints, and payload hygiene."""

    def __init__(
        self,
        max_message_length: int = 10000,
        max_attachment_size_bytes: int = 10 * 1024 * 1024,
        message_rate_limit: int = 60,  # per minute
        conversation_rate_limit: int = 20,  # per minute
        enabled: bool = True,
    ) -> None:
        self._max_message_length = max_message_length
        self._max_attachment_size_bytes = max_attachment_size_bytes
        self._message_rate_limit = message_rate_limit
        self._conversation_rate_limit = conversation_rate_limit
        self._enabled = enabled

        self._lock = threading.Lock()
        self._rate_buckets: Dict[str, List[float]] = {}  # key -> timestamps

    def check_rate_limit(self, actor_id: str, action: str = "send_message") -> None:
        """Enforce rate limits per actor and action within a 60-second sliding window."""
        if not self._enabled:
            return

        limit = self._message_rate_limit if action == "send_message" else self._conversation_rate_limit
        bucket_key = f"{actor_id}:{action}"
        now = time.time()
        window_start = now - 60.0

        with self._lock:
            timestamps = self._rate_buckets.setdefault(bucket_key, [])
            # Prune expired timestamps
            self._rate_buckets[bucket_key] = [t for t in timestamps if t > window_start]
            current_count = len(self._rate_buckets[bucket_key])

            if current_count >= limit:
                raise CommunicationRateLimitExceededException(
                    message=f"Rate limit exceeded for action '{action}'. Limit is {limit} per minute."
                )

            self._rate_buckets[bucket_key].append(now)

    def validate_message_content(self, content: str) -> None:
        """Validate text payload size and formatting."""
        if not self._enabled:
            return

        if not content or not content.strip():
            raise MessageInvalidException("Message content cannot be empty.")

        if len(content) > self._max_message_length:
            raise MessageTooLargeException(
                f"Message length ({len(content)}) exceeds maximum permitted ({self._max_message_length} characters)."
            )

    def validate_attachments(self, attachments: Optional[List[AttachmentReference]]) -> None:
        """Validate attachment size and structure."""
        if not self._enabled or not attachments:
            return

        allowed_mime_prefixes = ("image/", "application/pdf", "text/plain", "application/json")
        for att in attachments:
            if not att.document_id or not att.file_name:
                raise AttachmentInvalidException("Attachment must contain valid document_id and file_name.")

            if att.size_bytes > self._max_attachment_size_bytes:
                raise AttachmentInvalidException(
                    f"Attachment '{att.file_name}' size ({att.size_bytes} bytes) exceeds limit ({self._max_attachment_size_bytes} bytes)."
                )

            if not any(att.content_type.startswith(prefix) for prefix in allowed_mime_prefixes):
                raise AttachmentInvalidException(
                    f"Attachment MIME type '{att.content_type}' is not permitted."
                )
