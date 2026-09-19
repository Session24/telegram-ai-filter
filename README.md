# Telegram AI Filter

Personal AI-powered Telegram post filter. Analyzes posts from your Telegram channels using AI and shows you only the useful ones.

## What It Does

- Connects to Telegram channels via your user account (Telethon)
- Analyzes every new post using an OpenAI-compatible AI API
- Determines if a post is useful **for you personally**
- Classifies posts by category, content type, and importance
- Sends useful posts to your Telegram bot with feedback buttons
- Organizes posts into folders (system and custom)
- Records your feedback (useful / not useful) — automatic learning from feedback is planned but not yet implemented

## Architecture

```
telegram-ai-filter/
├── src/
│   └── telegram_ai_filter/
│       ├── ai/                          # AI provider abstraction
│       │   ├── provider.py              # Abstract base class
│       │   ├── openai_compatible.py     # OpenAI-compatible implementation
│       │   └── schemas.py              # PostAnalysis dataclass
│       ├── config/                      # Configuration
│       │   ├── settings.py             # .env loading
│       │   └── prompts.py             # AI prompt templates
│       ├── database/                    # SQLAlchemy models + repositories
│       │   ├── models.py               # ORM models
│       │   ├── engine.py               # Async engine setup
│       │   └── repositories/           # Data access layer
│       ├── telegram/                    # Telegram integration
│       │   ├── channel_reader.py       # Telethon channel reader
│       │   └── bot.py                  # python-telegram-bot UI
│       ├── services/                    # Business logic
│       │   ├── user_service.py
│       │   ├── analysis_service.py
│       │   ├── folder_service.py
│       │   └── stats_service.py
│       └── app.py                      # Main application entry point
├── tests/                              # Test suite
├── data/                               # SQLite database (gitignored)
├── logs/                               # Application logs (gitignored)
├── .env.example                        # Configuration template
├── pyproject.toml                      # Project metadata
├── requirements.txt                    # Dependencies
├── Dockerfile                          # Docker support
└── docker-compose.yml                  # Docker Compose config
```

## Requirements

- Python 3.11+
- Telegram Bot Token (from @BotFather)
- Telegram API credentials (from my.telegram.org)
- AI API endpoint (OpenAI, NVIDIA, OpenRouter, LM Studio, etc.)

## Installation

```bash
# Clone the repository
git clone https://github.com/Session24/telegram-ai-filter.git
cd telegram-ai-filter

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Copy configuration
cp .env.example .env
```

## Configuration

Edit `.env` with your values:

### Telegram Credentials

1. Go to https://my.telegram.org
2. Create an application
3. Get `API_ID` and `API_HASH`

4. Talk to @BotFather on Telegram
5. Create a bot
6. Get `BOT_TOKEN`

7. Add your bot to a channel/group or use your personal chat
8. Get `TARGET_CHAT_ID` (use @userinfobot or similar)

### AI Provider

Works with any OpenAI-compatible API:

| Provider | AI_BASE_URL | Notes |
|----------|-------------|-------|
| OpenAI | `https://api.openai.com/v1` | Requires API key |
| NVIDIA | `https://integrate.api.nvidia.com/v1` | Requires API key |
| OpenRouter | `https://openrouter.ai/api/v1` | Requires API key |
| LM Studio | `http://localhost:1234/v1` | Local, no key needed |
| Ollama | `http://localhost:11434/v1` | Local, no key needed |

```env
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=sk-your-key-here
AI_MODEL=gpt-4o-mini
```

## Running

```bash
python -m telegram_ai_filter
```

### First Run

**Step 1 — Telethon user account authorization**

On the very first launch the application will ask you to authorize your personal Telegram account via Telethon. Follow the prompts in the terminal: enter your phone number and the confirmation code you receive in Telegram. After that a `.session` file will be created and subsequent starts will not require re-authorization.

**Step 2 — Telegram bot setup**

Once Telethon is authorized, the bot starts polling. Open your Telegram bot in the Telegram app and send `/start` to create your user profile. Then:

