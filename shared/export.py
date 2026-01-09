"""Export utilities for network device monitoring data."""
import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def format_timestamp_jst(epoch: int) -> str:
    """Format UTC epoch timestamp as JST datetime string.
    
    Args:
        epoch: UTC epoch timestamp in seconds
        
    Returns:
        Formatted datetime string in JST (UTC+9)
    """
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    jst_tz = timezone(timedelta(hours=9))
    jst_dt = dt.astimezone(jst_tz)
    return jst_dt.strftime('%Y-%m-%d %H:%M:%S JST')


def export_run_as_text(run: Dict[str, Any], device: str, command: str) -> str:
    """Export a single run as formatted text.
    
    Args:
        run: Run data dictionary
        device: Device name
        command: Command text
        
    Returns:
        Formatted text output with metadata
    """
    lines = []
    lines.append("=" * 80)
    lines.append(f"Network Watch - Command Output Export")
    lines.append("=" * 80)
    lines.append(f"Device: {device}")
    lines.append(f"Command: {command}")
    lines.append(f"Timestamp: {format_timestamp_jst(run['ts_epoch'])}")
    lines.append(f"Duration: {run.get('duration_ms', 'N/A')}ms")
    lines.append(f"Status: {'Success' if run.get('ok') else 'Error'}")
    
    if run.get('is_filtered'):
        lines.append("Filtered: Yes")
    if run.get('is_truncated'):
        lines.append("Truncated: Yes")
    if run.get('original_line_count'):
        lines.append(f"Original Line Count: {run['original_line_count']}")
    
    lines.append("=" * 80)
    lines.append("")
    
    if run.get('ok'):
        lines.append(run.get('output_text', '(no output)'))
    else:
        lines.append(f"Error: {run.get('error_message', 'Unknown error')}")
    
    return '\n'.join(lines)


def export_run_as_json(run: Dict[str, Any], device: str, command: str) -> str:
    """Export a single run as JSON.
    
    Args:
        run: Run data dictionary
        device: Device name
        command: Command text
        
    Returns:
        JSON string with metadata and output
    """
    export_data = {
        "device": device,
        "command": command,
        "timestamp": format_timestamp_jst(run['ts_epoch']),
        "timestamp_epoch": run['ts_epoch'],
        "duration_ms": run.get('duration_ms'),
        "status": "success" if run.get('ok') else "error",
        "output": run.get('output_text') if run.get('ok') else None,
        "error_message": run.get('error_message') if not run.get('ok') else None,
        "is_filtered": bool(run.get('is_filtered')),
        "is_truncated": bool(run.get('is_truncated')),
        "original_line_count": run.get('original_line_count')
    }
    return json.dumps(export_data, indent=2)


def export_bulk_runs_as_json(runs_by_device: Dict[str, List[Dict[str, Any]]], command: str) -> str:
    """Export multiple device runs as JSON.
    
    Args:
        runs_by_device: Dictionary mapping device names to lists of runs
        command: Command text
        
    Returns:
        JSON string with all device outputs
    """
    export_data = {
        "command": command,
        "export_timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
        "devices": {}
    }
    
    for device, runs in runs_by_device.items():
        export_data["devices"][device] = [
            {
                "timestamp": format_timestamp_jst(run['ts_epoch']),
                "timestamp_epoch": run['ts_epoch'],
                "duration_ms": run.get('duration_ms'),
                "status": "success" if run.get('ok') else "error",
                "output": run.get('output_text') if run.get('ok') else None,
                "error_message": run.get('error_message') if not run.get('ok') else None,
                "is_filtered": bool(run.get('is_filtered')),
                "is_truncated": bool(run.get('is_truncated')),
                "original_line_count": run.get('original_line_count')
            }
            for run in runs
        ]
    
    return json.dumps(export_data, indent=2)


def export_ping_data_as_csv(ping_samples: List[Dict[str, Any]], device: str) -> str:
    """Export ping samples as CSV.
    
    Args:
        ping_samples: List of ping sample dictionaries
        device: Device name
        
    Returns:
        CSV string with ping data
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Device', 'Timestamp', 'Timestamp_Epoch', 'Status', 'RTT_ms', 'Error_Message'])
    
    # Write data rows
    for sample in ping_samples:
        writer.writerow([
            device,
            format_timestamp_jst(sample['ts_epoch']),
            sample['ts_epoch'],
            'success' if sample['ok'] else 'failure',
            sample.get('rtt_ms', ''),
            sample.get('error_message', '')
        ])
    
    return output.getvalue()


def export_ping_data_as_json(ping_samples: List[Dict[str, Any]], device: str) -> str:
    """Export ping samples as JSON.
    
    Args:
        ping_samples: List of ping sample dictionaries
        device: Device name
        
    Returns:
        JSON string with ping data
    """
    export_data = {
        "device": device,
        "export_timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
        "samples": [
            {
                "timestamp": format_timestamp_jst(sample['ts_epoch']),
                "timestamp_epoch": sample['ts_epoch'],
                "status": "success" if sample['ok'] else "failure",
                "rtt_ms": sample.get('rtt_ms'),
                "error_message": sample.get('error_message')
            }
            for sample in ping_samples
        ]
    }
    return json.dumps(export_data, indent=2)


def export_diff_as_text(diff_html: str, label_a: str, label_b: str) -> str:
    """Export diff as plain text (strip HTML).
    
    Args:
        diff_html: HTML diff content
        label_a: Label for first side
        label_b: Label for second side
        
    Returns:
        Plain text diff header
    """
    lines = []
    lines.append("=" * 80)
    lines.append(f"Network Watch - Diff Export")
    lines.append("=" * 80)
    lines.append(f"Comparing: {label_a} vs {label_b}")
    lines.append(f"Export Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Note: This is an HTML diff. Please view in a web browser.")
    lines.append("")
    
    return '\n'.join(lines)


def export_diff_as_html(diff_html: str, label_a: str, label_b: str) -> str:
    """Export diff as complete HTML document.
    
    Args:
        diff_html: HTML diff content (table)
        label_a: Label for first side
        label_b: Label for second side
        
    Returns:
        Complete HTML document
    """
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Network Watch - Diff Export</title>
    <style>
        body {{
            font-family: monospace;
            margin: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        td, th {{
            padding: 2px 5px;
            font-family: monospace;
            font-size: 12px;
        }}
        .diff_header {{
            background-color: #e0e0e0;
            font-weight: bold;
        }}
        .diff_next {{
            background-color: #c0c0c0;
        }}
        .diff_add {{
            background-color: #d4ffd4;
        }}
        .diff_chg {{
            background-color: #ffffaa;
        }}
        .diff_sub {{
            background-color: #ffdddd;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Network Watch - Diff Export</h1>
        <p><strong>Comparing:</strong> {label_a} vs {label_b}</p>
        <p><strong>Export Time:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    </div>
    {diff_html}
</body>
</html>"""
    return html
