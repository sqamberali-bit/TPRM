from enum import Enum


class VendorStatus(str, Enum):
    PROSPECTIVE = "prospective"
    ACTIVE = "active"
    OFFBOARDING = "offboarding"
    RETIRED = "retired"


class RiskStatus(str, Enum):
    OPEN = "open"
    IN_TREATMENT = "in_treatment"
    ACCEPTED = "accepted"
    ACCEPTED_TIMEBOXED = "accepted_timeboxed"
    CONTINGENT = "contingent"
    CLOSED = "closed"
    RESOLVED = "resolved"
    REMOVED = "removed"
    WITHDRAWN = "withdrawn"
    STALE = "stale"


class RiskSource(str, Enum):
    ASSESSMENT_REPORT = "assessment_report"
    UPGUARD = "upguard"
    MANUAL = "manual"


class Rating(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    NONE = "none"


class ClauseStatus(str, Enum):
    DRAFTED = "drafted"
    AGREED = "agreed"
    EXECUTED = "executed"


class ReportType(str, Enum):
    INITIAL = "initial"
    PERIODIC = "periodic"
    ADHOC = "adhoc"


class DataSensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class BusinessCriticality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AccessLevel(str, Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"


class DataVolume(str, Enum):
    MINIMAL = "minimal"
    MODERATE = "moderate"
    LARGE = "large"
    EXTENSIVE = "extensive"


class IntegrationDepth(str, Enum):
    STANDALONE = "standalone"
    API = "api"
    DEEP = "deep"
    EMBEDDED = "embedded"


class RegulatoryExposure(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class CertificationType(str, Enum):
    ISO27001 = "iso27001"
    SOC2_TYPE1 = "soc2_type1"
    SOC2_TYPE2 = "soc2_type2"
    IRAP = "irap"
    PCIDSS = "pcidss"
    OTHER = "other"


class FrameworkTag(str, Enum):
    NIST_CSF_2 = "nist_csf_2.0"
    ISO_27001_2022 = "iso_27001:2022"
    ESSENTIAL_EIGHT = "essential_eight"
    NSW_CSP = "nsw_csp"
    PPIP_MNDB = "ppip_mndb"


class AcceptanceAuthority(str, Enum):
    EXECUTIVE = "executive"
    SENIOR_MANAGEMENT = "senior_management"
    MANAGER = "manager"
    TEAM_LEAD = "team_lead"


class TriggerEventType(str, Enum):
    BREACH_NOTIFICATION = "breach_notification"
    REGULATORY_CHANGE = "regulatory_change"
    MAJOR_OUTAGE = "major_outage"
    ACQUISITION = "acquisition"
    DATA_INCIDENT = "data_incident"
    CONTRACT_RENEWAL = "contract_renewal"
    CERTIFICATION_LAPSE = "certification_lapse"
    MANUAL = "manual"


class ObligationType(str, Enum):
    PEN_TEST = "pen_test"
    INSURANCE = "insurance"
    BACKGROUND_CHECK = "background_check"
    AUDIT_REPORT = "audit_report"
    OTHER = "other"


class ExceptionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class EvidenceType(str, Enum):
    CERTIFICATE = "certificate"
    REPORT = "report"
    POLICY = "policy"
    SCREENSHOT = "screenshot"
    OTHER = "other"
