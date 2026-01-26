# Word Learner Bot - Use Cases

This document describes all use cases supported by the Word Learner Telegram bot.

## Overview

The Word Learner bot helps users learn vocabulary using spaced repetition. It supports multiple language pairs (English-Russian and Dutch-English) through separate bot instances.

## Bot Commands

### `/start` - Welcome Message
**Trigger:** User sends `/start`

**Flow:**
1. Bot sends welcome message
2. Bot displays list of all available commands with descriptions

**Response:**
```
Hello! Welcome to our bot, Here are our available commands:
/help - Help with available commands
/start - Start Command to get you started
/addWords - Add words to practice
/add - Add concrete word
/practice - Practice words
/reset - Reset current practice session
/remind - Set daily reminder
```

---

### `/add word1 word2` - Add Single Custom Word
**Trigger:** User sends `/add cat kot`

**Flow:**
1. Parse arguments: `word1` (target language), `word2` (source language)
2. Create bidirectional word entries:
   - Entry 1: `{target_lang: "cat", source_lang: "kot"}`
   - Entry 2: `{target_lang: "kot", source_lang: "cat"}`
3. Add both words to user's practice queue with stage=0
4. Confirm addition

**Response:**
```
Done! Added word to learn: cat : kot
[Practice words (N)]  <- inline button
```

---

### Direct Text `cat, kat` - Quick Add Word
**Trigger:** User sends plain text (not starting with `/`)

**Parsing Rules:**
- If text contains comma: split by comma
- If text contains exactly one space (no comma): split by space
- Otherwise: error

**Examples:**
- `cat, kat` -> ["cat", "kat"]
- `cat kat` -> ["cat", "kat"]
- `the cat, de kat` -> ["the cat", "de kat"]
- `the big cat` -> Error (multiple spaces, no comma)

**Flow:** Same as `/add` command

**Error Response:**
```
Use ',' for query with multiple whitespaces
```

---

### `/addWords` - Add Words from Database
**Trigger:** User sends `/addWords`

**Flow:**
1. Fetch 10 random words from database that user hasn't:
   - Already added to practice
   - Already skipped
2. For each word, show prompt with Learn/Skip buttons
3. User taps Learn or Skip for each word
4. Add learned words to practice queue
5. Add skipped words to skiplist
6. Show summary

**Word Selection Query:**
```sql
SELECT * FROM words
WHERE id NOT IN (
  SELECT word_id FROM word_practice WHERE chat_id = ?
  UNION
  SELECT word_id FROM word_skiplist WHERE chat_id = ?
)
ORDER BY RANDOM() LIMIT 10
```

**Prompt for each word:**
```
cat : kat
[Learn] [Skip]  <- reply keyboard
```

**Final Response:**
```
Done! Added words to learn: 7
```

---

### `/practice` - Start Practice Session
**Trigger:** User sends `/practice`

**Flow:**
1. Create or fetch today's daily pool (67-76 words)
2. Get up to 10 due words from today's pool
3. Add words to `current_practice` table
4. Trigger `/practiceWord` to show first word

**Daily Pool Logic:**
```sql
-- If no pool exists for today, create one
INSERT INTO today_practice (word_practice_id)
SELECT id FROM word_practice
WHERE chat_id = ? AND next_date <= NOW() AND deleted = FALSE
ORDER BY RANDOM() LIMIT [67-76]  -- random limit
```

**No Words Response:**
```
No words to practice!
```

---

### `/practiceWord` - Show Next Practice Word
**Trigger:** Internal (called after `/practice` or `/finish`)

**Flow:**
1. Get next word from `current_practice` table
2. If no words left:
   - Show session stats if all daily words done
   - Reset stats
3. Show word in target language with Reveal button

**Word Display:**
```
cat
[Reveal]  <- inline button with callback: "reveal {word_id}"
```

**Session Complete Response:**
```
Practiced all words!
8/10 of words were guessed correctly
[Practice more (N)]  <- inline button
```

---

### `reveal {wordId}` - Show Translation (Callback)
**Trigger:** User taps "Reveal" inline button

**Flow:**
1. Fetch word with translations
2. Show both source and target translations
3. Display action buttons

