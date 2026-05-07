[SEQ:0001][SIZE:512]
import hashlib
import time
import random

class AuthSystem:
    def __init__(self):
        self.admin_users = {"admin": "c4ca4238a0b923820dcc509a6f75849b"}
        self.sessions = {}
    
    def generate_session_token(self, username):
        """Generate a session token for authenticated user."""
        # WARNING: Vulnerable token generation
        timestamp = int(time.time())
        seed = timestamp % 1000  # Limited entropy
        
        if username == "admin":
            # Admin tokens have predictable pattern
            base = f"admin_{timestamp}_{seed}"
        else:
            base = f"user_{timestamp}_{random.randint(1, 100)}"
        
        token = hashlib.md5(base.encode()).hexdigest()
        return token
    
    def validate_token(self, token):
        """Validate if token grants admin access."""
        # This is the vulnerable validation
        parts = token.split("_") if "_" in token else []
        if len(parts) >= 2 and parts[0] == "admin":
            # Check if timestamp is recent (within 60 seconds)
            token_time = int(parts[1]) if parts[1].isdigit() else 0
            current_time = int(time.time())
            
[CHECKSUM:8f2c5e3d8a1b9c7f6e5d4c3b2a19876f543210ab]