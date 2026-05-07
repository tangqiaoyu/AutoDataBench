# Security Challenge: Forensic Data Carver & Authentication Bypass

You've been given a forensic disk image containing fragments from a compromised web application. Your task is to reconstruct the original data, identify a security vulnerability, and craft an exploit to bypass authentication.

## Your Task

1. **File System Exploration**
   - Navigate the directory structure at `/app/forensic_image/`
   - Identify all files with `.frag` extension (these are file fragments)
   - Sort fragments by their embedded sequence numbers to reconstruct original files

2. **Binary Data Reconstruction**
   - Each `.frag` file contains a piece of a larger file in this format:
     ```
     [SEQ:0001][SIZE:512]
     <512 bytes of data>
     [CHECKSUM:e3b0c442...]
     ```
   - Reconstruct the original files by concatenating fragments in sequence order
   - Verify checksums (SHA256) match the data in each fragment

3. **Vulnerability Analysis**
   - One reconstructed file will be `webapp_auth.py` - a Python authentication module
   - Analyze it for security vulnerabilities, focusing on:
     - Session token generation
     - Password comparison
     - Input validation

4. **Exploit Development**
   - Identify and exploit the vulnerability to generate a valid admin session token
   - The token should grant access to `/admin/dashboard` endpoint
   - Implement the exploit in a Python script

## Expected Outputs

- **`/app/output/reconstructed_files/`** - Directory containing reconstructed files:
  - `webapp_auth.py` - Complete authentication module
  - `config.yaml` - Application configuration
  - `README.txt` - Reconstruction log with timestamps and checksums

- **`/app/output/security_report.json`** - JSON report with:
  ```json
  {
    "vulnerability_type": "string",
    "vulnerability_location": "file:line",
    "exploit_mechanism": "string",
    "generated_token": "hex_string",
    "reconstruction_stats": {
      "total_fragments": 42,
      "successfully_reconstructed": 42,
      "checksum_matches": 42
    }
  }
  ```

- **`/app/output/exploit.py`** - Python script that:
  - Takes a username as command-line argument
  - Generates a valid admin session token exploiting the vulnerability
  - Outputs the token and demonstrates it works with sample validation

## Verification Criteria

The tests will check:
1. All fragment files are correctly reconstructed with valid checksums
2. The security report correctly identifies the vulnerability type and location
3. The exploit script generates tokens that pass the vulnerable validation logic
4. Generated tokens grant admin access when validated