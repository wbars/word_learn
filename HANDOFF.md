# Word Learn Bot Migration - Handoff Document

**Created:** 2026-01-26 ~21:45
**Status:** In Progress - Data migration partially complete

---

## What's Been Done

### 1. Project Setup (Complete)
- Python project created at `/Users/kirill.smelov/PycharmProjects/word_learn`
- Git repo initialized and pushed to `git@github.com:wbars/word_learn.git`
- Bot tokens REMOVED from git history (were accidentally committed)

### 2. Railway Setup (Complete)
- Project: `patient-reprieve`
- Project ID: `fca71bc1-8b88-40af-99aa-84ea45ccaae9`
- Dashboard: https://railway.com/project/fca71bc1-8b88-40af-99aa-84ea45ccaae9

Services created:
- `bot-en` - 5 variables configured
- `bot-dutch` - 5 variables configured
- `postgres-en` - Online
- `postgres-dutch` - Online

### 3. Database Migrations (Complete)
Both PostgreSQL databases have schema applied via Alembic.

### 4. Data Import (PARTIAL - Issue with Dutch)

**EN-RU Database (postgres-en):** ✅ OK
- Words: 3,198 imported (1 skipped)
- Word practice: 3,151 imported (1,194 skipped - orphaned refs)
- Today practice: 11,195 imported

**Dutch Database (postgres-dutch):** ⚠️ PROBLEM
- Words: Only 224 imported out of ~5,800!
- The parser regex is truncating the VALUES clause
- Issue: `re.search()` with `.*?;` stops at first semicolon inside data

---

## Current Issue: Dutch Words Not Fully Imported

The MySQL dump has ~5,806 words but only 224 were parsed.

**Root cause:** In `scripts/import_to_railway.py`, the regex pattern:
```python
insert_pattern = r"INSERT INTO `?(\w+)`?\s+(?:\([^)]+\)\s+)?VALUES\s*(.*?);"
```
The `.*?;` is non-greedy and stops at the first `;` character that might appear inside string values.

**Fix needed:** Update the parser to handle semicolons inside quoted strings, or use a different approach (e.g., line-by-line parsing).

---

## Database Connection Details

**postgres-en:**
```
postgresql://postgres:hHfWcSokJxSTdefluVEDjgqKydUGVTQt@shortline.proxy.rlwy.net:14039/railway
```

**postgres-dutch:**
```
postgresql://postgres:EluVnhukWpxAGDiaxRBoGxBCXtjCLoiy@shinkansen.proxy.rlwy.net:33993/railway
```

---

## MySQL Backups Location

- Server backups: `root@142.93.136.113:/root/backups/`
- Local backups: `/Users/kirill.smelov/PycharmProjects/word_learn/backups/`
  - `word_learner_20260126_212520.sql` (EN-RU, 880K)
  - `word_learner_dutch_20260126_212525.sql` (Dutch, 980K)

---

## Next Steps To Complete

### 1. Fix Dutch Import
```bash
cd /Users/kirill.smelov/PycharmProjects/word_learn
source .venv/bin/activate

# Clear Dutch database
python -c "
import asyncio, asyncpg
async def clear():
    conn = await asyncpg.connect('postgresql://postgres:EluVnhukWpxAGDiaxRBoGxBCXtjCLoiy@shinkansen.proxy.rlwy.net:33993/railway')
    await conn.execute('DELETE FROM today_practice')
    await conn.execute('DELETE FROM current_practice')
    await conn.execute('DELETE FROM current_practice_stats')
    await conn.execute('DELETE FROM word_skiplist')
    await conn.execute('DELETE FROM word_practice')
    await conn.execute('DELETE FROM reminders')
    await conn.execute('DELETE FROM words')
    await conn.close()
    print('Cleared')
asyncio.run(clear())
"

# Fix the parser in scripts/import_to_railway.py, then re-run:
python scripts/import_to_railway.py backups/word_learner_dutch_20260126_212525.sql "postgresql://postgres:EluVnhukWpxAGDiaxRBoGxBCXtjCLoiy@shinkansen.proxy.rlwy.net:33993/railway"
```

### 2. Deploy Bots on Railway
In Railway dashboard, click **"Deploy"** button to deploy both bots.

Or via CLI:
```bash
railway link -p fca71bc1-8b88-40af-99aa-84ea45ccaae9
railway up -s bot-en
railway up -s bot-dutch
```

### 3. Verify Bots Running
```bash
railway logs -s bot-en
railway logs -s bot-dutch
```

### 4. Switch Telegram Webhooks

**IMPORTANT:** User should regenerate bot tokens first via @BotFather (old ones were leaked).

Once you have new tokens, update Railway env vars, then webhooks are automatic with polling mode.

If using webhook mode, set:
```bash
# Get Railway URLs from dashboard, then:
curl "https://api.telegram.org/bot<NEW_EN_TOKEN>/setWebhook?url=<RAILWAY_BOT_EN_URL>"
curl "https://api.telegram.org/bot<NEW_DUTCH_TOKEN>/setWebhook?url=<RAILWAY_BOT_DUTCH_URL>"
```

### 5. Test Both Bots
- Send `/start` to each bot
- Send `/practice` to verify data migrated correctly

### 6. Decommission PHP (Optional, after verification)
```bash
./scripts/decommission_php.sh
```

---

## Bot Tokens (REGENERATE THESE!)

The old tokens were briefly exposed on GitHub. Regenerate via @BotFather:

- EN-RU bot: Get new token, update `BOT_TOKEN` in Railway `bot-en` service
- Dutch bot: Get new token, update `BOT_TOKEN` in Railway `bot-dutch` service

---

## Files Reference

- `scripts/import_to_railway.py` - MySQL to PostgreSQL import script (needs fix)
- `scripts/migrate_data.py` - Alternative migration script (direct MySQL connection)
- `scripts/run_reminders.py` - Daily reminder cron service
- `scripts/decommission_php.sh` - PHP shutdown script
- `alembic/versions/001_initial_schema.py` - Database schema

---

## To Resume This Work

```bash
cd /Users/kirill.smelov/PycharmProjects/word_learn
cat HANDOFF.md
# Then tell Claude: "Continue from HANDOFF.md - fix Dutch import and complete deployment"
```
