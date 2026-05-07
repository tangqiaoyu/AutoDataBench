[SEQ:0003][SIZE:512]
server:
  host: 0.0.0.0
  port: 8080
  debug: false

security:
  session_secret: "weak_secret_123"
  token_expiry: 3600
  admin_only_endpoints:
    - /admin/dashboard
    - /admin/users
    - /admin/config

database:
  host: localhost
  port: 5432
  name: webapp_db
  user: app_user
  # Password is in environment variable

logging:
  level: INFO
  file: /var/log/webapp.log
  max_size: 10485760

features:
  enable_registration: true
  require_email_verification: false
  two_factor_auth: false

# WARNING: Insecure defaults
# - No password complexity requirements
# - No account lockout mechanism
# - Session tokens predictable
# - Admin interface accessible with weak tokens

# To fix:
# 1. Use cryptographically secure random for tokens
# 2. Implement proper session management
# 3. Add salt to password hashes
# 4. Enable rate limiting
[CHECKSUM:fedcba0987654321fedcba0987654321fedcba09]