1. Configure your interests in `/settings`
2. Add channels as sources with `/addsource @channel`

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot, create user profile |
| `/help` | Show help and usage guide |
| `/settings` | Configure interests, AI settings |
| `/folders` | View and manage post folders |
| `/sources` | List connected Telegram channels |
| `/addsource @channel` | Add a Telegram channel as a source |
| `/removesource @channel` | Remove a source channel |
| `/history` | View recent analyzed posts |
| `/stats` | View filtering statistics |

### Post Feedback

When you receive a filtered post, you can:
- 👍 Mark as useful
- 👎 Mark as not useful
- 💾 Save to "Saved" folder
- 📁 Move to a specific folder (shows folder selection keyboard)

## Docker

```bash
docker compose up -d
```

Make sure your `.env` file is configured before running.

## AI Response Schema

The AI returns structured JSON for each post:

```json
{
    "useful": true,
    "score": 87,
    "category": "FPV",
    "subcategory": "Tiny Whoop",
    "content_type": "TECHNICAL",
    "importance": "high",
    "reason": "Practical guide on Tiny Whoop rate tuning for races",
    "suggested_folder": "FPV / Tiny Whoop"
}
```

### Content Types

- `TECHNICAL` - Code, configurations, how-to
- `NEWS` - News, updates
- `TUTORIAL` - Guides, walkthroughs
- `ANNOUNCEMENT` - Official announcements
- `COMPETITION` - Events, contests
- `PRODUCT` - Reviews, recommendations
- `SALE` - Sales, discounts
- `ADVERTISEMENT` - Promotional content
- `MEME` - Humor, entertainment
- `DISCUSSION` - Questions, opinions
- `OTHER` - Unclassified

### Importance Levels

- `low` - Minor, can wait
- `medium` - Worth reading when convenient
- `high` - Should be read soon
- `critical` - Urgent

## Security

- Never commit `.env` files or Telegram session files (`*.session`)
- The application and its SQLite database run and remain entirely on your local machine
- Telegram integration uses Telegram's own infrastructure (MTProto via Telethon, Bot API via python-telegram-bot)
- Post content is sent to the AI provider you configured **only for analysis** — it is not stored by this application outside your local database
- API keys are never logged or committed

## Testing

```bash
pip install -e ".[dev]"
pytest
```

The test suite covers:
- AI response parsing and validation (16 tests)
- Database operations and deduplication (12 tests)
- Configuration and prompt building (7 tests)
- Folder selection and move operations (8 tests)
- Source management (5 tests)
- Feedback persistence (2 tests)
- User data isolation (3 tests)
- End-to-end flow (3 tests)
- Bot keyboard building and formatting (13 tests)

## Project Structure

- **AI Layer** - Provider abstraction for OpenAI-compatible APIs
- **Database** - SQLAlchemy async with SQLite
- **Telegram** - Dual library: Telethon (user client) + python-telegram-bot (bot UI)
- **Services** - Business logic isolated from I/O
- **Config** - Environment-based configuration with validation

## Current Limitations

- **SQLite only** — the database backend is SQLite. PostgreSQL support is planned but not yet implemented.
- **Self-hosted** — you must provide your own Telegram credentials and AI API key.
- **Single-user mode** — runs with a single `TARGET_CHAT_ID`. Multi-user data isolation exists in the schema but the app orchestrator uses one target chat.
- **No Daily Digest** — the `digest_enabled` setting exists but the daily digest feature is not yet implemented.
- **No Learned Preferences** — the system records your feedback but does not yet adapt filtering automatically.
- **Deterministic channel IDs** — when adding sources via `/addsource`, channel IDs are generated from a hash of the username rather than resolved through the Telegram API. This works for the MVP but may cause collisions if two different channels produce the same hash. Resolving real channel IDs via Telethon is on the roadmap.

## Roadmap

- [x] Folder selection UI for moving posts
- [x] Source management via bot commands
- [x] Feedback persistence and counting
- [x] User data isolation (schema level)
- [ ] Resolve real channel IDs via Telethon API (replace deterministic hash)
- [ ] Daily digest feature
- [ ] PostgreSQL support
- [ ] Automatic learned preferences from feedback
- [ ] Web dashboard
- [ ] Semantic search
- [ ] Image analysis (OCR)
- [ ] Multiple AI providers simultaneously
- [ ] Import/export settings
- [ ] Webhooks
- [ ] Full multi-user support

## License

MIT
