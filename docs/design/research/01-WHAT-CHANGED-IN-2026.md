# Signals from 2026: Why This Portfolio Roadmap Exists

**Research cut-off:** 2026-11-11. These references justify *skills and research directions*, not a guarantee of hiring, product demand or future market structure.

| Source | Date | Verified public claim | Consequence for LedgerLens |
|---|---|---|---|
| CoderPad State of Tech Hiring | 2026 | survey identifies strong interest in AI application skills and higher importance of system design/debugging | demonstrate debugging and architecture, not only code generation |
| Anthropic research on employment | 2026-10-16 | at Anthropic, attention to agent output creates new coordination/oversight challenges | Human Attention and Review Queue Lab |
| LangChain 'Common Questions About Agent Evals' | 2026-10-15 | recommend code checks when possible, thread/trajectory eval and real trace feedback | multi-level eval with immutable datasets |
| LangChain agent observability/evals | 2026-03 | many teams trace but fewer evaluate; make failures into eval cases | Failure-to-regression compounding loop |
| Bank of England 2026 UK financial-services AI survey | 2026-10 | decision support significantly more prevalent than broad financial agent autonomy | design safe decision support rather than live money operations |
| IMF 'How Agentic AI Will Reshape Payments' | 2026-04 | early experimentation with agents across payment workflows; operational resilience matters | realistic domain use cases and failure labs |
| MCP specification | 2026-07-28 | stateless protocol core and authorization improvements | versioned typed MCP adapters with least privilege |
| NSA MCP security considerations | 2026-05-20 | integrating agents/tools expands security concerns in business and finance | tool identity, permission checking and egress controls |
| OWASP Top 10 for Agentic Applications | 2025-12 (2026 edition) | goal hijack, tool misuse, identity, memory poisoning etc | scripted safe adversarial tests |
| OpenTelemetry GenAI semantic conventions | 2026 | common event/span attributes and PII cautions | portable traces without secrets |
| OpenAI Agents SDK | current docs 2026-11 | agents as tools vs handoffs; code-driven vs model-driven orchestration | framework-independent comparison patterns |
| Temporal research | 2026-11 | durable workflows require explicit rules about what survives restarts | checkpoint and idempotence demonstrator |

## Grounded architectural conclusions

- Multiagent is **not inherently more accurate**. Adopt as a testable hypothesis with ablation, cost and risk controls.
- AI accuracy alone is insufficient for financial operations. Track evidence, escalation, abstention and the human review burden.
- The personal career bottleneck may be demo discoverability and independent validation. A keyless public app and credible case studies are early milestones.
- Agent monitoring isn't a substitute for evaluation; export failures into tests and documents.
- No real financial mutations in a portfolio application; mock safely and be explicit.

## Links

- https://coderpad.io/survey-reports/coderpad-state-of-tech-hiring-2026/
- https://www.anthropic.com/research/employment-at-anthropic
- https://www.langchain.com/blog/common-questions-about-agent-evals
- https://www.langchain.com/resources/llm-monitoring-observability
- https://www.bankofengland.co.uk/report/2026/artificial-intelligence-in-uk-financial-services-2026
- https://www.elibrary.imf.org/view/journals/068/2026/004/article-A001-en.xml
- https://blog.modelcontextprotocol.io/posts/2026-07-28/
- https://www.nsa.gov/Press-Room/Press-Releases-Statements/Press-Release-View/Article/4496698/nsa-releases-security-design-considerations-for-AI-driven-automation-leveraging/
- https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/
- https://openai.github.io/openai-agents-python/multi_agent/
- https://temporal.io/blog/durable-execution-means-deciding-what-survives-failure
