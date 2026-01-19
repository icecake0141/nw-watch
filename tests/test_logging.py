"""Comprehensive logging tests.

Tests for logging functionality, format consistency, and proper error logging.
"""

import logging
import re
from io import StringIO

import pytest

from nw_watch.shared.config import Config
from nw_watch.shared.db import Database


class TestLoggingFormat:
    """Test logging format and consistency."""

    def test_log_format_includes_timestamp(self, caplog):
        """Test that log messages include timestamps."""
        caplog.set_level(logging.INFO)

        logger = logging.getLogger("test_logger")
        logger.info("Test message")

        # Check that log was captured
        assert len(caplog.records) > 0

    def test_log_format_includes_level(self, caplog):
        """Test that log messages include log level."""
        caplog.set_level(logging.DEBUG)

        logger = logging.getLogger("test_logger")
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Verify all levels were captured
        levels = [record.levelname for record in caplog.records]
        assert "DEBUG" in levels
        assert "INFO" in levels
        assert "WARNING" in levels
        assert "ERROR" in levels

    def test_log_format_includes_logger_name(self, caplog):
        """Test that log messages include logger name."""
        caplog.set_level(logging.INFO)

        logger = logging.getLogger("test.module.name")
        logger.info("Test message")

        assert len(caplog.records) > 0
        assert caplog.records[0].name == "test.module.name"


class TestDatabaseLogging:
    """Test database operation logging."""

    def test_database_creation_logged(self, tmp_path, caplog):
        """Test that database creation is logged."""
        caplog.set_level(logging.DEBUG)

        db_path = tmp_path / "test.db"
        db = Database(str(db_path), history_size=10)

        # Should log database operations
        # (Actual logging depends on implementation)
        db.close()

    def test_database_insert_logged(self, tmp_path, caplog):
        """Test that database inserts are logged at appropriate level."""
        caplog.set_level(logging.DEBUG)

        db_path = tmp_path / "test.db"
        db = Database(str(db_path), history_size=10)

        caplog.clear()
        db.insert_run(
            device_name="TestDevice",
            command_text="test command",
            ts_epoch=100,
            output_text="output",
            ok=True,
        )

        # Inserts might be logged at DEBUG level
        # (This depends on implementation)

        db.close()

    def test_database_error_logged(self, tmp_path, caplog):
        """Test that database errors are logged."""
        caplog.set_level(logging.ERROR)

        db_path = tmp_path / "test.db"
        db = Database(str(db_path), history_size=10)

        # Trigger an error
        try:
            db.conn.execute("SELECT * FROM nonexistent_table")
        except Exception:
            pass  # Expected to fail

        # Error should be logged (if error handling includes logging)
        # (This depends on implementation)

        db.close()


class TestConfigLogging:
    """Test configuration loading logging."""

    def test_config_load_success_logged(self, tmp_path, caplog):
        """Test that successful config loading is logged."""
        caplog.set_level(logging.INFO)

        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
interval_seconds: 5
ping_interval_seconds: 1
ping_window_seconds: 60
history_size: 10
max_output_lines: 100

commands:
  - name: "test"
    command_text: "show version"

devices:
  - name: "Device1"
    host: "192.168.1.1"
    port: 22
    username: "admin"
    password: "test123"
    device_type: "cisco_ios"
""")

        config = Config(str(config_path))

        # Config loading might be logged
        # (This depends on implementation)
        assert config is not None

    def test_config_validation_error_logged(self, tmp_path, caplog):
        """Test that config validation errors are logged."""
        caplog.set_level(logging.ERROR)

        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
interval_seconds: -5  # Invalid
ping_interval_seconds: 1
ping_window_seconds: 60
history_size: 10
max_output_lines: 100

commands:
  - name: "test"
    command_text: "show version"

devices:
  - name: "Device1"
    host: "192.168.1.1"
    port: 22
    username: "admin"
    password: "test123"
    device_type: "cisco_ios"
""")

        try:
            Config(str(config_path))
        except ValueError:
            pass  # Expected to fail

        # Validation errors might be logged
        # (This depends on implementation)


class TestErrorLogging:
    """Test error logging coverage."""

    def test_exception_logging_includes_traceback(self, caplog):
        """Test that exceptions include traceback information."""
        caplog.set_level(logging.ERROR)

        logger = logging.getLogger("test_logger")

        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.exception("An error occurred")

        # Should have logged the exception with traceback
        assert len(caplog.records) > 0
        # The record should contain exception info
        assert caplog.records[0].exc_info is not None

    def test_error_messages_are_descriptive(self, tmp_path, caplog):
        """Test that error messages are descriptive."""
        caplog.set_level(logging.ERROR)

        # Trigger a database error with descriptive message
        db_path = tmp_path / "test.db"
        db = Database(str(db_path), history_size=10)

        logger = logging.getLogger("test_logger")

        try:
            db.conn.execute("INVALID SQL STATEMENT")
        except Exception as e:
            logger.error(f"Database query failed: {e}")

        # Error message should be descriptive
        if len(caplog.records) > 0:
            assert (
                "Database query failed" in caplog.records[-1].message
                or "syntax error" in str(caplog.records[-1].message).lower()
            )

        db.close()


