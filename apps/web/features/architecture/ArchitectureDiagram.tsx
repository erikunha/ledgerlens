/**
 * The picture of the architecture of the recorded demo and the accessible list that is its twin.
 *
 * Why this file exists: the tour of the architecture asks for a picture that a visitor can click
 * and for a list that a reader of a screen reader can read, and the two have to carry the same
 * six subsystems in the same order. Two copies of the content would drift, and a copy of the
 * content of a node in a second file is the drift that ADR-046 refused.
 *
 * Why the picture is an inline SVG with fixed coordinates: the six subsystems are a chain, and a
 * chain is six boxes and five arrows. The picture measures nothing, it reads no clock, it draws
 * no random number, it has no transition and no animation, and it adds no dependency to the
 * frontend, so it is legible as a static picture in every case and the preference for reduced
 * motion has nothing to switch off in it.
 *
 * Why the picture is a pure function of the array of the nodes: the nodes carry the words of the
 * page and the coordinates are written here, once. A picture that measured the text would depend
 * on a font that the visitor may not have, and a picture that animated would be a picture that a
 * reader cannot read while it moves.
 *
 * Why the list is rendered from the same array and by the same component: the list is the twin of
 * the picture and not a second copy of it, it is always present in the page, and it is never
 * behind a toggle. A visitor who cannot see the picture reads the six subsystems in the list, and
 * a visitor who can see the picture reads the same six in the same order.
 *
 * Why every node of the picture is an anchor of the SVG with an href: an anchor with an href is in
 * the tab order, so the nodes of the picture are reachable with the keyboard, and every node links
 * to its module and to at least one record, which is what FR-029 asks for.
 *
 * Why the chosen node is not told apart by a colour: a tint of the background is invisible in the
 * forced colours mode of the system and hard to see with low vision, so the chosen node carries a
 * heavier name, a thicker border and a word that says it is the chosen one.
 *
 * Why this module holds no state and no effect: the chosen node is the state of the page that
 * shows the tour, and the page hands it down as a prop. The picture is a function of the array and
 * of the props, so it needs no client boundary and the page ships the least code it can.
 */

import type { ReactElement } from "react";

import { ArchitectureNodeCard } from "@/features/architecture/ArchitectureNodeCard";
import { ARCHITECTURE_NODES, type ArchitectureNode } from "@/features/architecture/nodes";
import { recordUrlOf, sourceUrlOf } from "@/lib/repository";

/**
 * The geometry of the picture.
 *
 * Why the boxes are drawn one under the other: the chain of the run has to be legible on a
 * screen of three hundred and ninety pixels, and a horizontal chain of six boxes would shrink
 * the name of every subsystem to nothing. The viewBox carries the coordinates and the width of
 * the picture is a hundred percent of the column, so the picture never forces a scroll sideways.
 */
const BOX_X = 20;
const BOX_WIDTH = 400;
const BOX_HEIGHT = 96;
const BOX_TOP = 24;
const BOX_STEP = 158;
const VIEWBOX_WIDTH = 440;
const VIEWBOX_HEIGHT = 940;

/** The height of the band of the box that opens the module of the node. */
const MODULE_BAND = 58;

/**
 * The props of the picture and of the list.
 *
 * Why the commit is a prop and not a constant of the module: the commit is read at build time and
 * it belongs to the build, and a link that pins a commit written by hand is a constant that a
 * release has to remember to update (ADR-046).
 */
export interface ArchitectureDiagramProps {
  /** The commit of the checkout the links open. */
  readonly commit: string;
  /** The nodes of the picture. */
  readonly nodes?: readonly ArchitectureNode[];
  /** The identifier of the node the visitor chose, when one is chosen. */
  readonly selectedNodeId?: string | null;
}

/**
 * The props of the accessible list.
 *
 * Why the list takes the same props as the picture: the two are twins, and a twin that takes
 * another array is a copy that can drift.
 */
export interface ArchitectureNodeListProps {
  /** The commit of the checkout the links open. */
  readonly commit: string;
  /** The nodes of the list. */
  readonly nodes?: readonly ArchitectureNode[];
  /** The identifier of the node the visitor chose, when one is chosen. */
  readonly selectedNodeId?: string | null;
}

/**
 * The picture of the chain of the subsystems.
 *
 * Why the picture is drawn here and not in a file of its own: the picture and the list are
 * rendered from the same array, and a picture that lived in another file would be a second place
 * where the content of a node could be written.
 */
