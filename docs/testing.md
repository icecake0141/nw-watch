<!--
Copyright 2026 icecake0141
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
-->
# Testing

Japanese: [testing.ja.md](testing.ja.md)

## Scope

The repository includes tests for:

- Configuration validation and defaults
- Collector behavior (command execution, ping, scheduling, control state)
- Database persistence and history retention
- Web API endpoints and exports
- WebSocket behavior
- Security-related checks (input validation and headers)

Main test directory: [`tests/`](../tests)

## Local Validation Commands

Install dependencies:

```bash
pip install -e ".[dev]"
```

Format check:

```bash
black --check --diff .
```

Lint:

```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics --exclude=.git,__pycache__,data,tests
```

Type check:

```bash
mypy --install-types --non-interactive --ignore-missing-imports src/nw_watch
```

Tests:

```bash
pytest -v --tb=short --cov=nw_watch --cov-report=xml --cov-report=term
```

## CI Reference

CI workflow file: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

The pipeline runs lint and tests on Python 3.12 for PRs, and 3.11/3.12 for pushes to `main` and `develop`.
