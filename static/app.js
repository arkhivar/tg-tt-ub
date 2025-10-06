let statusInterval = null;
let authInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('startBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const verifyBtn = document.getElementById('verifyBtn');
    const requestCodeBtn = document.getElementById('requestCodeBtn');
    const fetchEmojisBtn = document.getElementById('fetchEmojisBtn');
    const chatIdInput = document.getElementById('chatId');
    const sortBySelect = document.getElementById('sortBy');
    const sortOrderSelect = document.getElementById('sortOrder');
    const progressCard = document.getElementById('progressCard');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const currentChat = document.getElementById('currentChat');
    const statusText = document.getElementById('statusText');
    const logContainer = document.getElementById('logContainer');
    const statusDot = document.getElementById('statusDot');
    const statusLabel = document.getElementById('statusLabel');
    const userInfo = document.getElementById('userInfo');
    const loginForm = document.getElementById('loginForm');
    const sortCard = document.getElementById('sortCard');
    const userName = document.getElementById('userName');
    const userPhone = document.getElementById('userPhone');
    const customOrderSection = document.getElementById('customOrderSection');
    const standardSortOptions = document.getElementById('standardSortOptions');
    const emojiList = document.getElementById('emojiList');
    const sortByRadios = document.querySelectorAll('input[name="sortBy"]'); // Get all radio buttons with name 'sortBy'

    let cooldownTimer = null;
    let fetchedEmojis = [];
    let customEmojiOrder = [];

    startBtn.addEventListener('click', startSort);
    logoutBtn.addEventListener('click', logout);
    verifyBtn.addEventListener('click', verifyCode);
    requestCodeBtn.addEventListener('click', requestNewCode);
    fetchEmojisBtn.addEventListener('click', fetchEmojis);

    sortByRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            if (radio.value === 'custom' && radio.checked) {
                customOrderSection.style.display = 'block';
                standardSortOptions.style.display = 'none';
            } else if (radio.checked) {
                customOrderSection.style.display = 'none';
                standardSortOptions.style.display = 'block';
                emojiList.style.display = 'none';
            }
        });
    });

    // Initialize UI state on page load
    const checkedRadio = document.querySelector('input[name="sortBy"]:checked');
    if (checkedRadio && checkedRadio.value === 'custom') {
        customOrderSection.style.display = 'block';
        standardSortOptions.style.display = 'none';
    }

    checkAuthStatus();
    authInterval = setInterval(checkAuthStatus, 50000);

    function fetchEmojis() {
        const chatId = chatIdInput.value.trim();

        if (!chatId) {
            alert('Please enter a chat ID or username first');
            return;
        }

        fetchEmojisBtn.disabled = true;
        fetchEmojisBtn.textContent = 'Fetching...';

        fetch('/fetch_emojis', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ chat_id: chatId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Error: ' + data.error);
            } else {
                fetchedEmojis = data.emojis;
                displayEmojiList(fetchedEmojis);
                fetchEmojisBtn.textContent = '✓ Emojis Fetched';
            }
        })
        .catch(error => {
            alert('Error: ' + error.message);
            fetchEmojisBtn.disabled = false;
            fetchEmojisBtn.textContent = '1. Fetch Emoji Icons';
        });
    }

    function displayEmojiList(emojis) {
        emojiList.innerHTML = '<h3>2. Arrange Emoji Order (Drag to reorder)</h3><small>Top emojis will appear first. Uncheck to ignore.</small>';

        const listContainer = document.createElement('div');
        listContainer.id = 'emojiSortableList';
        listContainer.style.cssText = 'display: flex; flex-direction: column; gap: 8px; margin-top: 10px;';

        emojis.forEach((emoji, index) => {
            const item = document.createElement('div');
            item.className = 'emoji-item';
            item.draggable = true;
            item.dataset.emojiId = emoji.emoji_id;
            item.style.cssText = 'display: flex; align-items: center; gap: 10px; padding: 10px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; cursor: move;';

            item.innerHTML = `
                <input type="checkbox" checked class="emoji-checkbox" style="width: auto; margin: 0;">
                <span style="font-weight: bold;">ID: ${emoji.emoji_id}</span>
                <span style="flex: 1;">${emoji.example_title} (${emoji.count} topics)</span>
                <span style="color: #999;">☰</span>
            `;

            item.addEventListener('dragstart', handleDragStart);
            item.addEventListener('dragover', handleDragOver);
            item.addEventListener('drop', handleDrop);
            item.addEventListener('dragend', handleDragEnd);

            listContainer.appendChild(item);
        });

        emojiList.appendChild(listContainer);
        emojiList.style.display = 'block';
    }

    let draggedElement = null;

    function handleDragStart(e) {
        draggedElement = this;
        this.style.opacity = '0.4';
    }

    function handleDragOver(e) {
        if (e.preventDefault) {
            e.preventDefault();
        }
        return false;
    }

    function handleDrop(e) {
        if (e.stopPropagation) {
            e.stopPropagation();
        }

        if (draggedElement !== this) {
            const allItems = [...document.querySelectorAll('.emoji-item')];
            const draggedIndex = allItems.indexOf(draggedElement);
            const targetIndex = allItems.indexOf(this);

            if (draggedIndex < targetIndex) {
                this.parentNode.insertBefore(draggedElement, this.nextSibling);
            } else {
                this.parentNode.insertBefore(draggedElement, this);
            }
        }

        return false;
    }

    function handleDragEnd(e) {
        this.style.opacity = '1';
    }

    function startSort() {
        const chatId = chatIdInput.value.trim();
        const sortBy = document.querySelector('input[name="sortBy"]:checked').value; // Get the value of the checked radio button
        const sortOrder = sortOrderSelect.value;
        const skipPinned = document.getElementById('skipPinned').checked;

        if (!chatId) {
            alert('Please enter a chat ID or username');
            return;
        }

        let requestBody = { 
            chat_id: chatId,
            sort_by: sortBy,
            sort_order: sortOrder,
            skip_pinned: skipPinned
        };

        if (sortBy === 'custom') {
            const emojiItems = document.querySelectorAll('.emoji-item');
            customEmojiOrder = [];

            emojiItems.forEach(item => {
                const checkbox = item.querySelector('.emoji-checkbox');
                if (checkbox.checked) {
                    customEmojiOrder.push(parseInt(item.dataset.emojiId));
                }
            });

            if (customEmojiOrder.length === 0) {
                alert('Please select at least one emoji to include in the sort');
                return;
            }

            requestBody.custom_emoji_order = customEmojiOrder;
        }

        startBtn.disabled = true;
        startBtn.textContent = 'Starting...';

        fetch('/start_sort', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Error: ' + data.error);
                startBtn.disabled = false;
                startBtn.textContent = 'Start Sort';
            } else {
                progressCard.style.display = 'block';
                startStatusPolling();
            }
        })
        .catch(error => {
            alert('Error: ' + error.message);
            startBtn.disabled = false;
            startBtn.textContent = 'Start Sort';
        });
    }

    function startStatusPolling() {
        if (statusInterval) {
            clearInterval(statusInterval);
        }

        statusInterval = setInterval(updateStatus, 1000);
        updateStatus();
    }

    function updateStatus() {
        fetch('/status')
            .then(response => response.json())
            .then(data => {
                currentChat.textContent = data.current_chat || '-';

                if (data.running) {
                    statusText.textContent = 'Running...';
                    statusText.style.color = '#667eea';
                } else if (data.error) {
                    statusText.textContent = 'Error!';
                    statusText.style.color = '#c33';
                    stopStatusPolling();
                } else {
                    statusText.textContent = 'Completed';
                    statusText.style.color = '#5cb85c';
                    stopStatusPolling();
                }

                const progress = data.total > 0 ? (data.progress / data.total) * 100 : 0;
                progressFill.style.width = progress + '%';
                progressText.textContent = `${data.progress} / ${data.total}`;

                if (data.logs && data.logs.length > 0) {
                    logContainer.innerHTML = '';
                    data.logs.forEach(log => {
                        const logEntry = document.createElement('div');
                        logEntry.className = 'log-entry';
                        logEntry.textContent = log;
                        logContainer.appendChild(logEntry);
                    });
                    logContainer.scrollTop = logContainer.scrollHeight;
                }

                if (!data.running) {
                    startBtn.disabled = false;
                    startBtn.textContent = 'Start Sort';
                }
            })
            .catch(error => {
                console.error('Status update error:', error);
            });
    }

    function stopStatusPolling() {
        if (statusInterval) {
            clearInterval(statusInterval);
            statusInterval = null;
        }
    }

    function logout() {
        if (!confirm('Are you sure you want to logout? You will need to authenticate again.')) {
            return;
        }

        fetch('/logout', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                location.reload();
            } else {
                alert('Logout failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            alert('Error: ' + error.message);
        });
    }

    function checkAuthStatus() {
        fetch('/auth_status')
            .then(response => response.json())
            .then(data => {
                if (data.authorized) {
                    statusDot.className = 'status-dot online';
                    statusLabel.textContent = 'Connected';
                    userInfo.style.display = 'block';
                    loginForm.style.display = 'none';
                    sortCard.classList.remove('disabled');

                    const fullName = [data.user.first_name, data.user.last_name].filter(Boolean).join(' ');
                    userName.textContent = fullName || data.user.username || 'User';
                    userPhone.textContent = data.user.phone || '';

                    const initials = (data.user.first_name || data.user.username || '?')[0].toUpperCase();
                    document.getElementById('userAvatar').textContent = initials;
                } else {
                    statusDot.className = 'status-dot offline';
                    statusLabel.textContent = 'Not authenticated';
                    userInfo.style.display = 'none';
                    loginForm.style.display = 'block';
                    sortCard.classList.add('disabled');
                }
            })
            .catch(error => {
                console.error('Auth status error:', error);
                statusDot.className = 'status-dot offline';
                statusLabel.textContent = 'Error checking status';
            });
    }

    function verifyCode() {
        const code = document.getElementById('loginCode').value.trim();

        if (!code) {
            alert('Please enter the verification code');
            return;
        }

        verifyBtn.disabled = true;
        verifyBtn.textContent = 'Verifying...';

        fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: 'code=' + encodeURIComponent(code)
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Login failed: ' + data.error);
                verifyBtn.disabled = false;
                verifyBtn.textContent = 'Verify Code';
            } else {
                document.getElementById('loginCode').value = '';
                alert('Login successful!');
                checkAuthStatus();
                verifyBtn.disabled = false;
                verifyBtn.textContent = 'Verify Code';
            }
        })
        .catch(error => {
            alert('Error: ' + error.message);
            verifyBtn.disabled = false;
            verifyBtn.textContent = 'Verify Code';
        });
    }

    function requestNewCode() {
        requestCodeBtn.disabled = true;
        const originalText = requestCodeBtn.textContent;
        requestCodeBtn.textContent = 'Sending...';

        fetch('/request_code', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                if (data.cooldown_remaining) {
                    startCooldown(data.cooldown_remaining);
                } else {
                    alert(data.error);
                    requestCodeBtn.disabled = false;
                    requestCodeBtn.textContent = originalText;
                }
            } else {
                alert('New verification code sent to your Telegram app!');
                startCooldown(60);
            }
        })
        .catch(error => {
            alert('Error: ' + error.message);
            requestCodeBtn.disabled = false;
            requestCodeBtn.textContent = originalText;
        });
    }

    function startCooldown(seconds) {
        let remaining = seconds;
        requestCodeBtn.disabled = true;

        if (cooldownTimer) {
            clearInterval(cooldownTimer);
        }

        cooldownTimer = setInterval(() => {
            if (remaining <= 0) {
                clearInterval(cooldownTimer);
                cooldownTimer = null;
                requestCodeBtn.disabled = false;
                requestCodeBtn.textContent = 'Request New Code';
            } else {
                requestCodeBtn.textContent = `Wait ${remaining}s`;
                remaining--;
            }
        }, 1000);
    }
});