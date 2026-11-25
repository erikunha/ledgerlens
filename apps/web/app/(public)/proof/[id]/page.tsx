/**
 * The page of one proof of work of the repository.
 *
 * Why this file exists: an artifact of the proof of work is a place of the site, and a place has an address.
 * The route is `/proof/<id>`, with the identifier of the artifact in the path, and the identifier of the
 * artifact is the digest of the bundle it was built from, so the address of the artifact is unguessable by
 * construction and no private artifact exists.
 *
 * Why the route is a server component: the site is a static export, and a static export of a dynamic route
 * needs the list of the parameters at build time. The page reads the catalog of the proofs from the disk
 * while the export is built, and an identifier that the catalog does not publish is the page of 404, never a
 * guess at run time.
 *
 * What the page shows: the provenance of the artifact (the commit, the digests, the catalog and the capture
 * kind), the claim, the evidence, the verdicts of the deterministic verifier, the recipe that reproduces the
 * run, the links of the commit the artifact names, the transcript, and the limitations. The badge of the
 * verified status is shown only when the status is verified, and a draft names what is missing.
 */

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Badge } from "@/components/ui/Badge";
import { readProofCatalog } from "@/lib/proof/catalog";

/**
 * The list of the artifacts the export holds a page for.
 *
 * Why the list is read from the disk: the export writes one HTML file per published artifact, so the build
 * has to know the identifiers before it writes them.
 */
export function generateStaticParams(): Array<{ id: string }> {
  return readProofCatalog(process.cwd()).map((artifact) => ({ id: artifact.artifact_id }));
}

/**
 * Why no artifact is invented at run time.
 *
 * The export holds one page per published artifact, and an identifier that the catalog does not publish is
 * the page of 404. A route that guessed would show a proof that was never built.
 */
export const dynamicParams = false;

/** The props of the route of an artifact. */
interface ProofPageProps {
  /** The identifier of the artifact, as it is in the path. */
  readonly params: Promise<{ id: string }>;
}

/**
 * The metadata of the route of an artifact.
 *
 * Why the route carries a title and a description of its own: an artifact is a place of the site, and every
 * place has a name that the browser, the search engine and the tab of the reader show.
 */
export async function generateMetadata({ params }: ProofPageProps): Promise<Metadata> {
  const { id } = await params;
  const artifact = readProofCatalog(process.cwd()).find((entry) => entry.artifact_id === id);
  if (!artifact) {
    return { title: "Proof of work" };
  }
  return {
    title: `Proof of ${artifact.scenario_id} (${artifact.catalog})`,
    description: artifact.claim,
  };
}

/**
 * The page of the artifact.
 *
 * The page reads the catalog from the disk and finds the artifact of the path. An identifier that the catalog
 * does not publish is the page of 404.
 */
export default async function ProofPage({ params }: ProofPageProps) {
  const { id } = await params;
  const artifact = readProofCatalog(process.cwd()).find((entry) => entry.artifact_id === id);
  if (!artifact) {
    notFound();
  }

  return (
    <div className="mx-auto flex w-full max-w-content flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={artifact.status === "verified" ? "success" : "warning"}>{artifact.status}</Badge>
          <Badge>{artifact.catalog}</Badge>
          <Badge>{artifact.capture_kind}</Badge>
        </div>
        <h1 className="text-3xl font-semibold">Proof of {artifact.scenario_id}</h1>
        <p className="max-w-2xl text-text-muted">{artifact.claim}</p>
        {artifact.status !== "verified" && artifact.missing.length > 0 ? (
          <p className="text-sm text-text-subtle">
            This artifact is a draft, and the evidence that is missing is: {artifact.missing.join("; ")}.
          </p>
        ) : null}
      </header>

      <section aria-labelledby="proof-provenance" className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold" id="proof-provenance">
          The provenance
        </h2>
        <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-text-subtle">The commit of the run</dt>
            <dd className="font-mono">{artifact.git_commit}</dd>
          </div>
          <div>
            <dt className="text-text-subtle">The identifier of the artifact</dt>
            <dd className="font-mono break-all">{artifact.artifact_id}</dd>
          </div>
          <div>
            <dt className="text-text-subtle">The catalog</dt>
            <dd>{artifact.catalog}</dd>
          </div>
          <div>
            <dt className="text-text-subtle">The capture kind</dt>
            <dd>{artifact.capture_kind}</dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="proof-verdicts" className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold" id="proof-verdicts">
          The verdicts of the deterministic verifier
        </h2>
        <p className="text-sm text-text-muted">{artifact.verdict_summary}</p>
        <p className="text-sm text-text-subtle">
          The evidence of the claims: {artifact.evidence_refs.join(", ")}.
        </p>
      </section>

      <section aria-labelledby="proof-numbers" className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold" id="proof-numbers">
          The numbers, from the reports of the repository
        </h2>
        <ul className="flex flex-col gap-1 text-sm">
          {artifact.numbers.map((number) => (
            <li key={number.name}>
              <span className="font-semibold">{number.name}</span>: {number.value}, from{" "}
              <span className="font-mono">{number.report_path}</span> (digest{" "}
              <span className="font-mono break-all">{number.report_digest}</span>)
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="proof-recipe" className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold" id="proof-recipe">
          The recipe that reproduces the run
        </h2>
        <pre
          className="overflow-x-auto rounded-lg border border-border p-4 text-sm"
          // the recipe scrolls sideways on a narrow screen, so it is a stop of the keyboard: a region
          // that scrolls and that cannot be reached is a region a keyboard visitor cannot read
          tabIndex={0}
          role="region"
          aria-label="The recipe that reproduces the run"
        >
          <code>{artifact.recipe}</code>
        </pre>
      </section>

      <section aria-labelledby="proof-links" className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold" id="proof-links">
          The links of the commit
        </h2>
        <ul className="flex flex-col gap-1 text-sm">
          {artifact.links.map((link) => (
            <li className="font-mono" key={link}>
              {link}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="proof-transcript" className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold" id="proof-transcript">
          The transcript
        </h2>
        <p className="text-sm text-text-muted">{artifact.transcript}</p>
        {artifact.media_dropped ? (
          <p className="text-sm text-text-subtle">
            The media of this artifact is over the budget of the site, and the transcript is the artifact.
          </p>
        ) : null}
      </section>

      <section aria-labelledby="proof-limitations" className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold" id="proof-limitations">
          The known limitations
        </h2>
        <ul className="flex list-disc flex-col gap-1 pl-6 text-sm text-text-muted">
          {artifact.known_limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </section>

      <p className="text-sm text-text-subtle">
        <Link className="underline" href="/proof">
          Back to the catalog of the proofs
        </Link>
      </p>
    </div>
  );
}
