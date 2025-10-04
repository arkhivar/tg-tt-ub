from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
from telethon.errors import FloodWaitError, ChatAdminRequiredError
import asyncio
import re

async def sort_topics(client, chat_id, sort_status, add_log, sort_by='emoji', sort_order='ascending'):
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
    offset_date = None
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
            
            last_topic = result.topics[-1]
            offset_topic = last_topic.id
            offset_id = last_topic.top_message or 0
            
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
    
    add_log(f"Total topics fetched: {len(all_topics)}")
    
    if sort_by == 'alphabetical':
        sorted_topics = sorted(
            all_topics,
            key=lambda t: t.title.lower() if hasattr(t, 'title') and t.title else '',
            reverse=(sort_order == 'descending')
        )
        add_log(f"Topics sorted alphabetically ({sort_order})")
    else:
        sorted_topics = sorted(
            all_topics,
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
                reply_to=topic.top_message,
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
                reply_to=topic.top_message,
                silent=True
            )
            sort_status["progress"] = idx + 1
            
            if idx < len(sorted_topics) - 1:
                await asyncio.sleep(3)
        except Exception as e:
            add_log(f"Error sending to topic {topic.id}: {str(e)}")
            continue
