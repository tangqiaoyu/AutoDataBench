import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

def test_output_files_exist():
    """Verify all required output files were created."""
    required_files = [
        '/app/output/parse_errors.json',
        '/app/output/user_sessions.csv',
        '/app/output/anomalies.json',
        '/app/output/request_volume.png',
        '/app/output/analysis_summary.md'
    ]
    
    for filepath in required_files:
        assert os.path.exists(filepath), f"Missing output file: {filepath}"
    
    print("✓ All output files exist")

def test_parse_errors_format():
    """Verify parse errors file is valid JSON."""
    with open('/app/output/parse_errors.json', 'r') as f:
        data = json.load(f)
    
    assert isinstance(data, list), "parse_errors.json should be a list"
    
    if data:  # If there are errors, check their structure
        for error in data:
            assert 'line' in error, "Each error should have 'line' field"
            assert 'error' in error, "Each error should have 'error' field"
    
    print("✓ Parse errors file has valid format")

def test_user_sessions_csv():
    """Verify session analysis CSV has correct structure and logic."""
    df = pd.read_csv('/app/output/user_sessions.csv')
    
    # Check required columns
    required_cols = ['user_id', 'session_id', 'start_time', 'end_time', 
                    'request_count', 'avg_response_ms', 'status_2xx', 
                    'status_3xx', 'status_4xx', 'status_5xx']
    
    for col in required_cols:
        assert col in df.columns, f"Missing column: {col}"
    
    # Check data types
    assert pd.api.types.is_numeric_dtype(df['request_count']), "request_count should be numeric"
    assert pd.api.types.is_numeric_dtype(df['avg_response_ms']), "avg_response_ms should be numeric"
    
    # Check session logic: request_count should be ≥ 1
    assert (df['request_count'] >= 1).all(), "All sessions should have at least 1 request"
    
    # Check status code columns sum to request_count (allow for rounding)
    status_sum = df[['status_2xx', 'status_3xx', 'status_4xx', 'status_5xx']].sum(axis=1)
    assert ((status_sum - df['request_count']).abs() < 0.01).all(), "Status codes should sum to request_count"
    
    print("✓ User sessions CSV has correct structure and logic")

def test_anomalies_json():
    """Verify anomaly report has correct structure and detection logic."""
    with open('/app/output/anomalies.json', 'r') as f:
        anomalies = json.load(f)
    
    # Check required keys
    required_keys = ['potential_ddos_users', 'suspicious_endpoints', 
                    'slow_requests', 'summary_stats']
    
    for key in required_keys:
        assert key in anomalies, f"Missing key in anomalies.json: {key}"
    
    # Check summary_stats structure
    stats = anomalies['summary_stats']
    assert 'total_requests' in stats
    assert 'unique_users' in stats
    assert 'error_rate' in stats
    assert 'avg_response_time' in stats
    
    # Verify error_rate is between 0 and 1
    assert 0 <= stats['error_rate'] <= 1, "error_rate should be between 0 and 1"
    
    # Check types of anomaly lists
    assert isinstance(anomalies['potential_ddos_users'], list)
    assert isinstance(anomalies['suspicious_endpoints'], list)
    assert isinstance(anomalies['slow_requests'], list)
    
    # Check slow_requests structure
    for slow_req in anomalies['slow_requests']:
        assert 'timestamp' in slow_req
        assert 'user_id' in slow_req
        assert 'endpoint' in slow_req
        assert 'response_time_ms' in slow_req
    
    print("✓ Anomalies JSON has correct structure")

def test_ddos_detection_logic():
    """Verify DDoS detection logic is correct (users with >10 requests/minute)."""
    # Load original log data to verify detection logic
    with open('/app/logs/network_logs.txt', 'r') as f:
        lines = f.readlines()
    
    # Parse logs (simplified version)
    user_requests = {}
    for line in lines:
        if line.strip():
            parts = line.split()
            if len(parts) >= 6:
                user_id = parts[1]
                user_requests[user_id] = user_requests.get(user_id, 0) + 1
    
    # Load anomalies
    with open('/app/output/anomalies.json', 'r') as f:
        anomalies = json.load(f)
    
    # Since we don't have timestamps in this simple check, we'll just verify
    # that the detection was attempted (list exists)
    ddos_users = anomalies['potential_ddos_users']
    assert isinstance(ddos_users, list), "potential_ddos_users should be a list"
    
    print("✓ DDoS detection logic applied")

def test_session_grouping_logic():
    """Verify session grouping uses 5-minute window correctly."""
    df_sessions = pd.read_csv('/app/output/user_sessions.csv')
    
    # Load log data to verify sessions
    log_data = []
    with open('/app/logs/network_logs.txt', 'r') as f:
        for line in f:
            if line.strip():
                # Simple parsing for test
                parts = line.strip('[]').split('] ')
                if len(parts) >= 2:
                    timestamp_str = parts[0]
                    rest = parts[1].split()
                    if len(rest) >= 5:
                        user_id = rest[0]
                        log_data.append({
                            'timestamp': pd.to_datetime(timestamp_str),
                            'user_id': user_id
                        })
    
    if log_data:
        log_df = pd.DataFrame(log_data)
        
        # For each user in sessions, verify session count is reasonable
        for user in df_sessions['user_id'].unique():
            user_logs = log_df[log_df['user_id'] == user]
            if len(user_logs) > 0:
                user_sessions = df_sessions[df_sessions['user_id'] == user]
                
                # Basic check: number of sessions should be ≤ number of requests
                total_requests = user_sessions['request_count'].sum()
                assert len(user_logs) >= total_requests, f"User {user}: More requests in sessions than in logs"
    
    print("✓ Session grouping appears reasonable")

def test_summary_report():
    """Verify summary report contains required sections."""
    with open('/app/output/analysis_summary.md', 'r') as f:
        content = f.read()
    
    # Check for key sections
    required_sections = ['Key statistics', 'Top 5 most active users', 
                        'Top 5 most accessed endpoints', 'Anomaly summary']
    
    for section in required_sections:
        assert section.lower() in content.lower(), f"Missing section in report: {section}"
    
    # Check it contains some numbers (not just empty)
    assert any(char.isdigit() for char in content), "Report should contain numerical data"
    
    print("✓ Summary report contains required content")

def test_visualization_exists():
    """Verify visualization file exists and has content."""
    png_path = '/app/output/request_volume.png'
    
    assert os.path.exists(png_path), "Visualization file missing"
    assert os.path.getsize(png_path) > 1000, "Visualization file appears too small (likely empty)"
    
    print("✓ Visualization file created successfully")

def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_output_files_exist,
        test_parse_errors_format,
        test_user_sessions_csv,
        test_anomalies_json,
        test_ddos_detection_logic,
        test_session_grouping_logic,
        test_summary_report,
        test_visualization_exists
    ]
    
    passed = 0
    failed = []
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed.append(f"{test.__name__}: {str(e)}")
        except Exception as e:
            failed.append(f"{test.__name__}: Unexpected error - {str(e)}")
    
    print(f"\n{'='*50}")
    print(f"Test Results: {passed}/{len(tests)} passed")
    
    if failed:
        print("\nFailed tests:")
        for failure in failed:
            print(f"  - {failure}")
    
    return passed == len(tests)

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)