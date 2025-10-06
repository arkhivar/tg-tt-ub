from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
from telethon.errors import FloodWaitError, ChatAdminRequiredError
import asyncio
import re

async def fetch_emoji_icons(client, chat_id, add_log):
    """Fetch all unique emoji icons from forum topics"""
    add_log(f"Fetching emoji icons from chat: {chat_id}")
    
    channel = None
    
    # Check if it's an invite link
    invite_hash = None
    if 't.me/' in str(chat_id):
        if '/joinchat/' in chat_id:
            invite_hash = chat_id.split('/joinchat/')[-1]
        elif '/+' in chat_id or 't.me/+' in chat_id:
            invite_hash = chat_id.split('+')[-1]
    
    if invite_hash:
        try:
            add_log(f"Detected invite link, checking chat...")
            check_result = await client(CheckChatInviteRequest(invite_hash))
            
            if hasattr(check_result, 'chat'):
                channel = check_result.chat
                add_log(f"Found chat from invite: {channel.title}")
            else:
                raise Exception("You need to join this group first. Please join via Telegram and try again.")
        except Exception as e:
            raise Exception(f"Failed to resolve invite link: {str(e)}")
    else:
        try:
            channel = await client.get_entity(chat_id)
        except Exception as first_error:
            try:
                add_log("Entity not in cache, searching all dialogs...")
                dialog_count = 0
                async for dialog in client.iter_dialogs():
                    dialog_count += 1
                    if (str(chat_id).lower() in dialog.name.lower() or 
                        str(dialog.id) == str(chat_id)):
                        channel = dialog.entity
                        add_log(f"Found chat: {dialog.name}")
                        break
                
                if not channel:
                    add_log(f"Searched {dialog_count} dialogs, retrying by ID...")
                    channel = await client.get_entity(chat_id)
            except Exception as e:
                raise Exception(f"Failed to resolve chat: {str(e)}. Try using the group's @username or invite link.")
    
    MAX_TOPICS = 10000
    all_topics = []
    offset_date = 0
    offset_id = 0
    offset_topic = 0
    
    while True:
        try:
            result = await client(GetForumTopicsRequest(
                channel=channel,
                offset_date=offset_date,
                offset_id=offset_id,
                offset_topic=offset_topic,
                limit=100
            ))
            
            if not result.topics:
                break
            
            all_topics.extend(result.topics)
            add_log(f"Fetched {len(result.topics)} topics (total: {len(all_topics)})")
            
            if len(all_topics) >= MAX_TOPICS:
                add_log(f"Reached maximum topic limit ({MAX_TOPICS}). Stopping fetch.")
                break
            
            if len(result.topics) < 100:
                break
            
            last_topic = result.topics[-1]
            offset_topic = last_topic.id
            offset_id = last_topic.top_message or 0
            
            message_dates = {m.id: m.date for m in result.messages}
            offset_date = message_dates.get(offset_id, 0)
            
            if not last_topic.top_message:
                add_log("Warning: Last topic has no top_message, stopping pagination")
                break
            
        except ChatAdminRequiredError:
            raise Exception("Bot needs admin rights or this is not a forum group")
        except FloodWaitError as e:
            wait_time = e.seconds
            add_log(f"Rate limited. Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            continue
        except Exception as e:
            raise Exception(f"Failed to fetch topics: {str(e)}")
    
    if not all_topics:
        raise Exception("No topics found in this chat")
    
    # Extract unique emoji icons
    emoji_map = {}  # emoji_id -> {emoji_id, count, example_title}
    
    for topic in all_topics:
        if hasattr(topic, 'icon_emoji_id') and topic.icon_emoji_id:
            emoji_id = topic.icon_emoji_id
            if emoji_id not in emoji_map:
                emoji_map[emoji_id] = {
                    'emoji_id': emoji_id,
                    'count': 0,
                    'example_title': topic.title if hasattr(topic, 'title') else 'Untitled'
                }
            emoji_map[emoji_id]['count'] += 1
    
    emoji_list = list(emoji_map.values())
    emoji_list.sort(key=lambda x: x['emoji_id'])  # Sort by emoji ID
    
    add_log(f"Found {len(emoji_list)} unique emoji icons")
    return emoji_list

async def sort_topics(client, chat_id, sort_status, add_log, sort_by='emoji', sort_order='ascending', skip_pinned=True, custom_emoji_order=None):
    add_log(f"Resolving chat entity: {chat_id}")
    
    channel = None
    
    # Check if it's an invite link
    invite_hash = None
    if 't.me/' in str(chat_id):
        if '/joinchat/' in chat_id:
            invite_hash = chat_id.split('/joinchat/')[-1]
        elif '/+' in chat_id or 't.me/+' in chat_id:
            invite_hash = chat_id.split('+')[-1]
    
    if invite_hash:
        try:
            add_log(f"Detected invite link, checking chat...")
            check_result = await client(CheckChatInviteRequest(invite_hash))
            
            # If already a member
            if hasattr(check_result, 'chat'):
                channel = check_result.chat
                add_log(f"Found chat from invite: {channel.title}")
            else:
                raise Exception("You need to join this group first. Please join via Telegram and try again.")
        except Exception as e:
            raise Exception(f"Failed to resolve invite link: {str(e)}")
    else:
        # Try direct resolution first
        try:
            channel = await client.get_entity(chat_id)
        except Exception as first_error:
            try:
                add_log("Entity not in cache, searching all dialogs...")
                dialog_count = 0
                # Try to find by name/title
                async for dialog in client.iter_dialogs():
                    dialog_count += 1
                    # Check if chat_id matches dialog name or ID
                    if (str(chat_id).lower() in dialog.name.lower() or 
                        str(dialog.id) == str(chat_id)):
                        channel = dialog.entity
                        add_log(f"Found chat: {dialog.name}")
                        break
                
                if not channel:
                    add_log(f"Searched {dialog_count} dialogs, retrying by ID...")
                    channel = await client.get_entity(chat_id)
            except Exception as e:
                raise Exception(f"Failed to resolve chat: {str(e)}. Try using the group's @username or invite link.")
    
    add_log(f"Fetching topics from chat: {chat_id}")
    
    # Safety limit to prevent extremely long operations
    MAX_TOPICS = 10000
    
    all_topics = []
    offset_date = 0
    offset_id = 0
    offset_topic = 0
    
    while True:
        try:
            result = await client(GetForumTopicsRequest(
                channel=channel,
                offset_date=offset_date,
                offset_id=offset_id,
                offset_topic=offset_topic,
                limit=100
            ))
            
            if not result.topics:
                break
            
            all_topics.extend(result.topics)
            add_log(f"Fetched {len(result.topics)} topics (total: {len(all_topics)})")
            
            # Safety check: stop if we exceed the maximum
            if len(all_topics) >= MAX_TOPICS:
                add_log(f"Reached maximum topic limit ({MAX_TOPICS}). Stopping fetch.")
                break
            
            if len(result.topics) < 100:
                break
            
            # Update offsets for next page based on LAST topic
            last_topic = result.topics[-1]
            offset_topic = last_topic.id
            offset_id = last_topic.top_message or 0
            
            # CRITICAL: Get the date of the top_message from the messages array
            # This is what makes pagination work correctly!
            message_dates = {m.id: m.date for m in result.messages}
            offset_date = message_dates.get(offset_id, 0)
            
            # Safety check: if top_message is None, we can't continue
            if not last_topic.top_message:
                add_log("Warning: Last topic has no top_message, stopping pagination")
                break
            
        except ChatAdminRequiredError:
            raise Exception("Bot needs admin rights or this is not a forum group")
        except FloodWaitError as e:
            wait_time = e.seconds
            add_log(f"Rate limited. Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            continue
        except Exception as e:
            raise Exception(f"Failed to fetch topics: {str(e)}")
    
    if not all_topics:
        raise Exception("No topics found in this chat")
    
    # Deduplicate topics by ID (in case pagination fetched duplicates)
    seen_ids = set()
    unique_topics = []
    for topic in all_topics:
        if topic.id not in seen_ids:
            seen_ids.add(topic.id)
            unique_topics.append(topic)
    
    if len(all_topics) != len(unique_topics):
        add_log(f"Removed {len(all_topics) - len(unique_topics)} duplicate topics")
    
    all_topics = unique_topics
    add_log(f"Total unique topics: {len(all_topics)}")
    
    # Separate pinned and non-pinned topics if skip_pinned is enabled
    if skip_pinned:
        pinned_topics = [t for t in all_topics if hasattr(t, 'pinned') and t.pinned]
        topics_to_sort = [t for t in all_topics if not (hasattr(t, 'pinned') and t.pinned)]
        
        if pinned_topics:
            add_log(f"Found {len(pinned_topics)} pinned topic(s) - will not sort these")
            add_log(f"Sorting {len(topics_to_sort)} non-pinned topics")
    else:
        topics_to_sort = all_topics
        pinned_topics = []
    
    if sort_by == 'alphabetical':
        sorted_topics = sorted(
            topics_to_sort,
            key=lambda t: t.title.lower() if hasattr(t, 'title') and t.title else '',
            reverse=(sort_order == 'descending')
        )
        add_log(f"Topics sorted alphabetically ({sort_order})")
    elif sort_by == 'custom' and custom_emoji_order:
        # Custom emoji order sorting - only include topics with checked emojis
        emoji_priority = {emoji_id: idx for idx, emoji_id in enumerate(custom_emoji_order)}
        
        add_log(f"Selected emoji IDs: {custom_emoji_order}")
        
        # Debug: Show all unique emoji IDs in topics
        topic_emoji_ids = set()
        for t in topics_to_sort:
            if hasattr(t, 'icon_emoji_id') and t.icon_emoji_id:
                topic_emoji_ids.add(t.icon_emoji_id)
        add_log(f"Found emoji IDs in topics: {sorted(list(topic_emoji_ids))}")
        
        # Filter to only include topics with emojis in the custom order
        filtered_topics = [
            t for t in topics_to_sort 
            if hasattr(t, 'icon_emoji_id') and t.icon_emoji_id in emoji_priority
        ]
        
        def get_sort_key(topic):
            emoji_id = topic.icon_emoji_id if hasattr(topic, 'icon_emoji_id') and topic.icon_emoji_id else None
            return emoji_priority.get(emoji_id, len(custom_emoji_order) + 1)
        
        sorted_topics = sorted(filtered_topics, key=get_sort_key)
        add_log(f"Topics sorted by custom emoji order ({len(sorted_topics)} topics with selected emojis)")
    else:
        sorted_topics = sorted(
            topics_to_sort,
            key=lambda t: t.icon_emoji_id if hasattr(t, 'icon_emoji_id') and t.icon_emoji_id else 0,
            reverse=(sort_order == 'descending')
        )
        add_log(f"Topics sorted by emoji ID ({sort_order})")
    
    sort_status["total"] = len(sorted_topics)
    
    for idx, topic in enumerate(sorted_topics):
        try:
            await client.send_message(
                channel,
                ".",
                reply_to=topic.id,
                silent=True
            )
            
            sort_status["progress"] = idx + 1
            add_log(f"Sent silent message to topic {topic.id} ({idx + 1}/{len(sorted_topics)})")
            
            if idx < len(sorted_topics) - 1:
                await asyncio.sleep(3)
                
        except FloodWaitError as e:
            wait_time = e.seconds
            add_log(f"Rate limited. Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            
            await client.send_message(
                channel,
                ".",
                reply_to=topic.id,
                silent=True
            )
            sort_status["progress"] = idx + 1
            
            if idx < len(sorted_topics) - 1:
                await asyncio.sleep(3)
        except Exception as e:
            add_log(f"Error sending to topic {topic.id}: {str(e)}")
            continue
