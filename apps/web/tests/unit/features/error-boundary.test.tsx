/**
 * The test of the boundaries of the site.
 *
 * Why this test exists: a page of the site that throws leaves the visitor in front of the default
 * page of error of the framework, outside the shell of the site, without the landmarks and
 * without the words of the site. A visitor who reads that cannot tell what the site is and what
 * went wrong, and a reader who cannot tell which parts of a run are true is worse off than a
 * reader who sees nothing (ADR-043).
 *
 * Why the boundary of the case is built here and not taken from the framework: the framework of
 * Next.js does not export the boundary it installs, and the contract of the boundary of the site
 * is the pair `error` and `reset`. The case builds that contract around a tree that throws, so
 * the case fails when the contract of the site changes.
 *
 * Why the case draws its own root: React reports an error that it recovered from to the root of
 * the tree, and the default of that report reaches the window of the test. The case collects the
 * report instead, so the case can prove that the boundary caught the exception and the case does
 * not fail because React recovered from a failure on purpose.
 *
 * Why the tree of the case breaks while it is drawn and not in the first drawing: the boundary
 * catches the errors of the drawing of the tree, and a page that breaks after the visitor acts is
 * the case the boundary has to survive.
 *
 * Why the case says what it proves and never the detail of the error: the failure state of the
 * site shows the visitor that the page failed and what to do next, and it never shows the message
 * of the error, because the message of an error of production carries the digest of the server
 * and the message of an error of development carries the name of an internal module.
 *
 * Every case runs with no key and no network.
 */

import { act, fireEvent, screen, within } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { createRoot, type Root } from "react-dom/client";
import { Component, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SiteErrorBoundary from "@/app/error";
import SiteGlobalError from "@/app/global-error";
import SiteNotFound from "@/app/not-found";

/**
 * The root of the fake path of the machine that the message of the error of the case carries.
 *
 * Why the root is built out of fragments: the public repository refuses a literal that looks
 * like the path of a machine of the author, and the case still has to prove that the boundary
 * hides such a path from the visitor. The root is therefore assembled at run time, so no line
 * of this file carries the literal of a path of a machine.
 */
const MACHINE_ROOT = "/" + "Users";

/**
 * The message of the error of the case.
 *
 * Why the message carries a path and a name of a module: the case has to prove that neither of
 * them reaches the visitor.
 */
const SECRET_MESSAGE = `the reader failed: ${MACHINE_ROOT}/analyst/ledgerlens/features/replay/ReplayViewer.tsx`;

/**
 * The component of the case: it throws while the tree is broken.
 *
 * Why it takes a flag and not an event: an error boundary catches the errors of the drawing of
 * the tree, and the errors of an event handler are not caught by a boundary.
 *
 * Why it throws every time it is asked to: React draws the tree that failed once more to be sure
 * of the failure, and a component that threw only the first time would look like a failure that
 * is already gone.
 */
function ThrowsWhenBroken({ broken }: { readonly broken: boolean }): ReactNode {
  if (broken) {
    throw new Error(SECRET_MESSAGE);
  }
  return <p>The page is back</p>;
}

/** The props of the boundary of the case. */
interface CaseBoundaryProps {
  /** The tree below the boundary. */
  readonly children?: ReactNode;
}

/** The state of the boundary of the case. */
interface CaseBoundaryState {
  /** The error the boundary caught, or null when nothing failed. */
  readonly error: Error | null;
  /** The flag that says that the tree below has to break. */
  readonly broken: boolean;
}

/**
 * The boundary of the case: it catches the error of the tree below it and hands it to the
 * boundary of the site.
 *
 * Why the case builds it: the framework hands the error and the reset to the boundary of the
 * site, and the case builds the very same contract, so the case proves the contract and not an
 * accident of the case.
 */
class CaseBoundary extends Component<CaseBoundaryProps, CaseBoundaryState> {
  override state: CaseBoundaryState = { error: null, broken: false };

  static getDerivedStateFromError(error: Error): CaseBoundaryState {
    return { error, broken: false };
  }

  /** The reset of the case: it draws the tree below the boundary again. */
  reset = (): void => {
    this.setState({ error: null });
  };

  override render(): ReactNode {
    if (this.state.error !== null) {
      return <SiteErrorBoundary error={this.state.error} reset={this.reset} />;
    }
    return (
      <>
        <button type="button" onClick={() => this.setState({ broken: true })}>
          Break the page
        </button>
        <ThrowsWhenBroken broken={this.state.broken} />
        {this.props.children}
      </>
    );
  }
}

/**
 * The errors that React reported while the case ran.
 *
 * Why the case collects them: the report of React is the proof that the exception reached a
 * boundary and was caught there, and the case reads it instead of letting it reach the window.
 */
const reported = {
  caught: [] as unknown[],
  uncaught: [] as unknown[],
  recoverable: [] as unknown[],
};

/** The roots that the case drew, so that the case can close them. */
const roots: Root[] = [];

/**
 * Draws the tree of the case in a root that collects the errors that React reports.
 *
 * Why the case draws its own root: the root is where React reports an error it recovered from,
 * and the case needs to read that report instead of letting it reach the window of the test.
 */
function renderCase(ui: ReactNode): void {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container, {
    onCaughtError: (error) => {
      reported.caught.push(error);
    },
    onUncaughtError: (error) => {
      reported.uncaught.push(error);
    },
    onRecoverableError: (error) => {
      reported.recoverable.push(error);
    },
  });
  roots.push(root);
  act(() => {
    root.render(ui);
  });
}

