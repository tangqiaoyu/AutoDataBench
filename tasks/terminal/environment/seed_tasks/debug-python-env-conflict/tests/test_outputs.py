import os
import subprocess
import sys
import pkg_resources
from pathlib import Path

def test_output_exists():
    """Verify all required output files were created."""
    assert os.path.exists('/app/output/analysis.txt'), "analysis.txt missing"
    assert os.path.exists('/app/project/requirements_resolved.txt'), "requirements_resolved.txt missing"
    assert os.path.exists('/app/output/reproduce.py'), "reproduce.py missing"

def test_analysis_format():
    """Verify analysis.txt has required sections."""
    with open('/app/output/analysis.txt', 'r') as f:
        content = f.read()
    
    sections = ['ROOT CAUSE:', 'DEPENDENCY GRAPH:', 'COMPATIBLE VERSION FOUND:', 
                'WORKAROUND:', 'EVIDENCE:']
    
    for section in sections:
        assert section in content, f"Missing section: {section}"

def test_requirements_resolved():
    """Verify the resolved requirements allow all tests to pass."""
    # Backup original requirements
    orig_req = Path('/app/project/requirements.txt').read_text()
    
    try:
        # Install resolved requirements
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 
                       '/app/project/requirements_resolved.txt', '--quiet'], 
                      check=True, capture_output=True)
        
        # Run all tests
        result = subprocess.run(['pytest', '/app/project/tests/', '-v'],
                              capture_output=True, text=True)
        
        # Check all tests pass
        assert result.returncode == 0, f"Tests failed with resolved requirements:\n{result.stdout}\n{result.stderr}"
        
        # Verify all 3 test files were run
        assert '3 passed' in result.stdout or '3/3' in result.stdout
        
    finally:
        # Restore original requirements
        Path('/app/project/requirements.txt').write_text(orig_req)

def test_reproduce_script():
    """Verify the reproduction script runs and demonstrates the issue."""
    # Run the reproduction script
    result = subprocess.run([sys.executable, '/app/output/reproduce.py'],
                          capture_output=True, text=True)
    
    # Script should run (may show error, but shouldn't crash)
    assert result.returncode == 0 or 'Error' in result.stderr or 'Conflict' in result.stdout
    
    # Should mention the conflicting package
    assert 'numpy' in result.stdout + result.stderr

def test_dependency_constraints():
    """Verify all original dependencies are preserved."""
    with open('/app/project/requirements.txt', 'r') as f:
        original = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    with open('/app/project/requirements_resolved.txt', 'r') as f:
        resolved = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    # Check all original packages are present (allow version changes)
    original_pkgs = {pkg.split('==')[0].split('>=')[0].split('<=')[0].strip() 
                    for pkg in original if '==' in pkg or '>=' in pkg or '<=' in pkg}
    
    resolved_pkgs = {pkg.split('==')[0].split('>=')[0].split('<=')[0].strip() 
                    for pkg in resolved if '==' in pkg or '>=' in pkg or '<=' in pkg}
    
    missing = original_pkgs - resolved_pkgs
    assert len(missing) == 0, f"Missing packages in resolved requirements: {missing}"