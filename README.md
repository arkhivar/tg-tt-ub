
# Telegram Topic Sorter

A Flask-based web application that uses Telegram userbot functionality (via Telethon) to sort forum topics in Telegram groups. This tool allows you to organize forum topics by emoji icons, alphabetically, or in a custom order.

## Features

- **Multiple Sorting Methods**:
  - Sort by emoji icon ID (numeric)
  - Alphabetical sorting by topic title
  - Custom order (drag-and-drop emoji sorting)
- **Skip Pinned Topics**: Option to exclude pinned topics from sorting
- **Custom Sort Messages**: Configure the message sent to each topic during sorting
- **Real-time Progress**: Live updates and activity logs during sorting operations
- **Web-based Authentication**: Secure login flow for Telegram userbot

## Architecture Overview

### Technology Stack
- **Backend**: Flask (Python)
- **Telegram Client**: Telethon (userbot mode with sync wrapper)
- **Frontend**: Vanilla JavaScript, HTML, CSS
- **Threading**: Background worker thread for non-blocking operations

### Key Components

1. **Authentication System**: Two-stage authentication with session persistence
2. **Background Task Queue**: Non-blocking sort operations using Python's `queue.Queue`
3. **Real-time Updates**: Client-side polling for progress and logs
4. **Dedicated Telethon Thread**: Separate event loop for Telegram operations to avoid blocking Flask

## Setup Instructions

### Prerequisites
- Python 3.8+
- Telegram API credentials (API_ID and API_HASH from [my.telegram.org](https://my.telegram.org))
- A Telegram account

### Environment Variables

Set these in Replit Secrets or your local `.env` file:

```
API_ID=your_api_id_here
API_HASH=your_api_hash_here
PHONE_NUMBER=your_phone_number_with_country_code
SESSION_SECRET=random_secret_for_flask_sessions (optional, auto-generated)
```

### Installation

1. Clone this repository
2. Install dependencies (handled automatically on Replit, or use `pip install -r requirements.txt` locally)
3. Set environment variables
4. Run `python main.py`
5. Navigate to the web interface and authenticate with your Telegram account

## Usage

1. **Authenticate**: Enter the verification code sent to your Telegram app
2. **Select Group**: Enter the chat ID, @username, group name, or invite link
3. **Choose Sort Method**:
   - **Emoji**: Sorts by numeric emoji icon ID
   - **Alphabetical**: Sorts by topic title
   - **Custom**: Drag emojis to create your preferred order
4. **Configure Options**:
   - Skip pinned topics (recommended)
   - Custom sort message (default: ".")
5. **Start Sort**: The app will post messages in each topic to rearrange them

## Important Technical Notes

### Critical Telethon Session Parameters

For stable session persistence, these TelegramClient parameters are **required** (discovered through troubleshooting):

```python
client = TelegramClient(
    'session', 
    api_id, 
    api_hash,
    device_model='Desktop',      # Required
    app_version='1.0',           # Required
    lang_code='en',              # Required
    system_lang_code='en'        # Required
)
```

Without these, you may encounter "key not registered" errors and session crashes.

### Data Type Gotchas

**Critical**: Telethon uses Python `int` for IDs, but JSON serialization converts them to strings. Always cast back to `int()` when comparing:

```python
# ❌ WRONG
emoji_priority = {emoji_id: idx for idx, emoji_id in enumerate(custom_emoji_order)}

# ✅ CORRECT
emoji_priority = {int(emoji_id): idx for idx, emoji_id in enumerate(custom_emoji_order)}
```

### Forum Topics Pagination

When paginating through forum topics:

1. **Deduplicate by topic ID** - Telegram can return duplicates across pages
2. **Extract offset_date from messages array** - Not from the topic object:

```python
last_topic = result.topics[-1]
offset_topic = last_topic.id
offset_id = last_topic.top_message or 0
message_dates = {m.id: m.date for m in result.messages}
offset_date = message_dates.get(offset_id, 0)  # Critical!
```

## File Structure

```
├── main.py                    # Flask app and routing
├── telethon_handler.py        # Telegram operations (sorting, fetching)
├── templates/
│   ├── index.html            # Main UI
│   ├── login.html            # Login form (unused - integrated into index)
│   └── error.html            # Error page
├── static/
│   ├── app.js                # Frontend logic
│   └── style.css             # Styling
├── session.session           # Telethon session file (auto-generated)
└── replit.md                 # Replit-specific documentation
```

## Known Limitations

- Single worker thread (no concurrent sorts)
- No persistence of task queue across restarts
- Rate limiting handled via FloodWaitError catching
- Requires group admin permissions for some operations

## Future Enhancements (from Assistant conversations)

### "Chat with a Chat" Feature
A planned feature to enable semantic search across Telegram group messages:

**Concept**: Use AI embeddings (via Qdrant vector database) to search conversation history with natural language queries like "What did we discuss about the physics exam last month?"

**Proposed Architecture**:
1. **Data Collection**: Telethon scrapes messages from selected groups (text + media metadata)
2. **Embedding Generation**: DeepSeek API (cloud) generates embeddings for message chunks
3. **Vector Storage**: Self-hosted Qdrant instance (local machine with sufficient storage)
4. **Search Interface**: Additional tab in existing UI for conversational search

**Technical Stack**:
- DeepSeek API for embeddings (cost-effective cloud option)
- Self-hosted Qdrant via Easypanel (one-click install)
- OCR integration for image/screenshot search (Tesseract/EasyOCR)
- CLIP embeddings for visual search

**Storage Requirements**: Moderate (embeddings are compact, ~few GB for large groups)

**Status**: Conceptual - foundation already exists in this codebase, would extend with new route and Qdrant integration.

## Troubleshooting

### Session Crashes
- Ensure all TelegramClient parameters are set (see Critical Telethon Session Parameters)
- Delete `session.session` and re-authenticate if issues persist

### Duplicate Topics
- Check deduplication logic in `telethon_handler.py`
- Ensure both emoji fetching and sorting use identical pagination

### Rate Limiting
- App automatically handles Telegram rate limits with retry logic
- Check activity logs for "Flood wait" messages

## Contributing

When extending this project:
1. Maintain consistent deduplication logic across all Telegram operations
2. Always cast Telethon IDs to `int()` before comparisons
3. Use the existing background worker pattern for long-running operations
4. Add detailed logging for debugging Telethon operations

## License

This project is provided as-is for personal use.

## Acknowledgments

Built with Flask, Telethon, and hosted on Replit. Special thanks to the Telethon community for session stability guidance.

---

**Migration Note**: This project was developed with extensive AI assistance. Key architectural decisions and troubleshooting insights are documented in this README and `replit.md`. The "Chat with a Chat" feature represents a planned evolution based on user requirements for semantic search capabilities.
