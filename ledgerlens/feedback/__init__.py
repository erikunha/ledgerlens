"""The verified feedback loop: a published failure becomes a reviewed regression.

Why the package exists: the repository publishes two catalogs of recorded scenarios, and the catalogs hold the
failures and not only the cases the agent resolves. The loop of this package turns a published failure into a
feedback record, gates the record with the deterministic verdict of the verifier of the repository, tiers the
record, and builds a training set from the records of the tier gold.

Why no output of a model enters a training set without the deterministic verdict as its gate: a loop without
the gate would be a machine that trains a model on the agreement of another model, and the number it produced
would measure nothing. The verdict of a record is the verdict of `ledgerlens/verify/checks.py` over the
published evidence of the bundle, computed offline, with no model and no network, and the verdict of a model
never fills that field and never promotes a record.
"""
