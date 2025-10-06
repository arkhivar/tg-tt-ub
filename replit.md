# Telegram Topic Sorter

## Overview

This is a Flask-based web application that uses a Telegram userbot (via Telethon) to sort forum topics in Telegram groups. The application operates as a userbot (authenticated with a user account, not a bot token), allowing it to interact with any Telegram group where the user has access. The core functionality fetches all forum topics from a specified group, sorts them using the selected method, and posts a message in each topic in the sorted order to rearrange them.

### Sorting Options (Oct 2025)
- **By Emoji ID**: Sorts topics by their emoji icon ID (numeric)
- **Alphabetical**: Sorts topics by their title (case-insensitive)
- **Order**: Both methods support ascending and descending order
- **Extensible Design**: Dropdown-based UI ready for additional sorting methods

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Static HTML/CSS/JavaScript**: Simple web interface with no framework dependencies
- **Real-time Status Updates**: Client-side polling mechanism to fetch sorting progress and logs
- **Responsive Design**: Mobile-friendly UI with gradient background and card-based layout
- **Single Page Application Pattern**: Multiple templates (login, index, error) for different states

### Backend Architecture
- **Flask Web Framework**: Lightweight Python web server handling HTTP requests and session management
- **Synchronous Request Handling**: Uses `telethon.sync` for synchronous Telegram operations within Flask routes
- **Background Task Processing**: Queue-based worker thread for non-blocking sort operations
  - **Problem**: Long-running Telegram operations would block HTTP responses
  - **Solution**: `queue.Queue` for task management with dedicated background worker thread
  - **Pros**: Simple implementation, no external dependencies
  - **Cons**: Single worker thread, no persistence across restarts

### Authentication & Session Management
- **Userbot Authentication Flow**: Two-stage authentication process
  1. Initial phone number-based code request
  2. Code verification via web form
- **Session Persistence**: Telethon session file (`session.session`) stored locally for reuse
  - **Problem**: Userbot requires interactive authentication
  - **Solution**: Web-based code entry form with Flask session management
  - **Pros**: One-time setup, persistent authentication
  - **Cons**: Session file must be preserved across deployments
- **Critical TelegramClient Parameters**: Required for proper session persistence (Oct 2025 fix)
  - `device_model='Desktop'`: Identifies device type to Telegram
  - `app_version='1.0'`: Application version identifier
  - `lang_code='en'`: Primary language code (ISO 639-1)
  - `system_lang_code='en'`: System language code
  - **Issue**: Without these parameters, sessions crash with "key not registered" errors
  - **Source**: Official Telethon community guidance for session stability

### Data Flow
1. User initiates sort via web interface with chat ID/username, sort method, and sort order
2. Frontend sends `sort_by` (emoji/alphabetical) and `sort_order` (ascending/descending) parameters
3. Backend validates parameters and queues task to background worker
4. Worker fetches all forum topics via Telegram API (pagination-aware)
5. Topics sorted by selected method (`icon_emoji_id` or `title`) with chosen order
6. Worker posts message to each topic in sorted order with 3-second delays
7. Progress tracked in shared status dictionary
8. Frontend polls status endpoint for real-time updates

### External Dependencies

#### Third-Party Services
- **Telegram API**: Core dependency for all userbot operations
  - Requires API_ID and API_HASH from my.telegram.org
  - Uses MTProto protocol via Telethon library

#### Python Libraries
- **Flask**: Web framework for HTTP server and routing
- **Telethon**: Telegram client library with sync wrapper
  - Version constraint: Must support `telethon.sync` for synchronous operations
  - Key methods: `GetForumTopicsRequest` for forum topic retrieval

#### Environment Variables (via Replit Secrets)
- **API_ID**: Telegram API application ID
- **API_HASH**: Telegram API application hash
- **PHONE_NUMBER**: User's Telegram phone number for authentication
- **SESSION_SECRET**: Flask session encryption key (optional, auto-generated)

