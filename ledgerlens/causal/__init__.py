"""The causal counterfactual interventions: the registry of the structural functions of the synthetic world.

Why the package exists: the repository can change one field of a branch and read the difference between two
states, but it cannot say what caused the difference. The package declares the dependencies of the synthetic
world in a registry, and the engine recomputes the descendants of an intervention along the edges of the
registry.

Why nothing of the registry is learned from an observation: a dependency that is learned from an observation is
a dependency that the data suggests and not a dependency that the code implements. The registry is written by
hand over the code of the repository, and a node that is not in the registry is never a descendant of anything.
A change without a declared edge is reported as `unknown` with the missing edge named, because a tool that says
"because" when it cannot is worse than a tool that says nothing.
"""
