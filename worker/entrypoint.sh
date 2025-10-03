#!/bin/sh
# worker/entrypoint.sh

# Exit immediately if a command exits with a non-zero status.
set -e

echo "🔒 Worker Entrypoint: Running as ROOT to configure system..."

# --- Step 1: Configure the IPTables Firewall Jail ---
echo "   -> Configuring firewall..."
if [ -z "$GATEWAY_INTERNAL_IP" ]; then
    echo "🔥 FATAL: GATEWAY_INTERNAL_IP environment variable is not set."
    exit 1
fi
iptables -P INPUT DROP
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -p tcp -m tcp --dport 8000 -s "$GATEWAY_INTERNAL_IP" -j ACCEPT
echo "   -> Firewall configured. Only IP $GATEWAY_INTERNAL_IP can connect."

# --- Step 2: Mount the Virtual Disk ---
echo "   -> Mounting virtual disk device..."
# The /sandbox directory should already exist as the user's home directory.
# Mount the virtual block device (passed in by the Gateway) to /sandbox.
mount /dev/vdisk /sandbox
echo "   -> Virtual disk mounted to /sandbox."

# --- Step 3: Set Final Permissions ---
# After mounting, change the ownership of the new filesystem's root.
chown -R sandbox:sandbox /sandbox
echo "   -> Changed ownership of /sandbox to 'sandbox' user."

# --- Step 4: Drop Privileges and Start Services ---
echo "🚀 Dropping privileges and starting Supervisor..."
# Use exec to replace this script's process with the supervisord process.
# Tini will act as the init system.
# Supervisord will now start jupyter and fastapi as the 'sandbox' user.
exec /usr/bin/tini -- /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
