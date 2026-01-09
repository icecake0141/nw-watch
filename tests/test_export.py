"""Tests for export utilities."""
import json
from shared.export import (
    export_run_as_text,
    export_run_as_json,
    export_bulk_runs_as_json,
    export_ping_data_as_csv,
    export_ping_data_as_json,
    export_diff_as_html,
    export_diff_as_text,
    format_timestamp_jst,
    sanitize_filename_component,
)


def test_format_timestamp_jst():
    """Test JST timestamp formatting."""
    # 2024-01-01 00:00:00 UTC = 2024-01-01 09:00:00 JST
    epoch = 1704067200
    result = format_timestamp_jst(epoch)
    assert "2024-01-01" in result
    assert "JST" in result


def test_sanitize_filename_component_basic():
    """Test basic filename sanitization."""
    # Normal text with spaces should be converted to underscores
    assert sanitize_filename_component("show version") == "show_version"
    assert sanitize_filename_component("ping 192.168.1.1") == "ping_192.168.1.1"


def test_sanitize_filename_component_path_traversal():
    """Test that path traversal attempts are blocked."""
    # Path traversal sequences should be removed
    assert sanitize_filename_component("../../etc/passwd") == "etcpasswd"
    assert sanitize_filename_component("../../../evil") == "evil"
    assert sanitize_filename_component("...") == "unnamed"  # Returns "unnamed" when empty
    assert sanitize_filename_component("....") == "unnamed"  # Returns "unnamed" when empty
    
    # Directory separators should be removed
    assert sanitize_filename_component("etc/passwd") == "etcpasswd"
    assert sanitize_filename_component("windows\\system32") == "windowssystem32"
    assert sanitize_filename_component("/etc/passwd") == "etcpasswd"
    assert sanitize_filename_component("\\etc\\passwd") == "etcpasswd"


def test_sanitize_filename_component_shell_metacharacters():
    """Test that shell metacharacters are removed."""
    # Shell metacharacters should be stripped
    assert sanitize_filename_component("command | grep test") == "command_grep_test"
    assert sanitize_filename_component("cmd && evil") == "cmd_evil"
    assert sanitize_filename_component("test;rm -rf") == "testrm_-rf"
    assert sanitize_filename_component("$(evil)") == "evil"
    assert sanitize_filename_component("`whoami`") == "whoami"
    assert sanitize_filename_component("test<file") == "testfile"
    assert sanitize_filename_component("test>file") == "testfile"


def test_sanitize_filename_component_control_characters():
    """Test that control characters and null bytes are removed."""
    # Null bytes and control characters should be removed
    assert sanitize_filename_component("test\x00evil") == "testevil"
    assert sanitize_filename_component("test\n\r\tevil") == "testevil"
    assert sanitize_filename_component("test\x01\x02\x03") == "test"


def test_sanitize_filename_component_edge_cases():
    """Test edge cases for filename sanitization."""
    # Empty or None input
    assert sanitize_filename_component("") == "unnamed"
    assert sanitize_filename_component(None) == "unnamed"
    
    # Only dangerous characters
    assert sanitize_filename_component("///") == "unnamed"
    assert sanitize_filename_component("...") == "unnamed"
    assert sanitize_filename_component("|||") == "unnamed"
    
    # Leading/trailing special chars should be stripped
    assert sanitize_filename_component("...test...") == "test"
    assert sanitize_filename_component("---test---") == "test"
    assert sanitize_filename_component("___test___") == "test"


def test_sanitize_filename_component_max_length():
    """Test that filenames are truncated to max length."""
    long_text = "a" * 200
    result = sanitize_filename_component(long_text)
    assert len(result) <= 100
    assert result == "a" * 100
    
    # Test with custom max_length
    result = sanitize_filename_component(long_text, max_length=50)
    assert len(result) == 50


def test_sanitize_filename_component_unicode():
    """Test handling of unicode characters."""
    # Unicode characters should be preserved if alphanumeric
    result = sanitize_filename_component("test_データ_123")
    # Note: \w in Python regex includes unicode letters
    assert "test" in result
    assert "123" in result


def test_export_run_as_text():
    """Test exporting run as text."""
    run = {
        "ts_epoch": 1704067200,
        "duration_ms": 123.45,
        "ok": True,
        "output_text": "Sample output",
        "is_filtered": False,
        "is_truncated": False,
        "original_line_count": 10,
    }
    
    result = export_run_as_text(run, "DeviceA", "show version")
    
    assert "DeviceA" in result
    assert "show version" in result
    assert "Sample output" in result
    assert "Success" in result
    assert "123.45ms" in result


