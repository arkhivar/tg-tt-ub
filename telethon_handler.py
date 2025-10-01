from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.errors import FloodWaitError, ChatAdminRequiredError
import time

def sort_topics(client, chat_id, sort_status, add_log):
    add_log(f"Resolving chat entity: {chat_id}")
    
    try:
        channel = client.get_entity(chat_id)
    except Exception as e:
        raise Exception(f"Failed to resolve chat: {str(e)}")
    
    add_log(f"Fetching topics from chat: {chat_id}")
    
    all_topics = []
    offset_date = None
    offset_id = 0
    offset_topic = 0
    
    while True:
        try:
            result = client(GetForumTopicsRequest(
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
            
            if len(result.topics) < 100:
                break
            
            last_topic = result.topics[-1]
            offset_topic = last_topic.id
            offset_id = last_topic.id
            
        except ChatAdminRequiredError:
            raise Exception("Bot needs admin rights or this is not a forum group")
        except FloodWaitError as e:
            wait_time = e.seconds
            add_log(f"Rate limited. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            continue
        except Exception as e:
            raise Exception(f"Failed to fetch topics: {str(e)}")
    
    if not all_topics:
        raise Exception("No topics found in this chat")
    
    add_log(f"Total topics fetched: {len(all_topics)}")
    
    sorted_topics = sorted(
        all_topics,
        key=lambda t: t.icon_emoji_id if hasattr(t, 'icon_emoji_id') and t.icon_emoji_id else 0
    )
    
    add_log("Topics sorted by emoji ID")
    sort_status["total"] = len(sorted_topics)
    
    for idx, topic in enumerate(sorted_topics):
        try:
            client.send_message(
                channel,
                ".",
                reply_to=topic.top_message
            )
            
            sort_status["progress"] = idx + 1
            add_log(f"Sent message to topic {topic.id} ({idx + 1}/{len(sorted_topics)})")
            
            if idx < len(sorted_topics) - 1:
                time.sleep(3)
                
        except FloodWaitError as e:
            wait_time = e.seconds
            add_log(f"Rate limited. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            
            client.send_message(
                channel,
                ".",
                reply_to=topic.top_message
            )
            sort_status["progress"] = idx + 1
            
            if idx < len(sorted_topics) - 1:
                time.sleep(3)
        except Exception as e:
            add_log(f"Error sending to topic {topic.id}: {str(e)}")
            continue
