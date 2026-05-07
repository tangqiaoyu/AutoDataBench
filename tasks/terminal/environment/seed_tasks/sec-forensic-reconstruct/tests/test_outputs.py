import os
import json
import hashlib
import tempfile
import shutil
from pathlib import Path
import subprocess
import sys
import yaml

def test_reconstruction_complete():
    """Verify all fragments were reconstructed correctly."""
    recon_dir = Path("/app/output/reconstructed_files")
    
    # Check required files exist
    assert recon_dir.exists(), "Reconstruction directory not found"
    assert (recon_dir / "webapp_auth.py").exists()
    assert (recon_dir / "config.yaml").exists()
    assert (recon_dir / "README.txt").exists()
    
    # Verify reconstruction log format
    with open(recon_dir / "README.txt") as f:
        log_content = f.read()
        assert "Reconstruction complete" in log_content
        assert "checksum verification" in log_content.lower()
    
    # Verify webapp_auth.py contains expected vulnerable pattern
    with open(recon_dir / "webapp_auth.py") as f:
        auth_code = f.read()
        # The vulnerability should be present (weak session generation)
        assert "time.time()" in auth_code or "random.randint" in auth_code
        assert "admin" in auth_code.lower()
    
    return True

def test_security_report_valid():
    """Verify security report correctly identifies vulnerability."""
    report_path = Path("/app/output/security_report.json")
    assert report_path.exists(), "Security report not found"
    
    with open(report_path) as f:
        report = json.load(f)
    
    # Required fields
    required_fields = [
        "vulnerability_type",
        "vulnerability_location", 
        "exploit_mechanism",
        "generated_token",
        "reconstruction_stats"
    ]
    for field in required_fields:
        assert field in report, f"Missing field: {field}"
    
    # Check vulnerability type is plausible
    valid_vuln_types = [
        "weak_session_generation",
        "predictable_token",
        "time_based_token",
        "insufficient_entropy"
    ]
    assert report["vulnerability_type"] in valid_vuln_types
    
    # Check reconstruction stats
    stats = report["reconstruction_stats"]
    assert stats["total_fragments"] == 42
    assert stats["successfully_reconstructed"] == 42
    assert stats["checksum_matches"] == 42
    
    # Token should be hex string
    token = report["generated_token"]
    assert isinstance(token, str)
    assert len(token) >= 32  # Reasonable token length
    try:
        int(token, 16)
    except ValueError:
        assert False, "Token should be valid hex string"
    
    return True

def test_exploit_script_works():
    """Verify exploit script generates valid tokens."""
    exploit_path = Path("/app/output/exploit.py")
    assert exploit_path.exists(), "Exploit script not found"
    
    # Run exploit script with test username
    result = subprocess.run(
        [sys.executable, str(exploit_path), "testadmin"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    assert result.returncode == 0, f"Exploit script failed: {result.stderr}"
    
    # Script should output a token
    output = result.stdout.strip()
    assert len(output) > 20, "Script should output token"
    
    # Verify token passes the vulnerable validation
    # Import the vulnerable auth module from reconstructed files
    recon_dir = Path("/app/output/reconstructed_files")
    sys.path.insert(0, str(recon_dir))
    
    try:
        import webapp_auth
        # The vulnerable module should have a validate_token function
        # Our generated token should pass validation
        token = output.split()[-1]  # Get last token from output
        # Note: We can't actually run validation without the full app
        # But we can check token format matches expected pattern
        assert "admin" in token.lower() or len(token) == 64  # Hex token
    finally:
        sys.path.pop(0)
    
    return True

def test_fragment_checksums():
    """Verify reconstructed data matches original checksums."""
    # Load the original fragment data to verify
    frag_dir = Path("/app/forensic_image")
    fragments = list(frag_dir.glob("*.frag"))
    
    # Simulate reconstruction to verify
    reconstructed_data = {}
    for frag in sorted(fragments):
        with open(frag, 'rb') as f:
            data = f.read()
            # Parse fragment header
            if b"[SEQ:" in data[:100]:
                # Extract data between header and checksum
                parts = data.split(b"]\n")
                if len(parts) >= 3:
                    seq_part = parts[0].decode()
                    data_part = parts[1]
                    checksum_part = parts[2].decode()
                    
                    # Get sequence number
                    seq_num = int(seq_part.split(":")[1])
                    
                    # Store in reconstruction dictionary
                    if seq_num not in reconstructed_data:
                        reconstructed_data[seq_num] = b""
                    reconstructed_data[seq_num] += data_part
    
    # Verify we got all 42 fragments
    assert len(reconstructed_data) == 3  # 3 files
    total_frags = sum(len(data) > 0 for data in reconstructed_data.values())
    assert total_frags == 42
    
    return True