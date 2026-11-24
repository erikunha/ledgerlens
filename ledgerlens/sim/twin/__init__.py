"""The operations digital twin: the operations of a payment business over a modelled arrival process.

Why the package exists: the repository can generate a world of payments and project it deterministically, but
it cannot say how cases arrive, how many cases a team can carry at once, what a queue does when it never
drains, or what changes when a review policy changes. The twin adds exactly that, and nothing else.

Why the twin runs no model and touches no payment network: the twin is a research instrument, not a product.
Every number it publishes is a number about the synthetic world it simulated, and every figure carries the
assumptions that produced it. The arrival distribution is a model and is labelled as one everywhere it
appears, because the repository has no arrival data.
"""
