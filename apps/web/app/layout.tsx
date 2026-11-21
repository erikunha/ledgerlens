import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

/**
 * The root layout of the public site.
 *
 * Why this file exists: the site is a static export with no server runtime, so the shell of the
 * pages is written once here and every page inherits it. The layout owns the language of the
 * document, the skip link that lets a keyboard user jump to the content, the metadata that the
 * search engines and the browser tabs read, and the stylesheet of the design package.
 *
 * Why there is no web font: the design tokens ask for the stacks of the platform, and a font
 * file would make the build depend on a network call for a page that has to work offline.
 * `app/globals.css` declares the same stacks as custom properties.
 */

export const metadata: Metadata = {
  title: {
    default: "LedgerLens: evidence-first payment investigation",
    template: "%s | LedgerLens",
  },
  description:
    "LedgerLens investigates payment complaints and shows the evidence behind every answer: the ledger rows it read, the policy it applied and the arithmetic it did.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground">
        <a className="ll-skip-link" href="#main">
          Skip to the main content
        </a>
        <main id="main">{children}</main>
      </body>
    </html>
  );
}
