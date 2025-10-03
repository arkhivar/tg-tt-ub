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
            sort_status["running"] = True
            sort_status["current_chat"] = chat_id
            sort_status["progress"] = 0
            sort_status["total"] = 0
            sort_status["error"] = None
            
            add_log(f"Starting sort for chat: {chat_id}")
            
            from telethon_handler import sort_topics
            run_async_in_telethon_thread(sort_topics(client, chat_id, sort_status, add_log))
            
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
    
    if not os.path.exists('session.session'):
        return redirect(url_for('login'))
    
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not client:
        return render_template('error.html', error="Missing API credentials")
    
    if request.method == 'POST':
        code = request.form.get('code')
        phone_code_hash = session.get('phone_code_hash')
        
        if not code:
            return render_template('login.html', error="Please enter the verification code")
        
        try:
            async def do_sign_in():
                return await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            
            run_async_in_telethon_thread(do_sign_in())
            session.pop('phone_code_hash', None)
            return redirect(url_for('index'))
        except PhoneCodeInvalidError:
            return render_template('login.html', error="Invalid code. Please try again.")
        except SessionPasswordNeededError:
            return render_template('login.html', error="2FA is enabled. Please disable it temporarily or contact support.")
        except Exception as e:
            return render_template('login.html', error=f"Login error: {str(e)}")
    
    if os.path.exists('session.session'):
        return redirect(url_for('index'))
    
    try:
        async def send_code():
            return await client.send_code_request(phone)
        
        sent_code = run_async_in_telethon_thread(send_code())
        session['phone_code_hash'] = sent_code.phone_code_hash
    except Exception as e:
        return render_template('error.html', error=f"Failed to send code: {str(e)}")
    
    return render_template('login.html')

@app.route('/start_sort', methods=['POST'])
def start_sort():
    if not client:
        return jsonify({"error": "Client not initialized. Please check API credentials."}), 500
    
    if not os.path.exists('session.session'):
        return jsonify({"error": "Not authorized. Please login first."}), 401
    
    data = request.json
    chat_id = data.get('chat_id')
    
    if not chat_id:
        return jsonify({"error": "Chat ID is required"}), 400
    
    if sort_status["running"]:
        return jsonify({"error": "A sort operation is already running"}), 400
    
    task_queue.put({'chat_id': chat_id})
    return jsonify({"status": "queued", "message": "Sort operation started"})

@app.route('/status')
def status():
    return jsonify(sort_status)

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