**Response:**
```
kat : cat
[Correct] [Incorrect] [Delete]  <- inline buttons
```

Callback data:
- Correct: `finish {wordId} correct`
- Incorrect: `finish {wordId} incorrect`
- Delete: `finish {wordId} delete`

---

### `finish {wordId} {action}` - Complete Word Practice (Callback)
**Trigger:** User taps Correct/Incorrect/Delete button

#### Action: `correct`
**Flow:**
1. Increment stage (max 33)
2. Calculate next review date: `today + 2^(stage-1) days` (+ rand(0,1) for stage > 1)
3. Update `word_practice` table
4. Increment session stats (correct + total)
5. Remove from `current_practice`
6. Trigger `/practiceWord`

**Response:**
```
Marked as correct!
```

#### Action: `incorrect`
**Flow:**
1. Reset stage to 1
2. Set next_date to tomorrow
3. Increment session stats (total only)
4. Remove from `current_practice`
5. Trigger `/practiceWord`

**Response:**
```
Marked as incorrect
```

#### Action: `delete`
**Flow:**
1. Set `deleted = TRUE` in `word_practice`
2. Remove from `current_practice`
3. Trigger `/practiceWord`

**Response:**
```
Deleted!
```

---

### `/remind HH:mm` - Set Daily Reminder
**Trigger:** User sends `/remind 09:00`

**Flow:**
1. Parse time in HH:mm format
2. Calculate next reminder datetime
3. Upsert into `reminders` table

**Next Reminder Logic:**
- If time is in the future today: remind today
- If time has passed today: remind tomorrow

**Response:**
```
OK, set reminder daily on 09:00. Next reminder: 15 Jan 09:00
```

---

### `/reset` - Reset Practice Session
**Trigger:** User sends `/reset`

**Flow:**
1. Delete all entries from `current_practice` for this chat
2. Confirm reset

**Response:**
```
Reset is done
```

---

## Spaced Repetition Algorithm

The bot uses a spaced repetition system based on the following formula:

| Stage | Days until next review |
|-------|------------------------|
| 0 | Same day (immediate) |
| 1 | 1 day (2^0) |
| 2 | 2-3 days (2^1 + rand(0,1)) |
| 3 | 4-5 days (2^2 + rand(0,1)) |
| ... | ... |
| N | 2^(N-1) + rand(0,1) days |
| 33 | Maximum stage (capped) |

**Formula:**
```python
def get_next_date(today: date, stage: int) -> date:
    if stage == 0:
        return today
    diff_days = 2 ** (stage - 1)
    if stage > 1:
        diff_days += random.randint(0, 1)
    return today + timedelta(days=diff_days)
```

---

## Daily Practice Pool

To prevent overwhelming users, a daily pool limits practice to 67-76 words:

1. Each day, a random subset (67-76) of due words is selected
2. Words are stored in `today_practice` table with current date
3. Practice sessions only pull from this daily pool
4. Pool resets the next day

**Why 67-76?** This provides variety while being manageable in a single day.

---

## Session Statistics

Statistics are tracked per practice session:

- **correct**: Number of words marked correct
- **total**: Total words practiced in session

Stats are shown when all words in `current_practice` are completed:
```
8/10 of words were guessed correctly
```

Stats are reset after being displayed.

---

## Data Model

### Tables

1. **words** - Vocabulary entries with translations
2. **word_practice** - User's learning progress per word
3. **word_skiplist** - Words user chose to skip during /addWords
4. **current_practice** - Active practice session words
5. **today_practice** - Daily word pool (67-76 random due words)
6. **current_practice_stats** - Session statistics (correct/total)
7. **reminders** - Daily reminder settings

---

## Multi-Bot Architecture

Two bot instances run from the same codebase:

| Bot | Languages | Database |
|-----|-----------|----------|
| Bot EN | English ↔ Russian | word_learn_en |
| Bot Dutch | Dutch ↔ English | word_learn_dutch |

Configuration via environment variables:
- `BOT_TOKEN`: Telegram bot token
- `DATABASE_URL`: PostgreSQL connection string
- `SOURCE_LANG`: Source language code (en/nl)
- `TARGET_LANG`: Target language code (ru/en)
