from enum import Enum


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    RECEPTIONIST = "receptionist"
    TRAINER = "trainer"
    MEMBER = "member"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    PAUSED = "paused"
    PENDING = "pending"
    CANCELLED = "cancelled"


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    LEAVE = "leave"


class AttendanceSource(str, Enum):
    BIOMETRIC = "biometric"
    MANUAL = "manual"
    QR = "qr"
    FACE_RECOGNITION = "face_recognition"


class PaymentStatus(str, Enum):
    PAID = "paid"
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    BANK_TRANSFER = "bank_transfer"
    ONLINE = "online"


class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    SYSTEM = "system"


# Default pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