#### Error Handling Strategy
- **FloodWaitError**: Automatic retry with exponential backoff
- **ChatAdminRequiredError**: Clear error message for permission issues
- **Session Errors**: Redirect to login flow for re-authentication

#### Rate Limiting Considerations
- Pagination limit: 100 topics per request
- Automatic handling of Telegram rate limits via FloodWaitError catching
- Log tracking for transparency during waits
## Troubleshooting & Common Pitfalls

### Data Type Mismatches with Telethon (Critical!)

**The Problem**: Telethon uses Python integers for IDs (like `emoji_id`), but JSON serialization converts these to strings when sending data to the frontend. When the frontend sends them back, they remain strings, causing comparison failures.

**Real-World Example**:
```python
# Telethon returns: emoji_id = 5231427706864328274 (int)
# JSON serialization converts to: "5231427706864328274" (str)
# Frontend sends back: "5231427706864328274" (str)
# Comparison fails: 5231427706864328274 == "5231427706864328274" → False
```

**The Solution**: Always convert emoji IDs to integers when comparing:
```python
# ❌ WRONG - String vs Integer comparison
emoji_priority = {emoji_id: idx for idx, emoji_id in enumerate(custom_emoji_order)}

# ✅ CORRECT - Convert to int first
emoji_priority = {int(emoji_id): idx for idx, emoji_id in enumerate(custom_emoji_order)}
```

**Why This Matters**: Telegram uses massive 64-bit integers for unique IDs. JavaScript's JSON.stringify() and Python's json.dumps() preserve these as strings to prevent precision loss. Always cast them back to `int()` before comparisons.

### Forum Topics Pagination & Deduplication

**The Duplicate Topic Problem**: When paginating through forum topics with `GetForumTopicsRequest`, Telegram's API can sometimes return duplicate topics across pages, especially in large groups or when topics are being actively modified.

**The Solution**: Always deduplicate topics by ID:
```python
# After fetching all topics from pagination
seen_ids = set()
unique_topics = []
for topic in all_topics:
    if topic.id not in seen_ids:
        seen_ids.add(topic.id)
        unique_topics.append(topic)

if len(all_topics) != len(unique_topics):
    add_log(f"Removed {len(all_topics) - len(unique_topics)} duplicate topics")

all_topics = unique_topics
```

**Critical Pagination Parameters**: For reliable pagination with forum topics:
- `offset_topic`: ID of the last topic from previous page
- `offset_id`: The `top_message` ID from the last topic (NOT the topic ID)
- `offset_date`: The **message date** from the messages array, keyed by `offset_id`

```python
# ✅ CORRECT pagination setup
last_topic = result.topics[-1]
offset_topic = last_topic.id
offset_id = last_topic.top_message or 0

# Get date from messages array (CRITICAL!)
message_dates = {m.id: m.date for m in result.messages}
offset_date = message_dates.get(offset_id, 0)
```

**Why This Matters**: The `offset_date` must come from the actual message object in `result.messages`, not from the topic object. Topics don't have dates, but their top messages do.

### Consistency Between Operations

**The Count Mismatch Problem**: If you fetch data in one operation and process it in another, ensure both use identical deduplication logic. 

**Example**: The emoji fetching function and the sorting function must both:
1. Use the same pagination logic
2. Apply the same deduplication by topic ID
3. Filter topics the same way (e.g., pinned vs unpinned)

Otherwise, you'll see mismatches like "5 topics found" in emoji fetch but only "3 topics sorted" in the actual sort.

### Best Practices Summary

1. **Always cast Telethon IDs to `int()` when comparing** (emoji_id, topic_id, message_id, etc.)
2. **Deduplicate topics by ID** after pagination completes
3. **Extract offset_date from the messages array**, not from topic objects
4. **Apply identical logic** across different functions that process the same data
5. **Log everything** - Telethon operations can be unpredictable, detailed logs save debugging time

These patterns apply to all Telethon operations with large datasets, not just forum topics. Keep them in mind when building Telegram automation tools!
