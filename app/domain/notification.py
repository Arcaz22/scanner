from dataclasses import dataclass


@dataclass
class NotificationResult:
    sent: bool
    message: str = ""
