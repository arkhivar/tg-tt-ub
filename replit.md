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