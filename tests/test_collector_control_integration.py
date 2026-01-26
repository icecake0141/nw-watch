# Copyright 2026 icecake0141
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# This file was created or modified with the assistance of an AI (Large Language Model).
# Review required for correctness, security, and licensing.
"""Integration tests for collector control via WEBGUI buttons."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import os


@pytest.fixture(autouse=True)
def control_dir(tmp_path, monkeypatch):
    """Provide an isolated control directory for tests."""
    control_path = tmp_path / "control"
    monkeypatch.setenv("NW_WATCH_CONTROL_DIR", str(control_path))
    return control_path


@pytest.fixture
def client():
    """Create test client."""
    from nw_watch.webapp.main import app

    return TestClient(app)


def test_pause_button_updates_control_state(client, control_dir):
    """Test that clicking Pause button updates control state file."""
    from nw_watch.shared.control_state import read_control_state, get_control_state_path

    # Initial state should be running
    response = client.get("/api/collector/status")
    assert response.status_code == 200
    data = response.json()
    assert data["commands_paused"] is False
    assert data["status"] == "running"

    # Click pause button (POST to pause endpoint)
    response = client.post("/api/collector/pause")
    assert response.status_code == 200
    data = response.json()
    assert data["commands_paused"] is True
    assert data["status"] == "paused"

    # Verify control state file was updated
    state = read_control_state()
    assert state["commands_paused"] is True
    assert state["shutdown_requested"] is False

    # Verify file exists
    control_file = get_control_state_path()
    assert control_file.exists()


def test_resume_button_updates_control_state(client, control_dir):
    """Test that clicking Resume button updates control state file."""
    from nw_watch.shared.control_state import read_control_state, update_control_state

    # Set initial paused state
    update_control_state({"commands_paused": True})

    # Click resume button
    response = client.post("/api/collector/resume")
    assert response.status_code == 200
    data = response.json()
    assert data["commands_paused"] is False
    assert data["status"] == "running"

    # Verify control state file was updated
    state = read_control_state()
    assert state["commands_paused"] is False
    assert state["shutdown_requested"] is False


def test_stop_button_updates_control_state(client, control_dir):
    """Test that clicking Stop button updates control state file."""
    from nw_watch.shared.control_state import read_control_state

    # Initial state should be running
    response = client.get("/api/collector/status")
    assert response.status_code == 200

    # Click stop button
    response = client.post("/api/collector/stop")
    assert response.status_code == 200
    data = response.json()
    assert data["commands_paused"] is True
    assert data["shutdown_requested"] is True
    assert data["status"] == "stopped"

    # Verify control state file was updated
    state = read_control_state()
    assert state["commands_paused"] is True
    assert state["shutdown_requested"] is True


def test_collector_would_respect_pause_state(control_dir):
    """Test that collector logic would respect pause state."""
    from nw_watch.shared.control_state import update_control_state, read_control_state

    # Simulate collector checking state while running
    state = update_control_state({"commands_paused": False})
    current = read_control_state()
    assert current["commands_paused"] is False
    # Collector would continue executing commands

    # Simulate webapp pausing via button
    state = update_control_state({"commands_paused": True})

    # Simulate collector checking state on next poll
    current = read_control_state()
    assert current["commands_paused"] is True
    # Collector would skip command execution and sleep


def test_collector_would_respect_stop_state(control_dir):
    """Test that collector logic would respect stop state."""
    from nw_watch.shared.control_state import update_control_state, read_control_state

    # Simulate webapp stopping via button
    state = update_control_state({"shutdown_requested": True, "commands_paused": True})

    # Simulate collector checking state
    current = read_control_state()
    assert current["shutdown_requested"] is True
    # Collector would exit its main loop


def test_button_workflow_end_to_end(client, control_dir):
    """Test complete workflow: run -> pause -> resume -> stop."""
    from nw_watch.shared.control_state import read_control_state

    # 1. Initial state: running
    response = client.get("/api/collector/status")
    assert response.json()["status"] == "running"

    # 2. Pause
    response = client.post("/api/collector/pause")
    assert response.json()["status"] == "paused"
    state = read_control_state()
    assert state["commands_paused"] is True

    # 3. Resume
    response = client.post("/api/collector/resume")
    assert response.json()["status"] == "running"
    state = read_control_state()
    assert state["commands_paused"] is False

    # 4. Stop
    response = client.post("/api/collector/stop")
    assert response.json()["status"] == "stopped"
    state = read_control_state()
    assert state["shutdown_requested"] is True

    # 5. Cannot pause when stopped
    response = client.post("/api/collector/pause")
    assert response.status_code == 409  # Conflict