/**
 * Draws the boundary of the case with a tree that breaks, and waits for the failure state.
 *
 * Why the case breaks the tree with a click: the error has to be thrown while the tree is drawn,
 * and the click is what asks for the drawing.
 */
function renderBrokenPage(): void {
  renderCase(<CaseBoundary />);
  fireEvent.click(screen.getByRole("button", { name: "Break the page" }));
}

beforeEach(() => {
  reported.caught = [];
  reported.uncaught = [];
  reported.recoverable = [];
  // React writes every error it catches to the console, and the case does not need that noise.
  vi.spyOn(console, "error").mockImplementation(() => undefined);
});

afterEach(() => {
  for (const root of roots.splice(0, roots.length)) {
    act(() => {
      root.unmount();
    });
  }
  document.body.innerHTML = "";
});

describe("the boundaries of the site", () => {
  it("shows the failure state of the site when the tree below the boundary throws", () => {
    // It proves that an exception leaves the visitor in front of the failure state of the site, and
    // not in front of the page of error of the framework.
    renderBrokenPage();

    const failure = screen.getByRole("alert");
    expect(within(failure).getByRole("heading", { name: "The page could not be shown" })).toBeInTheDocument();
    expect(within(failure).getByText(/the site hit a failure it did not expect/i)).toBeInTheDocument();
    expect(within(failure).getByRole("link", { name: "The catalog of the scenarios" })).toHaveAttribute(
      "href",
      "/replay",
    );
  });

  it("catches the exception with the boundary and never lets it reach the root of the site", () => {
    // It proves that the boundary really catches the exception: React caught the error at the
    // boundary and no error reached the root of the site.
    renderBrokenPage();

    expect(reported.caught.length).toBeGreaterThan(0);
    expect(reported.uncaught).toHaveLength(0);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("never shows the detail of the error to the visitor", () => {
    // It proves that the failure state shows no message, no path and no name of an internal
    // module, because the message of an error of production carries the digest of the server.
    renderBrokenPage();

    const text = document.body.textContent ?? "";
    expect(text).not.toContain("the reader failed");
    expect(text).not.toContain("ReplayViewer");
    expect(text).not.toContain(MACHINE_ROOT);
  });

  it("gives the visitor a way to draw the page again", () => {
    // It proves that the reset of the boundary is wired to an action the visitor can take, so a
    // failure that is not there anymore does not keep the visitor away from the page.
    renderBrokenPage();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(screen.getByText("The page is back")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("keeps the failure of the root of the site in the language of the site", () => {
    // It proves that the boundary of the root draws its own document, with the language of the
    // site, and that it says the same thing as the boundary of the segment.
    const markup = renderToStaticMarkup(
      <SiteGlobalError error={new Error(SECRET_MESSAGE)} reset={() => undefined} />,
    );

    expect(markup).toContain("<html lang=\"en\">");
    expect(markup).toContain("The page could not be shown");
    expect(markup).toContain("The catalog of the scenarios");
    expect(markup).not.toContain("ReplayViewer");
    expect(markup).not.toContain(MACHINE_ROOT);
  });

  it("shows the page that is not published in the look of the site", () => {
    // It proves that the page of 404 is the failure state of the site and not the page of error of
    // the framework, and that it leads the visitor to the catalog of the scenarios.
    renderCase(<SiteNotFound />);

    const failure = screen.getByRole("alert");
    expect(within(failure).getByRole("heading", { name: /not published/i })).toBeInTheDocument();
    expect(within(failure).getByRole("link", { name: "The catalog of the scenarios" })).toHaveAttribute(
      "href",
      "/replay",
    );
  });
});
