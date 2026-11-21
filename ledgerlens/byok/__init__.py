"""The live mode of the demo: the credential of the visitor, the model registry and the budget of a run.

Why this package exists: the third slice of the v3 cycle lets a visitor run a real case with a key of their own. The
key is the dangerous part of that feature, so the pieces that touch it live together in a package of the domain, with
no import of the API layer and no SQL anywhere.

What the package holds today:

* `ledgerlens.byok.vault`: the credential vault, the in-process memory that maps an opaque handle to a provider
  secret, bounded and expiring (FR-002, FR-003, FR-004, FR-005, FR-006, FR-022, FR-023);
* `ledgerlens.byok.errors`: the refusals of the live mode, one error per reason, each with a readable message;
* `ledgerlens.byok.registry`: the server side allowlist of the models that were really tested, with the provenance of
  the price of each one (FR-011, FR-015, FR-016, FR-027, FR-030, FR-031);
* `ledgerlens.byok.budget`: the coordinator of the caps of a run and the report of what the run cost (FR-009,
  FR-010, FR-011, FR-012);
* `ledgerlens.byok.adapter`: the interface of a provider, the fake one of the tests, the rule of the endpoint and
  the boundary where the credential of a run is scrubbed out of the error of a provider (FR-007, FR-017, FR-018).
  It also holds the contract of a tool calling turn: the schemas of the tools the model may call, the message that
  is the answer of a tool with the identifier of the call it answers, the calls the provider asked for, and the
  pure converters between the domain and the wire of the provider (FR-012). The rule of the type of the arguments
  of a call is public there and it is one rule: `arguments_text`, because every layer that reads the calls of a
  tool has to read them with the rule of the domain and not with a copy of it (FR-012).

Why the names are re-exported here: a caller of the live mode has one import for the pieces it needs and for the
refusals it may have to answer, and the names of the package are the public names of the slice.

Why the refusals of every module belong to one family: the model that is not allowed and the endpoint that is refused
are raised from their own modules, but they descend from the `ByokError` of this package, so a caller catches the
whole family with one name.
"""

from ledgerlens.byok.adapter import (
    ALLOWED_ENDPOINTS,
    ENDPOINT_LINK_LOCAL,
    ENDPOINT_LOOPBACK,
    ENDPOINT_NOT_A_URL,
    ENDPOINT_NOT_HTTPS,
    ENDPOINT_NOT_PUBLISHED,
    ENDPOINT_UNKNOWN_PROVIDER,
    EndpointRefused,
    EndpointVerdict,
    FakeProviderAdapter,
    LangChainProviderAdapter,
    ProviderAdapter,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
    ToolCall,
    ToolSchema,
    arguments_text,
    build_adapter,
    endpoint_refusal,
    endpoint_verdict,
    request_from_wire,
    request_to_wire,
    response_from_wire,
    response_to_wire,
    validate_endpoint,
)
from ledgerlens.byok.budget import (
    BudgetCoordinator,
    BudgetExceededError,
    BudgetRefused,
    CostReport,
    UsageRefused,
)
from ledgerlens.byok.errors import (
    ByokError,
    CapabilityMissing,
    ContractRefused,
    CredentialExpired,
    CredentialRefused,
    CredentialRevoked,
    CredentialUnknown,
    ProviderCallFailed,
    UnknownProvider,
)
from ledgerlens.byok.registry import (
    ALLOWLIST,
    ARCHITECTURE_CAPABILITIES,
    CAPABILITIES,
    CATALOGUE_CAPABILITY,
    PROVIDERS,
    STATUSES,
    Capability,
    ModelNotAllowed,
    ModelProfile,
    Pricing,
    ProfileStatus,
    ProviderRegistry,
    required_capabilities,
)
from ledgerlens.byok.vault import (
    DEFAULT_MAX_ENTRIES,
    DEFAULT_MAX_FAILURES,
    DEFAULT_TTL_SECONDS,
    CredentialHandle,
    CredentialVault,
)

__all__ = [
    "ALLOWED_ENDPOINTS",
    "ALLOWLIST",
    "ARCHITECTURE_CAPABILITIES",
    "CAPABILITIES",
    "CATALOGUE_CAPABILITY",
    "DEFAULT_MAX_ENTRIES",
    "DEFAULT_MAX_FAILURES",
    "DEFAULT_TTL_SECONDS",
    "ENDPOINT_LINK_LOCAL",
    "ENDPOINT_LOOPBACK",
    "ENDPOINT_NOT_A_URL",
    "ENDPOINT_NOT_HTTPS",
    "ENDPOINT_NOT_PUBLISHED",
    "ENDPOINT_UNKNOWN_PROVIDER",
    "PROVIDERS",
    "STATUSES",
    "BudgetCoordinator",
    "BudgetExceededError",
    "BudgetRefused",
    "ByokError",
    "Capability",
    "CapabilityMissing",
    "ContractRefused",
    "CostReport",
    "CredentialExpired",
    "CredentialHandle",
    "CredentialRefused",
    "CredentialRevoked",
    "CredentialUnknown",
    "CredentialVault",
    "EndpointRefused",
    "EndpointVerdict",
    "FakeProviderAdapter",
    "LangChainProviderAdapter",
    "ModelNotAllowed",
    "ModelProfile",
    "Pricing",
    "ProfileStatus",
    "ProviderAdapter",
    "ProviderCallFailed",
    "ProviderMessage",
    "ProviderRegistry",
    "ProviderRequest",
    "ProviderResponse",
    "ToolCall",
    "ToolSchema",
    "UnknownProvider",
    "UsageRefused",
    "arguments_text",
    "build_adapter",
    "endpoint_refusal",
    "endpoint_verdict",
    "request_from_wire",
    "request_to_wire",
    "required_capabilities",
    "response_from_wire",
    "response_to_wire",
    "validate_endpoint",
]
