# Log File Integrity Validator and Repair Tool

You are tasked with building a tool that validates and repairs corrupted log files from a distributed system. The system generates logs in a specific structured format, but sometimes log files become corrupted due to encoding issues, missing segments, or malformed entries.

## Input Files
1. `/app/logs/main.log` - Primary log file with potential corruption
2. `/app/logs/schema.json` - Schema definition for valid log entries
3. `/app/logs/reference.patch` - Patch file containing known good log segments

## Your Task

### Phase 1: Schema Validation
Read the schema from `/app/logs/schema.json` which defines:
- Required fields for each log entry
- Field types (timestamp, string, integer, enum)
- Valid value ranges and patterns
- Encoding requirements (UTF-8)

Validate each line in `/app/logs/main.log` against this schema. Log entries are JSON objects, one per line.

### Phase 2: Corruption Detection and Repair
Identify and fix the following corruption types:

1. **Encoding Issues**: Some entries were saved with mixed encoding (parts in Latin-1, parts in UTF-8). Convert all to valid UTF-8.
2. **Missing Fields**: Some entries are missing required fields. Use values from the most recent valid entry for the same `session_id`.
3. **Malformed Timestamps**: Some timestamps have incorrect format or timezone. Normalize to ISO 8601 format with UTC timezone.
4. **Truncated Entries**: Some entries end abruptly. Use `/app/logs/reference.patch` to find and insert missing segments. The patch file contains valid JSON fragments keyed by entry ID.

### Phase 3: Output Generation
Create the following output files:

1. `/app/output/repaired.log` - The repaired log file with all entries in valid JSON format, one per line, UTF-8 encoded. Entries should be sorted by timestamp.

2. `/app/output/validation_report.json` - A report containing:
   ```json
   {
     "total_entries": integer,
     "valid_entries": integer,
     "repaired_entries": integer,
     "unrecoverable_entries": integer,
     "corruption_types": {
       "encoding": integer,
       "missing_fields": integer,
       "timestamp": integer,
       "truncation": integer
     },
     "repair_sources": {
       "schema_defaults": integer,
       "previous_entry": integer,
       "patch_file": integer
     }
   }
   ```

3. `/app/output/suspicious_entries.ndjson` - Any entries that couldn't be fully repaired or have unusual patterns (e.g., timestamps far from sequence, extreme field values). One JSON object per line.

## Requirements

1. **Memory Efficiency**: Process the log file line-by-line to handle potentially large files.
2. **Error Handling**: Skip only completely unrecoverable entries (log them to stderr).
3. **Encoding Safety**: Ensure all output files are valid UTF-8 with proper error replacement.
4. **Validation Strictness**: Use exact schema validation - entries must match field types and constraints exactly.

## Expected Outputs

- `/app/output/repaired.log` - Complete repaired log in JSONL format
- `/app/output/validation_report.json` - JSON report with statistics
- `/app/output/suspicious_entries.ndjson` - Potentially problematic entries

The tests will verify:
1. All output files exist and are valid UTF-8
2. `repaired.log` contains valid JSON on each line that matches the schema
3. `validation_report.json` has correct counts that match actual repairs
4. No data loss (total entries in output should equal input minus unrecoverable)
5. Timestamps are properly sorted in chronological order