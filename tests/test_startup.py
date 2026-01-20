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
"""Tests for application startup functionality."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


class TestModuleImport:
    """Test that modules can be imported successfully."""

    def test_collector_main_can_be_imported(self):
        """Test that nw_watch.collector.main can be imported."""
        try:
            import nw_watch.collector.main
            assert hasattr(nw_watch.collector.main, 'main')
            assert hasattr(nw_watch.collector.main, 'Collector')
        except ModuleNotFoundError as e:
            pytest.fail(f"Failed to import nw_watch.collector.main: {e}")

    def test_webapp_main_can_be_imported(self):
        """Test that nw_watch.webapp.main can be imported."""
        try:
            import nw_watch.webapp.main
            assert hasattr(nw_watch.webapp.main, 'app')
        except ModuleNotFoundError as e:
            pytest.fail(f"Failed to import nw_watch.webapp.main: {e}")

    def test_all_submodules_can_be_imported(self):
        """Test that all main submodules can be imported."""
        modules = [
            'nw_watch',
            'nw_watch.collector',
            'nw_watch.collector.main',
            'nw_watch.webapp',
            'nw_watch.webapp.main',
            'nw_watch.shared',
            'nw_watch.shared.config',
            'nw_watch.shared.db',
            'nw_watch.shared.diff',
            'nw_watch.shared.export',
            'nw_watch.shared.filters',
        ]
        
        for module_name in modules:
            try:
                __import__(module_name)
            except ModuleNotFoundError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")


class TestModuleExecution:
    """Test that modules can be executed as __main__."""

    def test_collector_main_can_run_with_help(self):
        """Test that collector main can be run with --help flag."""
        result = subprocess.run(
            [sys.executable, "-m", "nw_watch.collector.main", "--help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        assert result.returncode == 0, f"Collector --help failed: {result.stderr}"
        assert "usage:" in result.stdout.lower(), "Help message should contain usage"
        assert "--config" in result.stdout, "Help should mention --config option"

    def test_collector_main_requires_config(self):
        """Test that collector main requires --config argument."""
        result = subprocess.run(
            [sys.executable, "-m", "nw_watch.collector.main"],
            capture_output=True,
            text=True,
            timeout=5
        )
        assert result.returncode != 0, "Should fail without --config"
        assert "required" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_collector_main_fails_with_missing_config_file(self):
        """Test that collector main fails gracefully with non-existent config."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            nonexistent_config = Path(tmp_dir) / "nonexistent.yaml"
            result = subprocess.run(
                [sys.executable, "-m", "nw_watch.collector.main", "--config", str(nonexistent_config)],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode != 0, "Should fail with non-existent config file"

    def test_webapp_main_can_be_run(self):
        """Test that webapp main module can be executed."""
        # Just verify that the module can be loaded - don't actually start the server
        result = subprocess.run(
            [sys.executable, "-c", "import nw_watch.webapp.main; print('OK')"],
            capture_output=True,
            text=True,
            timeout=5
        )
        assert result.returncode == 0, f"Failed to load webapp.main: {result.stderr}"
        assert "OK" in result.stdout


class TestPackageStructure:
    """Test that package structure is correct."""

    def test_package_has_init_files(self):
        """Test that all package directories have __init__.py files."""
        import nw_watch
        package_root = Path(nw_watch.__file__).parent
        
        # Check main package init
        assert (package_root / "__init__.py").exists(), "nw_watch/__init__.py should exist"
        
        # Check subpackages
        subpackages = ['collector', 'webapp', 'shared']
        for subpkg in subpackages:
            init_file = package_root / subpkg / "__init__.py"
            assert init_file.exists(), f"nw_watch/{subpkg}/__init__.py should exist"

    def test_package_installed_correctly(self):
        """Test that the package is installed and discoverable."""
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "nw-watch"],
            capture_output=True,
            text=True,
            timeout=5
        )
        assert result.returncode == 0, "Package nw-watch should be installed"
        assert "nw-watch" in result.stdout.lower()


class TestStartupWithValidConfig:
    """Test startup with a valid minimal configuration."""

    def test_collector_starts_with_valid_config(self):
        """Test that collector can start with a valid config (and exit quickly)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "test_config.yaml"
            config_path.write_text("""
interval_seconds: 5
ping_interval_seconds: 1
history_size: 10
max_output_lines: 500

commands:
  - name: "test_cmd"
    command_text: "show version"

devices:
  - name: "TestDevice"
    host: "192.168.1.1"
    username: "admin"
    password_env_key: "TEST_PASSWORD"
    device_type: "cisco_ios"
""")
            
            # Set environment variable
            env = os.environ.copy()
            env["TEST_PASSWORD"] = "test"
            
            # Start collector with timeout - it should initialize without errors
            # We'll kill it after a second since we're just testing startup
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "nw_watch.collector.main", "--config", str(config_path)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    env=env,
                    cwd=tmp_dir
                )
                # If it completed, check for errors
                if result.returncode != 0:
                    stderr_lower = result.stderr.lower()
                    assert "modulenotfounderror" not in stderr_lower, f"Module import failed: {result.stderr}"
                    assert "no module named" not in stderr_lower, f"Module import failed: {result.stderr}"
            except subprocess.TimeoutExpired as e:
                # This is expected - the collector runs indefinitely
                # Check that startup messages were logged (no import errors)
                stderr = e.stderr.decode() if e.stderr else ""
                stderr_lower = stderr.lower()
                assert "modulenotfounderror" not in stderr_lower, f"Module import failed: {stderr}"
                assert "no module named" not in stderr_lower, f"Module import failed: {stderr}"
                # Verify that it actually started successfully
                assert "created session database" in stderr_lower or "created devicecollector" in stderr_lower, \
                    f"Collector didn't start properly: {stderr}"
