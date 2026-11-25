"""The durable operations and the forensic traces: a run that restarts without losing evidence or doing work twice.

Why the package exists: the branch of a visitor is already durable (the idempotent commit, the atomic write, the
pure projection), and a run of the agent was not: it wrote nothing durable, died with its steps half done and
could not be resumed. The package is the second half: the journal of a run, the restart of a run that died, the
unknown status of a call whose answer never arrived, the barrier of a cancellation and the forensic export of a
run.

Why the journal is in the domain: the journal of a run is a fact of the domain, like the branch of a visitor,
and the domain never imports the API layer and never writes SQL of its own.
"""
