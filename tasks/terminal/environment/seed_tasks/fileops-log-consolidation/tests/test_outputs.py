import os
import json
import chardet
from datetime import datetime
import pytest

def test_output_files_exist():
    """Verify all required output files were created."""
    assert os.path.exists('/app/output/repaired.log'), "repaired.log not found"
    assert os.path.exists('/app/output/validation_report.json'), "validation_report.json not found"
    assert os.path.exists('/app/output/suspicious_entries.ndjson'), "suspicious_entries.ndjson not found"

def test_files_are_valid_utf8():
    """Verify all output files are valid UTF-8."""
    for filename in ['repaired.log', 'validation_report.json', 'suspicious_entries.ndjson']:
        with open(f'/app/output/{filename}', 'rb') as f:
            content = f.read()
            # Try to decode as UTF-8
            try:
                content.decode('utf-8')
            except UnicodeDecodeError:
                pytest.fail(f"{filename} contains invalid UTF-8")

def test_repaired_log_has_valid_json():
    """Verify each line in repaired.log is valid JSON."""
    with open('/app/output/repaired.log', 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if line:  # Skip empty lines
                try:
                    entry = json.loads(line)
                    assert isinstance(entry, dict), f"Line {i}: not a JSON object"
                except json.JSONDecodeError as e:
                    pytest.fail(f"Line {i}: invalid JSON - {e}")

def test_repaired_log_matches_schema():
    """Verify entries match the schema requirements."""
    with open('/app/logs/schema.json', 'r') as f:
        schema = json.load(f)
    
    required_fields = set(schema['required_fields'])
    field_types = schema['field_types']
    
    with open('/app/output/repaired.log', 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if line:
                entry = json.loads(line)
                
                # Check required fields
                missing = required_fields - set(entry.keys())
                assert not missing, f"Line {i}: missing required fields {missing}"
                
                # Check field types
                for field, expected_type in field_types.items():
                    if field in entry:
                        if expected_type == 'timestamp':
                            # Should be ISO 8601 format
                            try:
                                datetime.fromisoformat(entry[field].replace('Z', '+00:00'))
                            except (ValueError, TypeError):
                                pytest.fail(f"Line {i}: field '{field}' not valid ISO timestamp")
                        elif expected_type == 'integer':
                            assert isinstance(entry[field], int), f"Line {i}: field '{field}' not integer"
                        elif expected_type == 'string':
                            assert isinstance(entry[field], str), f"Line {i}: field '{field}' not string"

def test_timestamps_are_sorted():
    """Verify entries are sorted by timestamp."""
    timestamps = []
    with open('/app/output/repaired.log', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                entry = json.loads(line)
                ts = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                timestamps.append(ts)
    
    # Check if sorted
    for i in range(1, len(timestamps)):
        assert timestamps[i] >= timestamps[i-1], f"Timestamps not sorted at position {i}"

def test_validation_report_structure():
    """Verify validation report has correct structure and consistent counts."""
    with open('/app/output/validation_report.json', 'r') as f:
        report = json.load(f)
    
    # Check structure
    required_keys = ['total_entries', 'valid_entries', 'repaired_entries', 
                    'unrecoverable_entries', 'corruption_types', 'repair_sources']
    for key in required_keys:
        assert key in report, f"Missing key in report: {key}"
    
    # Check corruption_types structure
    corruption_keys = ['encoding', 'missing_fields', 'timestamp', 'truncation']
    for key in corruption_keys:
        assert key in report['corruption_types'], f"Missing corruption type: {key}"
    
    # Check repair_sources structure
    source_keys = ['schema_defaults', 'previous_entry', 'patch_file']
    for key in source_keys:
        assert key in report['repair_sources'], f"Missing repair source: {key}"
    
    # Check counts are consistent
    total = report['total_entries']
    valid = report['valid_entries']
    repaired = report['repaired_entries']
    unrecoverable = report['unrecoverable_entries']
    
    assert total == valid + repaired + unrecoverable, "Counts don't add up"
    
    # Verify counts match actual repaired.log
    with open('/app/output/repaired.log', 'r', encoding='utf-8') as f:
        actual_count = sum(1 for line in f if line.strip())
    
    assert actual_count == valid + repaired, "Reported valid+repaired doesn't match actual output count"

def test_suspicious_entries_format():
    """Verify suspicious entries file format."""
    with open('/app/output/suspicious_entries.ndjson', 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    assert isinstance(entry, dict), f"Suspicious entry {i}: not a JSON object"
                    # Should have at least a reason field
                    assert 'reason' in entry, f"Suspicious entry {i}: missing reason"
                except json.JSONDecodeError as e:
                    pytest.fail(f"Suspicious entry {i}: invalid JSON - {e}")

def test_no_data_loss():
    """Verify no unexpected data loss occurred."""
    # Count input entries (including corrupted ones we can detect)
    input_count = 0
    with open('/app/logs/main.log', 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.strip():
                input_count += 1
    
    # Count output entries
    output_count = 0
    with open('/app/output/repaired.log', 'r', encoding='utf-8') as f:
        output_count = sum(1 for line in f if line.strip())
    
    with open('/app/output/validation_report.json', 'r') as f:
        report = json.load(f)
    
    # Output should equal input minus unrecoverable
    expected_output = input_count - report['unrecoverable_entries']
    assert output_count == expected_output, f"Data loss: expected {expected_output}, got {output_count}"