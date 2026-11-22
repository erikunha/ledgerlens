"use client";

/**
 * The drawer of the engineering tour, and the tour that opens it.
 *
 * Why this file exists: the tour of the architecture shows a picture of the subsystems, and a
 * picture on its own leaves the visitor with a picture and nothing to read. The drawer is where
 * the tour says, in words, what the subsystems do and where the module of each one and the
 * record that explains why it exists live in the repository (ADR-046).
 *
 * Why the drawer is built on the primitive of the design system: the sheet is a dialog of Radix,
 * so the drawer carries `role="dialog"` and `aria-modal="true"`, the focus is trapped while it
 * is open, the Escape key closes it and the focus goes back to the control that opened it. A
 * drawer written by hand would be that dialog again, and it would be that dialog worse.
 *
 * Why the drawer never writes a description of its own: every sentence it shows about a
 * subsystem is the summary of a node of the array of the nodes, and every link it shows is built
 * by the same builder that the picture uses, so the drawer cannot drift away from the code it
 * describes. The only sentences of the drawer that are not summaries are the ones that say what
 * the drawer is about, because a drawer that names nothing is a drawer that says nothing.
 *
 * Why the context is optional: the page of the tour opens the drawer with the node the visitor
 * chose, and the replay opens it without one, because the drawer of a call of the recording is a
 * different thing and it waits for T048. A drawer that pretended to be about a call it does not
 * name would be a drawer that lies, so the drawer says in words that it is not tied to one call.
 *
 * Why the tour lives in this file and not in a file of its own: the route of the tour is a server
 * component, because the commit of the checkout is read while the site is built, and a server
 * component cannot hold the state of the visit. The tour is the client part of the page: it holds
 * the node the visitor chose in the memory of the browser, it draws the picture with that node
 * marked and it mounts the drawer that explains it. The state never goes into the path of the
 * page, because the path is what a visitor can share and the choice of a node is not (ADR-046).
 */

import { useRef, useState } from "react";
import type { ReactElement, RefObject } from "react";

import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { AdrLink } from "@/features/architecture/AdrLink";
import { ArchitectureDiagram } from "@/features/architecture/ArchitectureDiagram";
import { ArchitectureNodeCard } from "@/features/architecture/ArchitectureNodeCard";
import { ARCHITECTURE_NODES, type ArchitectureNode } from "@/features/architecture/nodes";
import { SourceLink } from "@/features/architecture/SourceLink";

/**
 * The props of the drawer of the engineering tour.
 *
 * Why the drawer is controlled by its caller: the page of the tour and the replay open the same
 * drawer from two different places, and each of them owns the state of the visit in its own
 * memory. A drawer that owned the state would force the two callers to share a state they do not
 * share (ADR-046).
 */
export interface EngineeringDrawerProps {
  /** Whether the drawer is open. */
  readonly open: boolean;
  /** The function that is called with the state the visitor asked for. */
  readonly onOpenChange: (open: boolean) => void;
  /** The commit of the tree that the links of the drawer open. */
  readonly commit: string;
  /** The node the drawer was opened with, when it was opened with one. */
  readonly context?: ArchitectureNode | null;
  /**
   * The control that opened the drawer, so that the focus goes back to it when the drawer closes.
   *
   * Why the drawer needs it: the drawer is controlled and it is opened by a control that lives
   * outside of it, so the primitive of the dialog does not know which control opened it and the
   * focus lands on the body of the page when the drawer closes. The rule of the repository is that
   * the focus returns to the control that opened the drawer (ADR-046).
   */
  readonly returnFocusTo?: RefObject<HTMLElement | null>;
}

/**
 * The props of the tour of the architecture.
 *
 * Why the tour takes the commit and not the links: the commit is read once at build time and it
 * belongs to the build, and the builder of the URLs lives in the library of the repository, so a
 * link of the picture, a link of the card and a link of the drawer cannot be spelled two ways.
 */
export interface EngineeringTourProps {
  /** The commit of the checkout the links open. */
  readonly commit: string;
  /** The nodes of the tour. */
  readonly nodes?: readonly ArchitectureNode[];
}

/**
 * The name of the drawer.
 *
 * Why the name is the same for the two callers: the drawer is the same drawer, and a visitor
 * that opens it from the page of the tour and a visitor that opens it from the replay read the
 * same thing.
 */
const DRAWER_TITLE = "The engineering behind the recorded demo";

/**
 * The three subsystems that the drawer explains.
 *
 * Why these three: the user story 5 of the plan names the guard, the arithmetic and the
 * verification, and ADR-046 says that the three subsystems the drawer explains are the first,
 * the third and the fifth of the array. The array is the order of the run, so the three are the
 * guard that only reads, the arithmetic of the money and the step that verifies the answer.
 *
 * Why the nodes are picked by their place and not by their identifier: the place is what the
 * decision names, and a node without a place is a node the array does not carry.
 */
const EXPLAINED_NODES: readonly ArchitectureNode[] = [
  ARCHITECTURE_NODES[0],
  ARCHITECTURE_NODES[2],
  ARCHITECTURE_NODES[4],
].filter((node): node is ArchitectureNode => node !== undefined);

