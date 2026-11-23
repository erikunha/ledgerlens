---
type: adr
status: accepted
date: 2026-11-23
---

# ADR-060: The surfaces that answer a person carry the sentence of the AI agent

Status: accepted. Date: 2026-11-23.

## Context

Article 50 of the EU AI Act has applied since 2 August 2026. A system that interacts directly with a natural
person has to inform that person, and the product of this repository answers people: the Help panel of the demo
application answers the complaint of a customer, the live mode of the public site runs an investigation with the
key of the visitor, and the recorded demo of the site plays the answer of an agent to whoever reads it.

Until this record, no surface of the product said anything about the origin of the answer. The audit of
compliance of the programme of readiness of 2027 found the gap and named it: the answer of a model reads like
the answer of a person, because it is written in the first person, in plain words, with the tone of somebody who
knows the case. The cost of the silence is not only the fine of the article. It is that a person who reads a
payment answer places a trust in a text that nobody wrote, and the product keeps that trust nowhere else.

Two facts of the repository made the decision less trivial than writing a line of text in two places.

The first is that the product has three stacks and not one: the domain is Python, the public site is TypeScript,
and the README has a Portuguese edition. A sentence written by hand in each surface is two or three sentences, and
two sentences drift, and the drift is invisible until a reader of the public site sees a promise the demo does
not keep.

The second is that the sentence has to be true. The product does what it says about the review of a case: the
verifier sends a case to a person when it cannot decide, and the escalation is a real path of the run. But the
product does not have a person reading every answer, and a sentence that says so would be a promise the product
does not keep, which is the failure this repository exists to avoid.

## Decision

### The words live in the domain, in one file

The sentence lives in `ledgerlens/prompts/ai_disclosure.json`, and the module `ledgerlens/prompts/ai_disclosure.py`
exposes it as `AI_DISCLOSURE`. The file of the words exists next to the module for one reason: the public site is
a TypeScript application and cannot import a module of Python, so the site reads the same JSON file that the
domain reads. There is exactly one place where the sentence is written, and both stacks read it.

### Every surface that answers a person carries the sentence

- The Help panel of the demo application (`app/streamlit_app.py`), as a caption under the question box, where the
  person reads it before the first answer.
- The live mode of the public site (`apps/web/app/(public)/live/page.tsx`), in the header of the page.
- The recorded demo of the public site (`apps/web/app/(public)/replay/scenario/[scenario]/page.tsx`), in the header
  of the page of a scenario, because the recording shows the answer of an agent to whoever reads it.

The rule of the record is the surface that answers a person. A surface that lists or edits cases does not answer,
and does not carry the sentence: the catalogue of the recorded demo and the sandbox of the visitor are out of
scope. This is stated here so that the rule is a rule and not a convenience, and so that a new surface that
answers has to be added to the list below.

### What the sentence says, and what it does not promise

The sentence says two things, and the test holds both of them: the answer is produced by an AI agent, and a person
reviews the cases that need review. The second half is the truth of the product: the agent recommends, the
verifier decides what it can decide, and the cases it cannot decide go to a person. The sentence does not say
that every answer is reviewed, because the product does not review every answer, and a disclosure that promises
more than the product keeps is a lie with a legal shape.

### The rule is held by tests, not by memory

`tests/test_ai_disclosure.py` holds four things: the module of the domain holds a sentence that is not empty and
that says the two things; the file of the words and the module hold the same sentence; the page of the demo is
rendered and carries the sentence; every page of the site that answers reads the file of the domain and not a
copy of its own. `apps/web/tests/unit/features/ai-disclosure.test.tsx` proves the other half, that the sentence
reaches the rendered page of the live mode and not only the source of the page.

A surface that answers and is not named by the test is a surface that forgot the obligation, and the test is what
catches it.

## Consequences

- A new surface that answers a person now has a cost: it has to carry the sentence and the test has to name it.
  The alternative was a surface that quietly forgets what the others keep.
- The demo application and the public site say the same words, because they read the same file. A change of the
  sentence changes both at once, and there is no second place to forget.
- The Portuguese README carries the sentence in Portuguese, because the README is a document read by a person and
  not a surface that answers; the domain keeps one sentence, in English, for the two stacks that answer.
- The obligation of Article 50 is bigger than this record. The sentence informs the person who interacts; the
  duties of keeping the record of the run and of the human oversight live with the trace of the run and with the
  escalation, and the programme of readiness of [ADR-058](ADR-058-the-programme-of-readiness-for-2027-and-what-it-does-not-do.md)
  carries them, not this record.

## Alternatives that were refused

- **Writing the sentence in each surface.** Refused: three stacks and three copies, and the drift is invisible.
- **Only in the README.** Refused: the README is read once, by a person deciding whether to trust the project,
  and the obligation is with the person who is being answered.
- **A policy page about the use of AI.** Refused for now: the obligation is to inform the person who interacts,
  and the interaction happens in the Help panel, not in a document the person may never open. A policy page may
  come later; it does not replace the sentence.
- **Saying that a human reviews every answer.** Refused: the product does not do that, and the sentence must not
  promise more than the product keeps.
- **Naming the model in the sentence.** Refused: the model of the default is deprecated and has a date
  ([ADR-057](ADR-057-the-model-has-a-clock-and-the-repository-pins-it.md)), and a sentence that names a model goes
  out of date. The sentence says what is true whatever the model is.

## The debt of this record

- The sentence is not localized. The site and the demo are English, and the obligation is read by people who may
  not read English. The Portuguese edition of the README carries the sentence in Portuguese; the surfaces do not
  carry a Portuguese sentence yet, and that is a debt, not a decision.
- The sentence says that a person reviews the cases that need review, and the product does not yet measure how
  often that person is in fact there. The escalation path exists and is tested; the staffing of it is a question
  of the operator of the product and not of this repository.

## Links

- [the module of the domain](../../ledgerlens/prompts/ai_disclosure.py) and [the file of the words](../../ledgerlens/prompts/ai_disclosure.json)
- [the test of the domain](../../tests/test_ai_disclosure.py) and [the test of the site](../../apps/web/tests/unit/features/ai-disclosure.test.tsx)
- [the programme of readiness for 2027](../readiness-2027.md)
- [the live mode of the demo](../../specs/003-r3-bring-your-own-key/spec.md)
