from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
import os
import queue
import threading
import time
import asyncio
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', os.urandom(24))

api_id = os.environ.get('API_ID')
api_hash = os.environ.get('API_HASH')
phone = os.environ.get('PHONE_NUMBER')

client = None
telethon_loop = None
last_code_request_time = 0
CODE_REQUEST_COOLDOWN = 60

def run_async_in_telethon_thread(coro):
    """Run an async coroutine in the Telethon thread's event loop"""
    if telethon_loop is None:
        raise RuntimeError("Telethon loop not initialized")
    future = asyncio.run_coroutine_threadsafe(coro, telethon_loop)
    return future.result(timeout=30)

def init_telethon():
    """Initialize Telethon in a dedicated thread with its own event loop"""
    global client, telethon_loop
    
    if not api_id or not api_hash:
        return
    
    old_umask = os.umask(0o000)
    
    telethon_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(telethon_loop)
    
    client = TelegramClient(
        'session', 
        int(api_id), 
        api_hash, 
        loop=telethon_loop,
        device_model='Desktop',
        app_version='1.0',
        lang_code='en',
        system_lang_code='en'
    )
    
    os.umask(old_umask)
    
    async def start():
        await client.connect()
        print("Telethon client connected")
    
    telethon_loop.run_until_complete(start())
    telethon_loop.run_forever()

telethon_thread = threading.Thread(target=init_telethon, daemon=True)
telethon_thread.start()
time.sleep(2)

task_queue = queue.Queue()
sort_status = {
    "running": False,
    "current_chat": None,
    "progress": 0,
    "total": 0,
    "error": None,
    "logs": []
}

def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    sort_status["logs"].append(f"[{timestamp}] {message}")
    if len(sort_status["logs"]) > 50:
        sort_status["logs"] = sort_status["logs"][-50:]

def background_worker():
    while True:
        task = task_queue.get()
        if task is None:
            break
        
        try:
            chat_id = task['chat_id']
            sort_by = task.get('sort_by', 'emoji')
            sort_order = task.get('sort_order', 'ascending')
            skip_pinned = task.get('skip_pinned', True)
            custom_emoji_order = task.get('custom_emoji_order')
            custom_message = task.get('custom_message', '.')
            
            sort_status["running"] = True
            sort_status["current_chat"] = chat_id
            sort_status["progress"] = 0
            sort_status["total"] = 0
            sort_status["error"] = None
            
            add_log(f"Starting sort for chat: {chat_id}")
            add_log(f"Sort method: {sort_by}, Order: {sort_order}")
            if skip_pinned:
                add_log("Pinned topics will be skipped")
            if custom_emoji_order:
                add_log(f"Using custom emoji order with {len(custom_emoji_order)} emojis")
            add_log(f"Using message: '{custom_message}'")
            
            from telethon_handler import sort_topics
            run_async_in_telethon_thread(sort_topics(client, chat_id, sort_status, add_log, sort_by, sort_order, skip_pinned, custom_emoji_order, custom_message))
            
            add_log("Sort completed successfully!")
            
        except Exception as e:
            sort_status["error"] = str(e)
            add_log(f"Error: {str(e)}")
        finally:
            sort_status["running"] = False
            task_queue.task_done()

worker = threading.Thread(target=background_worker, daemon=True)
worker.start()

@app.route('/')
def index():
    if not client:
        return render_template('error.html', error="Missing API credentials. Please set API_ID, API_HASH, and PHONE_NUMBER in Replit Secrets.")
    
    try:
        async def check_auth():
            return await client.is_user_authorized()
        
        is_authorized = run_async_in_telethon_thread(check_auth())
        
        if not is_authorized and 'phone_code_hash' not in session:
            try:
                async def send_code():
                    return await client.send_code_request(phone)
                
                sent_code = run_async_in_telethon_thread(send_code())
                session['phone_code_hash'] = sent_code.phone_code_hash
            except Exception as e:
                print(f"Failed to send code: {e}")
    except Exception as e:
        print(f"Auth check error: {e}")
    
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    if not client:
        return jsonify({"error": "Client not initialized"}), 500
    
    code = request.form.get('code')
    phone_code_hash = session.get('phone_code_hash')
    
    if not code:
        return jsonify({"error": "Please enter the verification code"}), 400
    
    try:
        async def do_sign_in():
            result = await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            if os.path.exists('session.session'):
                os.chmod('session.session', 0o666)
            return result
        
        run_async_in_telethon_thread(do_sign_in())
        session.pop('phone_code_hash', None)
        return jsonify({"status": "success"})
    except PhoneCodeInvalidError:
        return jsonify({"error": "Invalid code. Please try again."}), 400
    except SessionPasswordNeededError:
        return jsonify({"error": "2FA is enabled. Please disable it temporarily."}), 400
    except Exception as e:
        return jsonify({"error": f"Login error: {str(e)}"}), 500