/**
 * The first sentence of the drawer, when it was opened with a node.
 *
 * Why the sentence names the node: the drawer says what it is about in its first sentence, so a
 * visitor that opened it from the page of the tour knows at once which subsystem he is reading
 * about, and a visitor that opened it from the replay knows that the drawer is not about a call.
 */
function openingSentence(context: ArchitectureNode | null | undefined): string {
  if (context === null || context === undefined) {
    return "This drawer is not tied to one call of the recording.";
  }
  return `This drawer is about the ${context.label}.`;
}

/**
 * The drawer of the engineering tour.
 *
 * The drawer shows the context it was opened with and the three subsystems that the plan of the
 * release names. Every sentence about a subsystem comes from the array of the nodes and every
 * link is built by the builder of the links of the picture.
 */
export function EngineeringDrawer(props: EngineeringDrawerProps): ReactElement {
  const { open, onOpenChange, commit, context, returnFocusTo } = props;

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      returnFocusTo={returnFocusTo}
      title={DRAWER_TITLE}
      side="right"
    >
      <p className="text-sm text-foreground">{openingSentence(context)}</p>

      {context === null || context === undefined ? null : (
        <p className="text-sm text-text-muted">{context.summary}</p>
      )}

      <ul className="flex flex-col gap-4">
        {EXPLAINED_NODES.map((node) => (
          <li key={node.id} className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold text-foreground">{node.label}</h3>
            <p className="text-sm text-text-muted">{node.summary}</p>

            <p className="text-sm">
              <SourceLink path={node.module} commit={commit} />
            </p>

            <ul className="flex flex-col gap-1">
              {node.records.map((record) => (
                <li key={`${record.number}-${record.path}`} className="text-sm">
                  <AdrLink record={record} commit={commit} />
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </Sheet>
  );
}

/**
 * The tour of the architecture: the picture with its list, the nodes that open the drawer and the
 * drawer itself.
 *
 * The tour holds the node the visitor chose in the memory of the browser and nowhere else. The
 * chosen node is marked in the picture with a mark that is not a tint, and the card of the node
 * says in words that it is the chosen one, so the state of the visit survives the forced colours
 * mode of the system.
 */
export function EngineeringTour({ commit, nodes = ARCHITECTURE_NODES }: EngineeringTourProps): ReactElement {
  const [chosenNodeId, setChosenNodeId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  // The control that opened the drawer, so that the focus goes back to it when the drawer closes.
  // The control is the one that was pressed and not the last one that was drawn, because there is
  // one control per node and the focus has to go back to the control of the node the drawer is
  // about.
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const chosenNode = nodes.find((node) => node.id === chosenNodeId) ?? null;

  /**
   * Chooses a node and opens the drawer about it.
   *
   * Why the node is chosen before the drawer opens: the drawer names the node it was opened with
   * in its first sentence, and a drawer that opened without a name would have to be corrected
   * after the fact.
   *
   * Why the control that was pressed is remembered: the focus goes back to it when the drawer
   * closes, and there is one control per node.
   */
  function openDrawerFor(node: ArchitectureNode, trigger: HTMLButtonElement): void {
    triggerRef.current = trigger;
    setChosenNodeId(node.id);
    setDrawerOpen(true);
  }

  return (
    <>
      <section aria-labelledby="engineering-picture" className="flex flex-col gap-4">
        <h2 id="engineering-picture" className="text-lg font-semibold">
          The picture of the subsystems
        </h2>
        <p className="max-w-2xl text-sm text-text-muted">
          The subsystems of the recorded demo, in the order of the run. The list under the picture
          carries the same subsystems in the same order, so a visitor who cannot see the picture
          reads the same words.
        </p>
        <ArchitectureDiagram commit={commit} nodes={nodes} selectedNodeId={chosenNodeId} />
      </section>

      <section aria-labelledby="engineering-nodes" className="flex flex-col gap-4">
        <h2 id="engineering-nodes" className="text-lg font-semibold">
          The subsystems and their code
        </h2>
        <p className="max-w-2xl text-sm text-text-muted">
          Every subsystem opens the engineering drawer, which explains the guard, the arithmetic and
          the verification, and links to the module of each one and to the record that explains why
          it exists.
        </p>

        <ul className="flex flex-col gap-6">
          {nodes.map((node) => (
            <li key={node.id} className="flex flex-col gap-2">
              <ArchitectureNodeCard
                node={node}
                commit={commit}
                titleLevel="h3"
                selected={node.id === chosenNodeId}
              />
              <div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={(event) => openDrawerFor(node, event.currentTarget)}
                >
                  Open the engineering drawer for the {node.label}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <EngineeringDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        commit={commit}
        context={chosenNode}
        returnFocusTo={triggerRef}
      />
    </>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the drawer at once. */
export const __all__ = [
  "EngineeringDrawerProps",
  "EngineeringDrawer",
  "EngineeringTourProps",
  "EngineeringTour",
] as const;
