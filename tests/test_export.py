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
)


def test_format_timestamp_jst():
    """Test JST timestamp formatting."""
    # 2024-01-01 00:00:00 UTC = 2024-01-01 09:00:00 JST
    epoch = 1704067200
    result = format_timestamp_jst(epoch)
    assert result == "2024-01-01 09:00:00 JST"


def test_format_timestamp_jst_day_boundary():
    """Test JST timestamp formatting across day boundary."""
    # 2024-01-01 23:00:00 UTC = 2024-01-02 08:00:00 JST (crosses day boundary)
    epoch = 1704150000
    result = format_timestamp_jst(epoch)
    assert result == "2024-01-02 08:00:00 JST"


def test_format_timestamp_jst_various_hours():
    """Test JST timestamp formatting at various hours."""
    # 2024-01-01 12:00:00 UTC = 2024-01-01 21:00:00 JST
    epoch_midday = 1704110400
    result_midday = format_timestamp_jst(epoch_midday)
    assert result_midday == "2024-01-01 21:00:00 JST"
    
    # 2024-01-01 15:30:45 UTC = 2024-01-02 00:30:45 JST (crosses day boundary)
    epoch_afternoon = 1704123045
    result_afternoon = format_timestamp_jst(epoch_afternoon)
    assert result_afternoon == "2024-01-02 00:30:45 JST"
    
    # 2024-01-01 06:00:00 UTC = 2024-01-01 15:00:00 JST
    epoch_morning = 1704088800
    result_morning = format_timestamp_jst(epoch_morning)
    assert result_morning == "2024-01-01 15:00:00 JST"


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