@app.route('/fetch_emojis', methods=['POST'])
def fetch_emojis():
    if not client:
        return jsonify({"error": "Client not initialized. Please check API credentials."}), 500
    
    if not os.path.exists('session.session'):
        return jsonify({"error": "Not authorized. Please login first."}), 401
    
    data = request.json
    chat_id = data.get('chat_id')
    
    if not chat_id:
        return jsonify({"error": "Chat ID is required"}), 400
    
    try:
        from telethon_handler import fetch_emoji_icons
        emoji_list = run_async_in_telethon_thread(fetch_emoji_icons(client, chat_id, add_log))
        return jsonify({"emojis": emoji_list})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/start_sort', methods=['POST'])
def start_sort():
    if not client:
        return jsonify({"error": "Client not initialized. Please check API credentials."}), 500
    
    if not os.path.exists('session.session'):
        return jsonify({"error": "Not authorized. Please login first."}), 401
    
    data = request.json
    chat_id = data.get('chat_id')
    sort_by = data.get('sort_by', 'emoji')
    sort_order = data.get('sort_order', 'ascending')
    skip_pinned = data.get('skip_pinned', True)
    custom_emoji_order = data.get('custom_emoji_order')  # List of emoji IDs in desired order
    custom_message = data.get('custom_message', '.')  # Custom message for sorting
    
    if not chat_id:
        return jsonify({"error": "Chat ID is required"}), 400
    
    if sort_by not in ['emoji', 'alphabetical', 'custom']:
        return jsonify({"error": "Invalid sort_by value. Must be 'emoji', 'alphabetical', or 'custom'"}), 400
    
    if sort_order not in ['ascending', 'descending']:
        return jsonify({"error": "Invalid sort_order value. Must be 'ascending' or 'descending'"}), 400
    
    if sort_by == 'custom' and not custom_emoji_order:
        return jsonify({"error": "custom_emoji_order is required when sort_by is 'custom'"}), 400
    
    if sort_status["running"]:
        return jsonify({"error": "A sort operation is already running"}), 400
    
    task_queue.put({
        'chat_id': chat_id,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'skip_pinned': skip_pinned,
        'custom_emoji_order': custom_emoji_order,
        'custom_message': custom_message
    })
    return jsonify({"status": "queued", "message": "Sort operation started"})

@app.route('/status')
def status():
    return jsonify(sort_status)

@app.route('/auth_status')
def auth_status():
    if not client:
        return jsonify({"authorized": False, "error": "Client not initialized"})
    
    try:
        async def check_auth():
            if not await client.is_user_authorized():
                return None
            me = await client.get_me()
            return {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone
            }
        
        user_info = run_async_in_telethon_thread(check_auth())
        
        if user_info:
            return jsonify({
                "authorized": True,
                "user": user_info
            })
        else:
            return jsonify({"authorized": False})
    except Exception as e:
        return jsonify({"authorized": False, "error": str(e)})

@app.route('/request_code', methods=['POST'])
def request_code():
    global last_code_request_time
    
    if not client:
        return jsonify({"error": "Client not initialized"}), 500
    
    current_time = time.time()
    time_since_last_request = current_time - last_code_request_time
    
    if time_since_last_request < CODE_REQUEST_COOLDOWN:
        remaining = int(CODE_REQUEST_COOLDOWN - time_since_last_request)
        return jsonify({
            "error": f"Please wait {remaining} seconds before requesting another code",
            "cooldown_remaining": remaining
        }), 429
    
    try:
        async def send_code():
            return await client.send_code_request(phone)
        
        sent_code = run_async_in_telethon_thread(send_code())
        session['phone_code_hash'] = sent_code.phone_code_hash
        last_code_request_time = current_time
        
        return jsonify({
            "status": "success",
            "message": "Verification code sent to your Telegram app"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to send code: {str(e)}"}), 500

@app.route('/logout', methods=['POST'])
def logout():
    if sort_status["running"]:
        return jsonify({"error": "Cannot logout while a sort operation is running"}), 400
    
    try:
        async def do_logout():
            await client.log_out()
        
        run_async_in_telethon_thread(do_logout())
        
        if os.path.exists('session.session'):
            os.remove('session.session')
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
