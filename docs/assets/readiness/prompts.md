# The illustrations of the readiness page and the language they share

The eight images of [`docs/readiness-2027.md`](../../readiness-2027.md) are conceptual illustrations of what each
audited component does in this system. They are not screenshots and they are not decoration: they are a second
reading of the eight sections, in a visual register that a reader who sees two of them can recognise.

Every image was generated from one shared style block, written once and repeated byte for byte in the eight prompts.
The images were then reduced to a shared palette with `pngquant` so that the eight files carry the same colour
treatment, and each file was kept under 600 kilobytes.

## The visual language

One paragraph, and it is the same in all eight prompts:

> Flat vector technical illustration in one consistent editorial infographic style. Warm off-white paper background.
> Ink navy line work at a single uniform medium stroke weight, rounded caps and joins. No gradients, no shadows, no
> texture, no 3D perspective, no photorealism, no painterly rendering. Strictly limited palette: ink navy for
> structure and outlines, one muted amber for the element the eye must land on, one muted teal for supporting
> components, one muted brick red reserved for risk, refusal or fault. Constant shape vocabulary: rounded rectangles
> for stores and artifacts, small filled circles for discrete events and steps, thin straight or gently curved
> connectors between them, dotted connectors for paths that do not exist yet. Orthographic straight-on view, calm
> and uncluttered, generous empty space, 3:2 landscape composition. Absolutely no text, no letters, no digits, no
> words, no captions, no labels, no watermark, no logo, no signature, no written user interface.

Three rules carry the identity of the set:

1. **One palette, one line weight.** Ink navy for structure, amber for the subject of the image, teal for what
   supports it, brick red only for what is wrong, refused or missing. The same four colours, in the same proportion,
   in all eight.
2. **One vocabulary of shapes.** Rounded rectangles are stores and artifacts. Small filled circles are discrete
   events and steps. Dotted connectors are paths that do not exist yet. Solid connectors are paths that do.
3. **No words.** Not one image carries text, a digit, a label or a watermark. The typography of this repository is
   its own, and an image model renders letters badly enough to be worth avoiding.

## The prompts

### 01-agent-runtime.png

> Subject: the agent runtime. At the centre an amber hexagonal hub, the agent. Six thin navy connectors radiate from
> the hub to six teal rounded rectangles arranged in a wide arc around it, the tools, each holding only a few small
> abstract geometric marks, never a letter or a digit. A dotted navy circle loops around the hub and back into it,
> an unbounded turn. Where that dotted circle would close, a solid amber arc segment stops it short, a ceiling.
> Beneath the whole arrangement a wide navy rounded rectangle spans the width, the deterministic verifier, receiving
> a downward arrow from the hub, and from it three thin arrows descend to three small circles in a row, one teal,
> one amber, one brick red, the three verdicts. One brick red circle sits apart from the others, connected by a
> dotted line, human review.

### 02-retrieval.png

> Subject: the retrieval. On the left a stack of pale teal sheets of paper, slightly fanned, the corpus. In the
> centre a hexagonal lattice of many small navy dots inside a large circle, the vector index, with exactly one dot
> filled amber, the hit. From the upper left a thin arrow carrying a small amber card enters the lattice, the query.
> From the lower right three pale sheets emerge from the lattice, the retrieved excerpts. Between the corpus and the
> index a thin navy bridge holds a small amber balance scale, the freshness comparison, and beside it a small teal
> circular seal. From the index a dotted connector runs down to a small empty outlined circle where a check would
> belong, not built yet.

### 03-verification.png

> Subject: the verification. On the left a large amber sheet, the claim, with a rectangular window cut out of its
> middle. To the right four teal sheets of evidence angled toward the window, with pale fragment shapes that fit
> exactly into the opening, shown sliding into it. Over the filled window sits a large navy lens in profile,
> focusing one thin beam downward. Below, that beam splits into three thin branches that end in three small circles
> in a row, one teal, one amber, one brick red, the three verdicts. A brick red circle sits apart from the row,
> joined by a dotted line, the case that goes to a person.

### 04-evaluation-integrity.png

> Subject: the integrity of the evaluation. Two identical stacks of small pale cards stand side by side, separated
> by a tall solid navy vertical wall running through the middle of the frame. Above the left stack a teal circular
> arrow loops back into the stack, the tuning loop. Thin teal connectors run from that left stack into a small amber
> box, the tuned system, and out of it again, so the system and the data it was tuned on touch each other. The right
> stack stands inside a thin navy outlined vault, untouched, with no arrow leaving it and no arrow entering it, and
> the amber box does not reach it. A dotted line crosses the wall and stops short of the vault, the connection that
> is not made yet.

### 05-safety.png

> Subject: the safety posture. On the left a stream of pale teal data cards flows rightward into a hexagonal
> gateway. One card in the stream is brick red and carries a jagged thorn shape growing out of it, the poisoned
> text. Below, a layered defence drawn as three concentric navy shield outlines around a teal sandbox box. The red
> card stops at the outer shield and a short brick red arrow turns back away from it. Inside the sandbox box a small
> amber circle works over a small teal slab. A dotted outline surrounds the whole defence, a perimeter that is not
> yet closed.

### 06-observability.png

> Subject: the observability and the provenance. Across the middle of the frame a horizontal sequence of nine small
> navy circles, discrete events, joined by a thin line running left to right that ends in an amber rounded
> rectangle, the answer. From each event circle a fine vertical thread drops to a wide teal slab below, the record,
> each thread ending in a small dot where it lands. One position in the sequence is drawn as a dotted empty circle
> with a dotted thread, the event that is missing. At the right edge a large navy lens in profile looks back along
> the line, the way a reader would.

### 07-operations.png

> Subject: the operations and the economics. On the left three horizontal meters stacked one above the other on a
> common navy axis with fine tick marks: the first filled amber to about two thirds, the second filled teal to about
> half, the third filled brick red only at its very beginning. Each meter ends in a small teal disc. On the right
> four parallel conveyor lanes run left to right, each a thin line with a small amber token travelling along it at a
> different point, the concurrency, and one lane ends in a small brick red octagon, a failure. Below the lanes a
> single pale amber disc sits alone.

### 08-public-surface.png

> Subject: the public surface. On the right a large flat browser window drawn in ink navy outline with a row of
> small circles in its top bar and nothing written in it. Inside it, a wide amber banner across the top, then a grid
> of six teal cards, then one large navy rounded rectangle lower down, the reading surface. On the left a tall stack
> of pale paper pages, slightly fanned, with thin teal rules on the top page, the written document. A thin navy
> connector runs from that stack into the browser window, the link between them. Above the browser window a small
> amber arrow points outward into open space, the invitation to the reader.

## How they were produced

The images were generated with the image model of the connected Matrix provider, through
`mcode-tools connector call connector__matrix__generate_image`, one request per image, all eight in a single batch,
at `aspect_ratio 3:2`, `area 1K`, `output_format png`. The receipt was 8 of 8 succeeded and 0 failed.

The delivered files are 1248 by 832 pixels, PNG, palette mode, after `pngquant --quality=88-100 --speed 1 --strip`.
The reduction is what keeps every file under 600 kilobytes, and applying it to all eight is what makes the palette
identical across the set.
