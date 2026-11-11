# ADR-P005: Stable TraceEvent and SSE transport

**Status:** proposed. **Context:** current tracer emits LangChain-related Span models; the frontend should not depend on framework internals. Need progressive display of nested calls and exact provenance.

**Decision:** versioned TraceEvent envelope with monotonically increasing sequence IDs, explicit run state and evidence events; normalize Python callbacks to protocol. Use SSE over authenticated GET for one-way updates, bounded replay buffer and reconnect. Store actual captured events for static Guided Replay. Map to OpenTelemetry conventions via an adapter.

**Alternatives:** poll results (simple but poor live inspection), WebSockets (more operations/complexity), direct callbacks into Streamlit (locks UI). **Trade-offs:** SSE transport and reconnection semantics. **Rollback:** polling same final result endpoint.
