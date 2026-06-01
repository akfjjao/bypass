let timerInterval = null;
let timerStart = 0;

document.addEventListener("DOMContentLoaded", () => {
    // Initial fetch of history
    loadHistory();
    
    // Add enter key support to input field
    document.getElementById("short-url").addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            startBypass();
        }
    });
});

function switchTab(tabName) {
    // Deactivate all tabs
    document.querySelectorAll(".nav-tab").forEach(tab => tab.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(content => content.style.display = "none");
    
    // Activate clicked tab
    if (tabName === "bypass") {
        document.getElementById("tab-bypass").classList.add("active");
        document.getElementById("view-bypass").style.display = "block";
    } else if (tabName === "history") {
        document.getElementById("tab-history").classList.add("active");
        document.getElementById("view-history").style.display = "block";
        loadHistory();
    }
}

function startBypass() {
    const urlInput = document.getElementById("short-url");
    const url = urlInput.value.trim();
    
    if (!url) {
        alert("Please paste a URL shortener link to bypass.");
        return;
    }
    
    // Reset views
    document.getElementById("result-container").style.display = "none";
    document.getElementById("error-container").style.display = "none";
    document.getElementById("progress-container").style.display = "block";
    
    const terminal = document.getElementById("log-terminal");
    terminal.innerHTML = "";
    
    // Disable inputs
    urlInput.disabled = true;
    document.getElementById("btn-bypass").disabled = true;
    
    // Setup and start Timer
    const timerBadge = document.getElementById("elapsed-timer");
    timerStart = Date.now();
    timerBadge.innerText = "0.0s";
    
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
        const elapsed = (Date.now() - timerStart) / 1000;
        timerBadge.innerText = elapsed.toFixed(1) + "s";
    }, 100);
    
    // Initialize Web Socket Connection
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/bypass`;
    const socket = new WebSocket(wsUrl);
    
    socket.onopen = () => {
        socket.send(JSON.stringify({ url: url }));
    };
    
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === "progress") {
            appendTerminalLog(data.message, data.status);
        } else if (data.type === "result") {
            clearInterval(timerInterval);
            handleSuccess(data.result);
            socket.close();
        } else if (data.type === "error") {
            clearInterval(timerInterval);
            handleFailure(data.message);
            socket.close();
        }
    };
    
    socket.onerror = (error) => {
        clearInterval(timerInterval);
        handleFailure("Connection to bypass server encountered a terminal WebSocket error.");
        socket.close();
    };
    
    socket.onclose = () => {
        // Enable inputs
        urlInput.disabled = false;
        document.getElementById("btn-bypass").disabled = false;
    };
}

function appendTerminalLog(message, status) {
    const terminal = document.getElementById("log-terminal");
    const line = document.createElement("div");
    line.className = "log-line";
    
    const timestamp = new Date().toLocaleTimeString();
    
    let colorClass = "log-info";
    if (status === "start") colorClass = "log-start";
    else if (status === "success") colorClass = "log-success";
    else if (status === "warning") colorClass = "log-warning";
    else if (status === "error") colorClass = "log-error";
    
    line.innerHTML = `
        <span style="color: #4b3d75;">[${timestamp}]</span> 
        <span class="${colorClass}">${escapeHtml(message)}</span>
    `;
    
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
}

function handleSuccess(result) {
    // Hide loading log panel and display results
    document.getElementById("progress-container").style.display = "none";
    
    if (result.success) {
        document.getElementById("result-container").style.display = "block";
        
        const finalLink = document.getElementById("final-link");
        finalLink.href = result.bypassed_url;
        finalLink.innerText = result.bypassed_url;
        
        document.getElementById("res-strategy").innerText = result.strategy;
        document.getElementById("res-hops").innerText = result.hops.length;
        document.getElementById("res-time").innerText = result.time_taken.toFixed(2) + "s";
        
        // Render Hops steps list
        const hopsList = document.getElementById("hops-list");
        hopsList.innerHTML = "";
        result.hops.forEach((hop, index) => {
            const li = document.createElement("li");
            li.innerHTML = `<strong>Hop ${index + 1}:</strong> ${escapeHtml(hop)}`;
            hopsList.appendChild(li);
        });
        
        // Reload history list in background
        loadHistory();
    } else {
        handleFailure(result.error || "Headless browser failed to escape redirection walls.");
    }
}

function handleFailure(errorMsg) {
    document.getElementById("progress-container").style.display = "none";
    document.getElementById("error-container").style.display = "block";
    document.getElementById("error-message").innerText = errorMsg;
}

function resetBypasser() {
    document.getElementById("error-container").style.display = "none";
    document.getElementById("result-container").style.display = "none";
    document.getElementById("progress-container").style.display = "none";
    
    const urlInput = document.getElementById("short-url");
    urlInput.value = "";
    urlInput.focus();
}

function copyFinalLink() {
    const linkElement = document.getElementById("final-link");
    const linkText = linkElement.href;
    
    navigator.clipboard.writeText(linkText).then(() => {
        alert("Bypassed link copied to clipboard!");
    }).catch(err => {
        console.error("Copy failed", err);
    });
}

function loadHistory() {
    fetch("/api/history")
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                renderHistoryTable(data.history);
            }
        })
        .catch(err => console.error("Failed to load history", err));
}

function renderHistoryTable(historyList) {
    const rowsContainer = document.getElementById("history-rows");
    const emptyState = document.getElementById("history-empty");
    
    rowsContainer.innerHTML = "";
    
    if (historyList.length === 0) {
        emptyState.style.display = "flex";
        return;
    }
    
    emptyState.style.display = "none";
    
    historyList.forEach(item => {
        const row = document.createElement("tr");
        
        const shortUrlTrunc = item.original_url;
        const bypassedUrlTrunc = item.bypassed_url || "Failed";
        const successClass = item.success ? "resolved" : "error";
        
        row.innerHTML = `
            <td>
                <a href="${item.original_url}" target="_blank" class="table-link">${escapeHtml(shortUrlTrunc)}</a>
            </td>
            <td>
                ${item.success 
                    ? `<a href="${item.bypassed_url}" target="_blank" class="table-link resolved">${escapeHtml(bypassedUrlTrunc)}</a>` 
                    : `<span style="color: var(--error-red); font-weight:600;">Failed</span>`}
            </td>
            <td>
                <span class="history-badge">${escapeHtml(item.strategy || "N/A")}</span>
            </td>
            <td style="font-family: 'JetBrains Mono', monospace; font-size:13px;">
                ${item.time_taken.toFixed(2)}s
            </td>
            <td>
                <button class="btn-secondary" onclick="quickTestLink('${escapeHtml(item.original_url)}')">
                    <i class="fa-solid fa-bolt"></i> Test
                </button>
            </td>
        `;
        
        rowsContainer.appendChild(row);
    });
}

function quickTestLink(url) {
    switchTab("bypass");
    document.getElementById("short-url").value = url;
    startBypass();
}

function escapeHtml(text) {
    if (!text) return "";
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}