def test_export_run_as_text_with_error():
    """Test exporting failed run as text."""
    run = {
        "ts_epoch": 1704067200,
        "duration_ms": 50.0,
        "ok": False,
        "error_message": "Connection failed",
        "is_filtered": False,
        "is_truncated": False,
    }
    
    result = export_run_as_text(run, "DeviceB", "show interfaces")
    
    assert "DeviceB" in result
    assert "show interfaces" in result
    assert "Error" in result
    assert "Connection failed" in result


def test_export_run_as_json():
    """Test exporting run as JSON."""
    run = {
        "ts_epoch": 1704067200,
        "duration_ms": 123.45,
        "ok": True,
        "output_text": "Sample output",
        "is_filtered": False,
        "is_truncated": True,
        "original_line_count": 500,
    }
    
    result = export_run_as_json(run, "DeviceA", "show version")
    data = json.loads(result)
    
    assert data["device"] == "DeviceA"
    assert data["command"] == "show version"
    assert data["status"] == "success"
    assert data["output"] == "Sample output"
    assert data["is_truncated"] is True
    assert data["original_line_count"] == 500


def test_export_bulk_runs_as_json():
    """Test exporting bulk runs as JSON."""
    runs_by_device = {
        "DeviceA": [
            {
                "ts_epoch": 1704067200,
                "duration_ms": 100.0,
                "ok": True,
                "output_text": "Output A",
                "is_filtered": False,
                "is_truncated": False,
                "original_line_count": 10,
            }
        ],
        "DeviceB": [
            {
                "ts_epoch": 1704067300,
                "duration_ms": 150.0,
                "ok": True,
                "output_text": "Output B",
                "is_filtered": False,
                "is_truncated": False,
                "original_line_count": 15,
            }
        ],
    }
    
    result = export_bulk_runs_as_json(runs_by_device, "show version")
    data = json.loads(result)
    
    assert data["command"] == "show version"
    assert "DeviceA" in data["devices"]
    assert "DeviceB" in data["devices"]
    assert len(data["devices"]["DeviceA"]) == 1
    assert data["devices"]["DeviceA"][0]["output"] == "Output A"
    assert data["devices"]["DeviceB"][0]["output"] == "Output B"


def test_export_ping_data_as_csv():
    """Test exporting ping data as CSV."""
    ping_samples = [
        {
            "ts_epoch": 1704067200,
            "ok": True,
            "rtt_ms": 12.5,
            "error_message": None,
        },
        {
            "ts_epoch": 1704067201,
            "ok": False,
            "rtt_ms": None,
            "error_message": "Timeout",
        },
    ]
    
    result = export_ping_data_as_csv(ping_samples, "DeviceA")
    
    lines = result.strip().split('\n')
    assert len(lines) == 3  # Header + 2 data rows
    assert "Device" in lines[0]
    assert "Timestamp" in lines[0]
    assert "RTT_ms" in lines[0]
    assert "DeviceA" in lines[1]
    assert "success" in lines[1]
    assert "12.5" in lines[1]
    assert "failure" in lines[2]
    assert "Timeout" in lines[2]


def test_export_ping_data_as_json():
    """Test exporting ping data as JSON."""
    ping_samples = [
        {
            "ts_epoch": 1704067200,
            "ok": True,
            "rtt_ms": 12.5,
            "error_message": None,
        },
        {
            "ts_epoch": 1704067201,
            "ok": False,
            "rtt_ms": None,
            "error_message": "Timeout",
        },
    ]
    
    result = export_ping_data_as_json(ping_samples, "DeviceA")
    data = json.loads(result)
    
    assert data["device"] == "DeviceA"
    assert len(data["samples"]) == 2
    assert data["samples"][0]["status"] == "success"
    assert data["samples"][0]["rtt_ms"] == 12.5
    assert data["samples"][1]["status"] == "failure"
    assert data["samples"][1]["error_message"] == "Timeout"


def test_export_diff_as_text():
    """Test exporting diff as text."""
    result = export_diff_as_text("<html>diff</html>", "Previous", "Latest")
    
    assert "Previous" in result
    assert "Latest" in result
    assert "Diff Export" in result


def test_export_diff_as_html():
    """Test exporting diff as HTML."""
    diff_html = '<table><tr><td>test</td></tr></table>'
    result = export_diff_as_html(diff_html, "DeviceA", "DeviceB")
    
    assert "<!DOCTYPE html>" in result
    assert "DeviceA" in result
    assert "DeviceB" in result
    assert diff_html in result
    assert "<style>" in result
