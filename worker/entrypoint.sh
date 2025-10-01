#!/bin/sh
# worker/entrypoint.sh

# Exit immediately if a command exits with a non-zero status.
set -e

echo "🔒 Worker Entrypoint: Running as ROOT to configure firewall..."

# Check if the trusted Gateway IP was provided
if [ -z "$GATEWAY_INTERNAL_IP" ]; then
    echo "🔥 FATAL: GATEWAY_INTERNAL_IP environment variable is not set."
    exit 1
fi

# --- Configure the IPTables Firewall Jail ---
# 1. Set the default policy for incoming traffic to DROP (deny all).
iptables -P INPUT DROP

# 2. Allow all traffic on the loopback interface (for internal communication like FastAPI -> Jupyter).
iptables -A INPUT -i lo -j ACCEPT

# 3. Allow established and related connections to continue. This is essential.
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# 4. The Golden Rule: Explicitly allow incoming traffic on port 8000 ONLY from the Gateway's IP.
iptables -A INPUT -p tcp -m tcp --dport 8000 -s "$GATEWAY_INTERNAL_IP" -j ACCEPT

echo "✅ Firewall jail configured. Only IP $GATEWAY_INTERNAL_IP can access this worker."
echo "🚀 Dropping privileges and starting Supervisor..."

# Use exec to replace this script's process with the supervisord process.
# Tini will act as the init system.
# Supervisord will now start jupyter and fastapi as the 'sandbox' user.
exec /usr/bin/tini -- /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
