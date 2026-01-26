#!/bin/bash
# =============================================================================
# Export MySQL data from DigitalOcean server
# =============================================================================
# This script connects via SSH and dumps both MySQL databases
#
# Usage:
#   ./scripts/export_mysql.sh
# =============================================================================

set -e

SERVER="142.93.136.113"
SSH_USER="root"
SSH_KEY="$HOME/.ssh/id_rsa"

# Output directory
BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"

DATE=$(date +%Y%m%d_%H%M%S)

echo "=============================================="
echo "  MySQL Export Script"
echo "=============================================="
echo "Server: $SSH_USER@$SERVER"
echo ""

# Export English-Russian bot database
echo "[1/2] Exporting word_learner (EN-RU)..."
ssh -i "$SSH_KEY" "$SSH_USER@$SERVER" \
    "mysqldump -u word_learner -p'password' word_learner" \
    > "$BACKUP_DIR/word_learner_en_$DATE.sql"
echo "  Saved: $BACKUP_DIR/word_learner_en_$DATE.sql"

# Export Dutch-English bot database
echo "[2/2] Exporting word_learner_dutch (Dutch-EN)..."
ssh -i "$SSH_KEY" "$SSH_USER@$SERVER" \
    "mysqldump -u word_learner_dutch -p'password' word_learner_dutch" \
    > "$BACKUP_DIR/word_learner_dutch_$DATE.sql"
echo "  Saved: $BACKUP_DIR/word_learner_dutch_$DATE.sql"

echo ""
echo "=============================================="
echo "  Export Complete!"
echo "=============================================="
echo ""
echo "Files:"
ls -lh "$BACKUP_DIR"/*_$DATE.sql
echo ""
echo "Next: Update the migration script with Railway PostgreSQL URLs"
