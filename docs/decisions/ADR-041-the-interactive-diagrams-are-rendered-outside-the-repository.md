---
type: adr
status: accepted
date: 2026-11-21
---

# ADR-041: The interactive diagrams are rendered outside the repository

Status: accepted. Date: 2026-11-21.

## Context

The convention of the repository is that a flow, a sequence or a relation is drawn in Mermaid whenever it is clearer
drawn (`AGENTS.md`, the section about the documentation). The architecture of the live mode is a relation of eight
components across two origins, with a trust boundary and a secret that travels in exactly one place, and Mermaid draws
it well enough for a reader of the Markdown.

The reader of a published document, on the other hand, wants to follow the connections one by one, to see the regions
of trust and to read the legend of the diagram without scrolling a page of Markdown. The tool **Archify**, version
3.2.0, renders an architecture diagram from a typed JSON source into a self contained HTML file with an interactive
viewer. It is a Node program with no dependencies and it runs offline.

The rendered file cannot be committed to this repository. The rendered HTML of the tool weighs about 820 KB (846989
bytes in the version of the tool that produced the diagram of the live mode) and carries **31 em dashes and 3 en
dashes** inside the CSS and the JavaScript of its own viewer template. The rule of the repository forbids the em dash
and the en dash in any text of the repository (`AGENTS.md`, the section about the language), and the dashes of the
template are exactly that kind of text. A file that breaks the rule of the repository cannot live in the repository.

The source of the diagram has none of these problems. It is a small JSON file, its text is plain, and the dashes of the
template never enter it.

## Decision

**The typed JSON source of an interactive diagram IS committed, and the rendered HTML IS NOT.**

**The convention of the repository does not change.** The Markdown keeps its Mermaid diagram, and the JSON carries the
typed source of the deeper interactive version of the same picture. The two are two views of one diagram, and the
Mermaid one is the one that the reader of the repository reads without any tool.

**The rendered file lives OUTSIDE the repository**, in the folder of the artefacts of the local machine, and it is never
committed. A reader who wants the interactive version runs the command that is written below and gets the file.

**The tool is not a dependency of the repository.** It is a local clone, and the repository gains no script that
depends on it, no Node dependency and no Python dependency. The commands of the ADR name the tool by its path on the
machine that has it.

## The interface of the milestone

The file `docs/diagrams/live-mode.architecture.json` holds the typed source of the architecture of the live mode. Its
shape is the schema of the tool:

| key | what it holds |
| --- | --- |
| `schema_version` | the number `1` |
| `diagram_type` | the string `architecture` |
| `meta` | the title, the output name and the quality profile |
| `components` | the eight components of the picture, with the type, the label, the position and the size |
| `boundaries` | the four regions of the picture: the origin of the site, the origin of the API, the memory of the server and the file of the run |
| `connections` | the eight relationships, with the labels that say what travels |
| `cards` | the three panels of the legend |

The commands are these two, and they are the whole of the interface:

```bash
node <the tool of the owner, outside the repository> validate architecture docs/diagrams/live-mode.architecture.json --quality showcase --json
node <the tool of the owner, outside the repository> deliver architecture docs/diagrams/live-mode.architecture.json <the folder of the artefacts, outside the repository>/live-mode.architecture.html --quality showcase --json
```

The first command proves that the source is well formed and that the picture has no crossed connection, no label over a
component and no label over another relationship. It must answer `ok: true` before the second command runs.

The second command renders the file and writes it in the folder of the artefacts, outside the repository. The folder is
created when it does not exist.

The `validate` command of the source of the live mode answers with the sha256 of the source
`393e4fa6208c6f97d773f90709b6965ad714640422fa65ac5f7bcd762e75c90d`, and the `deliver` command answers with the sha256
of the artifact `50116902ac926e319e7a195950b50bb2bdb7e72d1266509bbb42e6f443eed18a`. The second hash changes when the
version of the tool changes, and that is the expected behaviour: the artifact is not a file of the repository and it is
not pinned by anything.

The Markdown that shows the diagram is `docs/frontend.md`, and the Mermaid block of it is the version that the
repository commits.

## What this milestone does not have

- No rendered HTML in the repository, and no generated file of any kind in the repository.
- No change to the convention of the Mermaid: the Markdown keeps its Mermaid diagram.
- No dependency on the tool: no Node dependency, no Python dependency, no script of the repository that calls it.
- No job of the continuous integration that renders the diagram, and no check of the gate that validates it.
- No fork of the tool and no patch of its template: the dashes of the template are the reason the artifact stays
  outside, and a local patch would have to be redone on every release of the tool.
- No change to the text of the diagram: the labels of the JSON obey the same rule as the rest of the repository.

## The alternatives considered

- **(a) Commit the rendered HTML and accept the dashes of the template.** It breaks the rule of the language of the
  repository, it puts 820 KB of generated code in the history of a public repository, and every update of the tool
  would produce a large diff that says nothing about the work.
- **(b) Commit the rendered HTML after patching the template of the tool to remove the dashes.** The patch would be a
  fork of the tool, it would be lost on the next release of the tool, and the reviewer of the repository would have to
  trust a template that is not the template of the tool anymore.
- **(c) Keep only the Mermaid diagram and drop the interactive version.** The repository stays exactly as it is, and the
  reader loses the regions of trust and the legend. The Mermaid diagram answers the question of the flow, and it does
  not answer the question of the boundary of the key as well.
- **(d) Commit the rendered HTML in a branch of the artefacts.** The artefacts of the work are local by the decision of
  the repository, and a branch of a public repository is not a local artefact.

## Consequences

The rule about the dashes stays absolute, and the diagrams of the repository stay reviewable in a diff, because what a
diff of the source shows is the content of the diagram and not the result of a template.

The reader of the Markdown sees the Mermaid diagram, which is the convention of the repository and the promise of the
documentation. The reader who wants the interactive version runs one command, writes the file outside the repository
and opens it.

The cost of the decision is that the interactive version is not served with the repository, and that the reader who
wants it needs the tool. The tool is a local clone of a version that is written down here, and the source of the
diagram is enough to render it with any tool that reads the same schema.
