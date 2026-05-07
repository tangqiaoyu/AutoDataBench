[SEQ:0002][SIZE:512]
            if abs(current_time - token_time) < 60:
                return {"role": "admin", "username": "admin"}
        
        # Check if it's a valid MD5 of admin pattern
        try:
            # This is the exploit: we can predict admin tokens
            for i in range(1000):
                test_base = f"admin_{current_time}_{i}"
                test_token = hashlib.md5(test_base.encode()).hexdigest()
                if test_token == token:
                    return {"role": "admin", "username": "admin"}
        except:
            pass
        
        return {"role": "user", "username": "unknown"}
    
    def login(self, username, password):
        """Authenticate user with password."""
        # MD5 hash of password (vulnerable: no salt)
        password_hash = hashlib.md5(password.encode()).hexdigest()
        
        if username in self.admin_users:
            if self.admin_users[username] == password_hash:
                token = self.generate_session_token(username)
                self.sessions[token] = {
                    "username": username,
                    "role": "admin" if username == "admin" else "user",
                    "expires": time.time() + 3600
                }
                return token
        
        return None

# Configuration
ADMIN_PASSWORD_HASH = "c4ca4238a0b923820dcc509a6f75849b"
SESSION_TIMEOUT = 3600
MAX_LOGIN_ATTEMPTS = 5

# Security note: This implementation has multiple vulnerabilities:
# 1. Predictable session token generation
# 2. Time-based token validation
# 3. Unsalted MD5 password hashes
# 4. No rate limiting on token validation
[CHECKSUM:a1b2c3d4e5f68790a1b2c3d4e5f68790a1b2c3d4]