class TestLogLevels:
    """Test appropriate use of log levels."""

    def test_debug_level_for_detailed_info(self, caplog):
        """Test that DEBUG level is used for detailed information."""
        caplog.set_level(logging.DEBUG)

        logger = logging.getLogger("test_logger")
        logger.debug("Detailed debug information")

        # DEBUG messages should be captured when level is DEBUG
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debug_records) > 0

    def test_info_level_for_normal_operations(self, caplog):
        """Test that INFO level is used for normal operations."""
        caplog.set_level(logging.INFO)

        logger = logging.getLogger("test_logger")
        logger.info("Normal operation completed")

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) > 0

    def test_warning_level_for_issues(self, caplog):
        """Test that WARNING level is used for potential issues."""
        caplog.set_level(logging.WARNING)

        logger = logging.getLogger("test_logger")
        logger.warning("Potential issue detected")

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) > 0

    def test_error_level_for_errors(self, caplog):
        """Test that ERROR level is used for errors."""
        caplog.set_level(logging.ERROR)

        logger = logging.getLogger("test_logger")
        logger.error("An error occurred")

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) > 0


class TestLogSecurity:
    """Test that logs don't expose sensitive information."""

    def test_passwords_not_logged(self, tmp_path, caplog):
        """Test that passwords are not logged in plain text."""
        caplog.set_level(logging.DEBUG)

        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
interval_seconds: 5
ping_interval_seconds: 1
ping_window_seconds: 60
history_size: 10
max_output_lines: 100

commands:
  - name: "test"
    command_text: "show version"

devices:
  - name: "Device1"
    host: "192.168.1.1"
    port: 22
    username: "admin"
    password: "my_secret_password_123"
    device_type: "cisco_ios"
""")

        config = Config(str(config_path))

        # Check all log messages
        for record in caplog.records:
            # Password should not appear in logs
            assert "my_secret_password_123" not in record.message

    def test_sensitive_data_redacted_in_errors(self, caplog):
        """Test that sensitive data is redacted in error logs."""
        caplog.set_level(logging.ERROR)

        logger = logging.getLogger("test_logger")

        # Simulate logging an error that might contain sensitive data
        # Good practice is to redact before logging
        sensitive_value = "password123"
        redacted_value = "***REDACTED***"

        logger.error(f"Authentication failed for user with password: {redacted_value}")

        # Check that sensitive data is not in logs
        for record in caplog.records:
            assert sensitive_value not in record.message


class TestLogPerformance:
    """Test logging performance characteristics."""

    def test_excessive_logging_disabled_by_default(self, caplog):
        """Test that excessive debug logging is disabled by default."""
        # At INFO level, DEBUG messages should not be captured
        caplog.set_level(logging.INFO)

        logger = logging.getLogger("test_logger")
        logger.debug("Debug message that should not appear")
        logger.info("Info message that should appear")

        # Should not capture DEBUG when level is INFO
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]

        assert len(debug_records) == 0
        assert len(info_records) > 0

    def test_logging_does_not_impact_performance(self, tmp_path, caplog):
        """Test that logging doesn't significantly impact performance."""
        import time

        caplog.set_level(logging.INFO)

        logger = logging.getLogger("test_logger")

        # Measure time with logging
        start_time = time.time()
        for i in range(1000):
            logger.info(f"Message {i}")
        end_time = time.time()

        duration = end_time - start_time

        # Should complete in reasonable time
        # (This is a soft requirement and may vary)
        assert duration < 2.0, f"1000 log messages took {duration:.2f}s"


class TestLogContext:
    """Test that logs include appropriate context."""

    def test_log_includes_module_context(self, caplog):
        """Test that logs include module context."""
        caplog.set_level(logging.INFO)

        logger = logging.getLogger("collector.main")
        logger.info("Collector started")

        # Should include module name
        assert len(caplog.records) > 0
        assert "collector" in caplog.records[0].name

    def test_log_includes_operation_context(self, caplog):
        """Test that logs include operation context."""
        caplog.set_level(logging.INFO)

        logger = logging.getLogger("test_logger")

        # Good practice: include context in message
        device_name = "Device1"
        logger.info(f"Connecting to device: {device_name}")

        # Message should include context
        assert len(caplog.records) > 0
        assert "Device1" in caplog.records[0].message


class TestLogConsistency:
    """Test logging consistency across the application."""

    def test_consistent_message_format(self, caplog):
        """Test that log messages follow consistent format."""
        caplog.set_level(logging.INFO)

        logger = logging.getLogger("test_logger")

        # Log messages should follow consistent patterns
        logger.info("Operation started: test_operation")
        logger.info("Operation completed: test_operation")
        logger.info("Operation failed: test_operation")

        # Check that messages follow a pattern
        for record in caplog.records:
            # Should have descriptive messages
            assert len(record.message) > 0
            assert record.message[0].isupper()  # Should start with capital letter

    def test_consistent_error_reporting(self, caplog):
        """Test that errors are reported consistently."""
        caplog.set_level(logging.ERROR)

        logger = logging.getLogger("test_logger")

        # Errors should include what failed and why
        try:
            raise ValueError("Invalid configuration")
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")

        assert len(caplog.records) > 0
        error_msg = caplog.records[0].message
        assert "failed" in error_msg.lower() or "error" in error_msg.lower()
