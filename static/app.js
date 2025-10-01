let statusInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('startBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const chatIdInput = document.getElementById('chatId');
    const progressCard = document.getElementById('progressCard');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const currentChat = document.getElementById('currentChat');
    const statusText = document.getElementById('statusText');
    const logContainer = document.getElementById('logContainer');

    startBtn.addEventListener('click', startSort);
    logoutBtn.addEventListener('click', logout);

    function startSort() {
        const chatId = chatIdInput.value.trim();
        
        if (!chatId) {
            alert('Please enter a chat ID or username');
            return;
        }

        startBtn.disabled = true;
        startBtn.textContent = 'Starting...';

        fetch('/start_sort', {
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
                window.location.href = '/login';
            } else {
                alert('Logout failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            alert('Error: ' + error.message);
        });
    }
});