function ArchitecturePicture({
  nodes,
  commit,
  selectedNodeId,
}: {
  readonly nodes: readonly ArchitectureNode[];
  readonly commit: string;
  readonly selectedNodeId: string | null;
}): ReactElement {
  return (
    /*
     * The picture carries no attribute of height: "auto" is not a length that a browser accepts, and
     * the attribute made every visit of the page log an error in the console of the browser. The
     * viewBox and the class of the picture draw the picture, and the browser needs no height.
     */
    <svg
      aria-label="The picture of the architecture of the recorded demo"
      className="h-auto w-full max-w-lg text-foreground"
      data-architecture-picture="true"
      preserveAspectRatio="xMidYMid meet"
      role="group"
      viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
      width="100%"
    >
      {nodes.map((node, index) => {
        const top = BOX_TOP + index * BOX_STEP;
        const isChosen = node.id === selectedNodeId;
        const record = node.records[0];

        return (
          <g key={node.id} data-architecture-node={node.id}>
            {/* the box of the node: the border is the mark of the chosen node, and a thicker
                border survives the forced colours mode of the system, where a tint does not */}
            <rect
              fill="none"
              height={BOX_HEIGHT}
              rx={10}
              ry={10}
              stroke="currentColor"
              strokeOpacity={isChosen ? 1 : 0.45}
              strokeWidth={isChosen ? 3 : 1.5}
              width={BOX_WIDTH}
              x={BOX_X}
              y={top}
            />

            {/* the first anchor of the node opens the module it is written in, and the name of the
                subsystem is the visible text of the anchor, so a reader that cannot see the
                picture still reads the name

                Why the anchor carries a tabindex: an anchor of an SVG is not in the order of the
                keyboard in every engine of the suite. WebKit only puts it there when the anchor
                says that it takes the focus, and a node that a keyboard visitor cannot reach in
                one engine is a node the picture does not have (ADR-046). */}
            <a
              aria-current={isChosen ? "true" : undefined}
              data-architecture-link="module"
              href={sourceUrlOf(node.module, commit)}
              tabIndex={0}
              title={node.summary}
            >
              <rect fill="transparent" height={MODULE_BAND} width={BOX_WIDTH} x={BOX_X} y={top} />
              <text
                fill="currentColor"
                fontSize={21}
                fontWeight={isChosen ? 700 : 600}
                x={BOX_X + 20}
                y={top + 40}
              >
                {node.label}
              </text>
            </a>

            {/* the second anchor of the node opens the number of the record that explains why the
                module exists. The nodes always carry a record, and the test of the nodes refuses
                one that does not, so the guard here is the shape of the data and not a branch of
                the page. */}
            {record ? (
              <a
                data-architecture-link="record"
                href={recordUrlOf(record.path, commit)}
                tabIndex={0}
                title={`${record.number} ${record.title}`}
              >
                <rect
                  fill="transparent"
                  height={BOX_HEIGHT - MODULE_BAND}
                  width={BOX_WIDTH}
                  x={BOX_X}
                  y={top + MODULE_BAND}
                />
                <text fill="currentColor" fontSize={15} x={BOX_X + 20} y={top + 74}>
                  {record.number}
                </text>
              </a>
            ) : null}

            {/* the mark of the chosen node is a word and not a colour */}
            {isChosen ? (
              <text
                fill="currentColor"
                fontSize={15}
                textAnchor="end"
                x={BOX_X + BOX_WIDTH - 16}
                y={top + 40}
              >
                The chosen node
              </text>
            ) : null}

            {/* the arrow of the chain: the run goes from one subsystem to the next one */}
            {index < nodes.length - 1 ? (
              <g data-architecture-arrow="true">
                <line
                  stroke="currentColor"
                  strokeWidth={2}
                  x1={VIEWBOX_WIDTH / 2}
                  x2={VIEWBOX_WIDTH / 2}
                  y1={top + BOX_HEIGHT + 10}
                  y2={top + BOX_STEP - 10}
                />
                <path
                  d={`M ${VIEWBOX_WIDTH / 2 - 10} ${top + BOX_STEP - 20} L ${VIEWBOX_WIDTH / 2} ${
                    top + BOX_STEP - 10
                  } L ${VIEWBOX_WIDTH / 2 + 10} ${top + BOX_STEP - 20}`}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                />
              </g>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}

/**
 * The accessible list of the subsystems.
 *
 * The list is the twin of the picture: it carries the same six subsystems, in the same order,
 * each one a heading, a sentence and the links to the module and to the records. It is always in
 * the page and it is never behind a toggle.
 */
export function ArchitectureNodeList({
  commit,
  nodes = ARCHITECTURE_NODES,
  selectedNodeId = null,
}: ArchitectureNodeListProps): ReactElement {
  return (
    <section
      aria-label="The subsystems of the architecture"
      data-architecture-list="true"
      className="flex flex-col gap-4"
    >
      {nodes.map((node) => (
        <ArchitectureNodeCard
          key={node.id}
          commit={commit}
          node={node}
          selected={node.id === selectedNodeId}
          titleLevel="h3"
        />
      ))}
    </section>
  );
}

/**
 * The picture of the architecture and the accessible list that is its twin.
 *
 * The page that shows the tour renders this component and nothing else: the picture and the list
 * are drawn together, because a list that is not in the page is a list that a reader of a screen
 * reader never reaches.
 */
export function ArchitectureDiagram({
  commit,
  nodes = ARCHITECTURE_NODES,
  selectedNodeId = null,
}: ArchitectureDiagramProps): ReactElement {
  return (
    <section
      aria-label="The architecture of the recorded demo"
      className="flex flex-col gap-8"
      data-architecture-diagram="true"
    >
      <ArchitecturePicture commit={commit} nodes={nodes} selectedNodeId={selectedNodeId} />
      <ArchitectureNodeList commit={commit} nodes={nodes} selectedNodeId={selectedNodeId} />
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the diagram at once. */
export const __all__ = [
  "ArchitectureDiagramProps",
  "ArchitectureDiagram",
  "ArchitectureNodeListProps",
  "ArchitectureNodeList",
] as const;
