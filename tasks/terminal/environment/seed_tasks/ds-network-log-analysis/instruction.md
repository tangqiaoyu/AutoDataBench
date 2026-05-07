# Network Log Anomaly Detection and Session Analysis

You are a data scientist working for a cybersecurity firm. You've been given network log data from a client's web application to analyze for suspicious patterns and user behavior.

## Your Task

Analyze the network logs in `/app/logs/network_logs.txt` to:

1. **Load and Parse the Log Data**:
   - The log file contains semi-structured data with fields: `timestamp`, `user_id`, `endpoint`, `http_method`, `status_code`, `response_time_ms`
   - Parse each line using regex to extract these fields
   - Handle missing or malformed entries by logging them to `/app/output/parse_errors.json`
   - Convert timestamps to datetime objects and response_time_ms to numeric

2. **Session Detection and Analysis**:
   - Define a user session as consecutive requests from the same user where gaps between requests are ≤ 5 minutes
   - For each user, identify all sessions and compute:
     - Session duration (first to last request)
     - Number of requests per session
     - Average response time per session
     - Status code distribution (count of 2xx, 3xx, 4xx, 5xx)
   - Save session-level analysis to `/app/output/user_sessions.csv` with columns: `user_id`, `session_id`, `start_time`, `end_time`, `request_count`, `avg_response_ms`, `status_2xx`, `status_3xx`, `status_4xx`, `status_5xx`

3. **Anomaly Detection**:
   - Detect potential DDoS patterns: users with >10 requests per minute on average
   - Detect suspicious endpoints: endpoints receiving >50% 4xx or 5xx errors
   - Detect abnormal response times: requests with response_time_ms > 3 standard deviations from the mean for that endpoint
   - Save anomaly report to `/app/output/anomalies.json` with structure:
     ```json
     {
       "potential_ddos_users": [list of user_ids],
       "suspicious_endpoints": [list of endpoints],
       "slow_requests": [list of {"timestamp": "...", "user_id": "...", "endpoint": "...", "response_time_ms": N}],
       "summary_stats": {
         "total_requests": N,
         "unique_users": N,
         "error_rate": 0.XX,
         "avg_response_time": N.N
       }
     }
     ```

4. **Visualization Generation**:
   - Create an hourly request volume chart showing requests per hour
   - Save visualization to `/app/output/request_volume.png`
   - Generate a markdown report at `/app/output/analysis_summary.md` containing:
     - Key statistics (total requests, unique users, error rate)
     - Top 5 most active users
     - Top 5 most accessed endpoints
     - Anomaly summary

## Expected Outputs
- `/app/output/parse_errors.json` - JSON list of lines that couldn't be parsed
- `/app/output/user_sessions.csv` - CSV file with session analysis
- `/app/output/anomalies.json` - JSON anomaly report with specified structure
- `/app/output/request_volume.png` - PNG chart of hourly request volume
- `/app/output/analysis_summary.md` - Markdown summary report

## Data Format Details
Each log line follows this pattern:
```
[2024-03-15 14:30:25] user_1234 GET /api/data 200 145
[2024-03-15 14:30:27] user_5678 POST /api/login 401 89
[2024-03-15 14:30:30] user_1234 GET /api/profile 200 210
```
Where fields are: `[timestamp] user_id http_method endpoint status_code response_time_ms`

Some lines may be malformed or have missing fields - handle these gracefully.

## Success Criteria
The tests will verify:
1. All output files exist and are in correct formats
2. Session detection logic correctly groups requests within 5-minute windows
3. Anomaly detection identifies users with >10 requests/minute
4. JSON outputs are valid and contain required keys
5. Statistical calculations are accurate within tolerance