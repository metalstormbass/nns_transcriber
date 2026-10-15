# deep-audit

Installs the full dependency tree from `requirements.txt` into a clean
virtualenv and runs `pip-audit` against it in strict mode.

Run it on PRs that change `requirements.txt` or anything that affects the
dependency set, by adding the `ci/run:deep-audit` label to the PR.

It is on-request rather than automatic because the PySide6 wheel download
is large and the audit result only changes when dependencies change.
