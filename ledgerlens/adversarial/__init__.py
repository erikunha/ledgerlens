"""The safe adversarial laboratory: the boundaries of the repository, measured with canned exercises.

Why the package exists: the repository already holds the boundaries (the guard of the SQL, the allowlist of the
tools, the scope of the session, the budget of the run, the verifier), and the laboratory measures them with a
list of canned exercises whose payloads are synthetic. The laboratory adds no defense of its own: a laboratory
that filtered the attacks itself would measure its own filter, and the boundaries of the product would stay
unmeasured.

Why the exercises are data and not text of a visitor: a request of the laboratory accepts an exercise id of the
list and nothing else, so no text of a visitor ever reaches a prompt of a provider.
"""
