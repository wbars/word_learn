#!/bin/bash
# =============================================================================
# PHP Bot Decommission Script
# =============================================================================
# This script safely decommissions the PHP word learner bot by:
# 1. Backing up both MySQL databases
# 2. Downloading backups locally
# 3. Stopping PHP services
# 4. Archiving PHP codebase
# 5. Clearing Telegram webhooks
#
# Prerequisites:
# - SSH access to the PHP server
# - MySQL credentials
# - Bot tokens
#
# Usage:
#   ./scripts/decommission_php.sh [--dry-run]
#
# Environment variables:
#   PHP_USER: SSH user (default: deploy)
#   PHP_SERVER: Server hostname (default: wordlearnertelegram.com)
#   MYSQL_PASSWORD: MySQL password
# =============================================================================

set -e

# Configuration
PHP_SERVER="${PHP_SERVER:-wordlearnertelegram.com}"
PHP_USER="${PHP_USER:-deploy}"
PHP_PATH="/var/www/html"
DATE=$(date +%Y%m%d_%H%M%S)

# Bot tokens (set via environment or replace with actual tokens)
BOT_TOKEN_EN="${BOT_TOKEN_EN:-your_en_bot_token_here}"
BOT_TOKEN_DUTCH="${BOT_TOKEN_DUTCH:-your_dutch_bot_token_here}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo -e "${YELLOW}=== DRY RUN MODE - No changes will be made ===${NC}"
fi

echo ""
echo "=============================================="
echo "  PHP Bot Decommission Script"
echo "=============================================="
echo "Server: $PHP_USER@$PHP_SERVER"
echo "Date: $DATE"
echo "=============================================="
echo ""

# Function to run command (respects dry-run)
run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY RUN] Would execute: $@${NC}"
    else
        echo -e "${GREEN}Executing: $@${NC}"
        eval "$@"
    fi
}

# Function to run SSH command
ssh_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY RUN] Would execute on server: $@${NC}"
    else
        ssh "$PHP_USER@$PHP_SERVER" "$@"
    fi
}

# =============================================================================
# Pre-flight checks
# =============================================================================
echo -e "${GREEN}[0/5] Pre-flight checks...${NC}"

if [ "$DRY_RUN" = false ]; then
    # Test SSH connection
    echo "Testing SSH connection..."
    if ! ssh -o ConnectTimeout=10 "$PHP_USER@$PHP_SERVER" "echo 'SSH connection OK'" 2>/dev/null; then
        echo -e "${RED}Error: Cannot connect to $PHP_USER@$PHP_SERVER${NC}"
        echo "Please check:"
        echo "  1. SSH key is configured"
        echo "  2. Server is reachable"
        echo "  3. PHP_USER and PHP_SERVER are correct"
        exit 1
    fi
fi

# Create local backup directory
mkdir -p ./backups

# =============================================================================
# Step 1: Backup MySQL databases
# =============================================================================
echo ""
echo -e "${GREEN}[1/5] Backing up MySQL databases...${NC}"

# English-Russian bot database
echo "  - Backing up word_learner (EN-RU)..."
ssh_cmd "mysqldump -u word_learner -p\${MYSQL_PASSWORD:-password} word_learner > /tmp/word_learner_en_backup_$DATE.sql"

# Dutch-English bot database
echo "  - Backing up word_learner_dutch (Dutch-EN)..."
ssh_cmd "mysqldump -u word_learner_dutch -p\${MYSQL_PASSWORD:-password} word_learner_dutch > /tmp/word_learner_dutch_backup_$DATE.sql"

# =============================================================================
# Step 2: Download backups locally
# =============================================================================
echo ""
echo -e "${GREEN}[2/5] Downloading backups...${NC}"

if [ "$DRY_RUN" = false ]; then
    scp "$PHP_USER@$PHP_SERVER:/tmp/word_learner_en_backup_$DATE.sql" ./backups/
    scp "$PHP_USER@$PHP_SERVER:/tmp/word_learner_dutch_backup_$DATE.sql" ./backups/
    echo "  - Backups saved to ./backups/"
else
    echo -e "${YELLOW}[DRY RUN] Would download backups to ./backups/${NC}"
fi

# =============================================================================
# Step 3: Stop PHP services
# =============================================================================
echo ""
echo -e "${GREEN}[3/5] Stopping PHP services...${NC}"

# Try different service managers (systemd vs init)
ssh_cmd "sudo systemctl stop php-fpm 2>/dev/null || sudo systemctl stop php8.1-fpm 2>/dev/null || sudo service php-fpm stop 2>/dev/null || echo 'PHP-FPM not running as service'"
ssh_cmd "sudo systemctl stop apache2 2>/dev/null || sudo systemctl stop httpd 2>/dev/null || echo 'Apache not running'"

# =============================================================================
# Step 4: Archive PHP codebase
# =============================================================================
echo ""
echo -e "${GREEN}[4/5] Archiving PHP codebase...${NC}"

ssh_cmd "tar -czf /tmp/wordlearner_php_$DATE.tar.gz -C $PHP_PATH ."

if [ "$DRY_RUN" = false ]; then
    scp "$PHP_USER@$PHP_SERVER:/tmp/wordlearner_php_$DATE.tar.gz" ./backups/
    echo "  - Archive saved to ./backups/wordlearner_php_$DATE.tar.gz"
else
    echo -e "${YELLOW}[DRY RUN] Would download archive to ./backups/${NC}"
fi

# =============================================================================
# Step 5: Clear Telegram webhooks
# =============================================================================
echo ""
echo -e "${GREEN}[5/5] Clearing Telegram webhooks...${NC}"
echo "  (Webhooks should already point to Python bot)"

if [ "$DRY_RUN" = false ]; then
    echo "  - EN-RU bot webhook status:"
    curl -s "https://api.telegram.org/bot${BOT_TOKEN_EN}/getWebhookInfo" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"    URL: {d['result'].get('url', 'Not set')}\")"

    echo "  - Dutch-EN bot webhook status:"
    curl -s "https://api.telegram.org/bot${BOT_TOKEN_DUTCH}/getWebhookInfo" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"    URL: {d['result'].get('url', 'Not set')}\")"
else
    echo -e "${YELLOW}[DRY RUN] Would check webhook status${NC}"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Decommission Complete!${NC}"
echo "=============================================="
echo ""
echo "Backups stored in ./backups/:"
if [ "$DRY_RUN" = false ]; then
    ls -la ./backups/*$DATE* 2>/dev/null || echo "  (no files)"
else
    echo "  word_learner_en_backup_$DATE.sql"
    echo "  word_learner_dutch_backup_$DATE.sql"
    echo "  wordlearner_php_$DATE.tar.gz"
fi
echo ""
echo "PHP services stopped on $PHP_SERVER"
echo ""
echo -e "${YELLOW}To fully remove PHP files:${NC}"
echo "  ssh $PHP_USER@$PHP_SERVER 'rm -rf $PHP_PATH/*'"
echo ""
echo -e "${YELLOW}To restart PHP if rollback needed:${NC}"
echo "  ssh $PHP_USER@$PHP_SERVER 'sudo systemctl start php-fpm'"
echo ""
