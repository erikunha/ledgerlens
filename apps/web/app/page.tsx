import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { buttonClasses } from "@/components/ui/Button";
import { CardSection } from "@/components/ui/Card";

/**
 * The home page of the public site.
 *
 * Why this file exists: the demo has two halves and a visitor has to be able to tell them apart
 * before anything happens. The recorded demo reads the published artifacts and calls nobody, and
 * the live mode asks the backend of the demo and asks for the key of the visitor. Both are
 * offered here, each one with the mode it runs in written down, because a recorded run is never
 * labelled live and a live run is never labelled recorded (ADR-040).
 */

export default function HomePage() {
  return (
    <div className="mx-auto flex w-full max-w-content flex-col gap-10 px-6 py-12">
      <header className="flex flex-col gap-4">
        <p className="text-xs font-medium uppercase tracking-wide text-text-subtle">
          Financial agents should show their work
        </p>
        <h1 className="max-w-3xl text-3xl font-semibold">
          Evidence-first payment investigation, with a trace you can read
        </h1>
        <p className="max-w-2xl text-text-muted">
          LedgerLens investigates payment complaints and shows the evidence behind every answer: the ledger
          rows it read, the policy it applied and the arithmetic it did. All the money of the demo is
          simulated.
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-2" aria-label="The two ways to see the demo">
        <CardSection
          title="Recorded demo"
          description="The published artifacts of a capture, played in the browser."
        >
          <div className="flex flex-col gap-3">
            <Badge tone="neutral">mode: deterministic_sandbox</Badge>
            <p className="text-sm text-text-muted">
              The demo reads the static artifacts of the site. It asks no provider, it needs no key and no
              network, and it runs the same way for every visitor.
            </p>
            <p className="text-sm text-text-subtle">
              Deterministic execution, with the scripted model and the recorded exchange rate. This is not a
              live execution and it calls no model.
            </p>
            <div>
              <Link className={buttonClasses("primary", "md")} href="/replay">
                Open the recorded demo
              </Link>
            </div>
          </div>
        </CardSection>

        <CardSection title="Live mode" description="Your own key, your own run, on the backend.">
          <div className="flex flex-col gap-3">
            <Badge tone="neutral">mode: live_agent</Badge>
            <p className="text-sm text-text-muted">
              You type the key of your provider and the run happens on the backend of the demo. The key is
              read once, from the field you typed, and it never reaches a URL, a header or a log. The caps of
              the run bound the calls of the run, not the bill of your provider.
            </p>
            <p className="text-sm text-text-subtle">
              The live mode is refused when the product runs offline: the server answers with the code
              LIVE_MODE_OFFLINE and the recorded demo keeps working exactly as before.
            </p>
            <div>
              <Link className={buttonClasses("secondary", "md")} href="/live">
                Open the live mode
              </Link>
            </div>
          </div>
        </CardSection>
      </section>
    </div>
  );
}
