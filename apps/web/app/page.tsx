import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { buttonClasses } from "@/components/ui/Button";
import { CardSection } from "@/components/ui/Card";

/**
 * The home page of the public site.
 *
 * Why this file exists: the demo has three ways to be seen and a visitor has to be able to tell them
 * apart before anything happens. The recorded demo reads the published artifacts and calls nobody,
 * the sandbox forks a published case into a branch of the visitor, and the live mode asks the backend
 * of the demo and asks for the key of the visitor. All three are offered here, each one with the
 * mode it runs in written down, because a recorded run is never labelled live and a live run is
 * never labelled recorded (ADR-040, ADR-044).
 *
 * Why the catalog of a real model is a link and not a fourth card: the site publishes two catalogs of
 * the recorded scenarios, and the second one is a second way to read the same nine cases, not a fourth
 * mode of the demo. The card of the recorded demo therefore names it, so that a visitor who arrives at
 * the door of the site finds both catalogs without having to know that the second one exists (ADR-075).
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

      <section className="grid gap-4 lg:grid-cols-3" aria-label="The three ways to see the demo">
        <CardSection
          title="Recorded demo"
          description="The published artifacts of a capture, played in the browser."
          titleLevel="h2"
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
            <div className="flex flex-wrap items-center gap-2">
              <Link className={buttonClasses("primary", "md")} href="/replay">
                Open the recorded demo
              </Link>
              {/*
                The site publishes two catalogs of the recorded scenarios, the recordings of the scripted model and
                the recordings of a real model, and each one has its own route (ADR-075). The link names the second
                one here, so that a visitor who arrives at the door of the site finds the catalog of a real run
                without having to know that it exists.
              */}
              <Link className={buttonClasses("secondary", "md")} href="/replay-real">
                Open the catalog of a real model
              </Link>
            </div>
          </div>
        </CardSection>

        <CardSection
          title="Sandbox"
          description="A published case, forked into a branch of your own session."
          titleLevel="h2"
        >
          <div className="flex flex-col gap-3">
            <Badge tone="neutral">mode: visitor_sandbox</Badge>
            <p className="text-sm text-text-muted">
              The sandbox forks a published case into a branch of your own session and lets you build a typed
              mutation on it, read what the mutation would do and commit it. It asks no provider and it spends no
              money of your own.
            </p>
            <p className="text-sm text-text-subtle">
              The branch lives on the origin of the backend, in your own session, and the state of the branch stays
              in the memory of the page: it never travels in the address of the browser.
            </p>
            <div>
              <Link className={buttonClasses("secondary", "md")} href="/sandbox">
                Open the sandbox
              </Link>
            </div>
          </div>
        </CardSection>

        <CardSection
          title="Live mode"
          description="Your own key, your own run, on the backend."
          titleLevel="h2"
        >
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
