// Download page functionality
// Handles form submission, progress updates, and task management

let updateInterval = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function () {
    // Load existing tasks
    loadTasks();

    // Setup form handler
    const form = document.getElementById('downloadForm');
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }

    // Setup clear completed button
    const clearBtn = document.getElementById('clearCompleted');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearCompleted);
    }

    // Start polling for updates
    startPolling();
});

// Handle form submission
async function handleFormSubmit(e) {
    e.preventDefault();

    const form = e.target;
    const formData = new FormData(form);

    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Failed to start download');
        }

        const data = await response.json();

        // Clear the form
        form.reset();

        // Show success message with warning count if applicable
        if (data.warnings && data.warnings.length > 0) {
            showNotification(
                `${data.tasks.length} download(s) started. ${data.warnings.length} invalid URL(s) skipped.`,
                'warning'
            );
            // Display warnings in the queue
            displayWarnings(data.warnings);
        } else {
            showNotification('Downloads started successfully!', 'success');
        }

        // Immediately load tasks to show the new downloads
        await loadTasks();

    } catch (error) {
        console.error('Error starting download:', error);
        showNotification('Failed to start downloads: ' + error.message, 'danger');
    }
}

// Load all tasks from the server
async function loadTasks() {
    try {
        const response = await fetch('/api/tasks');

        if (!response.ok) {
            throw new Error('Failed to load tasks');
        }

        const data = await response.json();
        displayTasks(data.tasks);

    } catch (error) {
        console.error('Error loading tasks:', error);
    }
}

// Display warnings for invalid URLs
function displayWarnings(warnings) {
    if (!warnings || warnings.length === 0) return;

    const taskList = document.getElementById('taskList');
    const warningCards = warnings.map(warning => createWarningCard(warning)).join('');

    // Prepend warnings to the task list
    taskList.insertAdjacentHTML('afterbegin', warningCards);

    // Auto-dismiss warnings after 10 seconds
    setTimeout(() => {
        document.querySelectorAll('.warning-card').forEach(card => {
            card.style.transition = 'opacity 0.5s';
            card.style.opacity = '0';
            setTimeout(() => card.remove(), 500);
        });
    }, 10000);
}

// Create HTML for a warning card
function createWarningCard(warning) {
    return `
        <div class="card mb-3 border-warning warning-card">
            <div class="card-body">
                <div class="d-flex align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">
                            <i class="bi bi-exclamation-triangle text-warning"></i>
                            <span class="badge bg-warning text-dark">INVALID URL</span>
                        </h6>
                        <p class="mb-1 text-muted small">
                            ${escapeHtml(warning.url)}
                        </p>
                        <small class="text-danger">
                            <i class="bi bi-x-circle"></i> ${escapeHtml(warning.warning)}
                        </small>
                    </div>
                    <button class="btn btn-sm btn-outline-secondary" onclick="this.closest('.warning-card').remove()" title="Dismiss">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Display tasks in the UI
function displayTasks(tasks) {
    const taskList = document.getElementById('taskList');

    if (!tasks || tasks.length === 0) {
        taskList.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="bi bi-inbox display-4"></i>
                <p class="mt-2">No downloads in queue</p>
            </div>
        `;
        return;
    }

    // Sort tasks: active first, then by start time
    tasks.sort((a, b) => {
        const statusOrder = { downloading: 0, pending: 1, completed: 2, failed: 3, cancelled: 4 };
        const statusDiff = (statusOrder[a.status] || 5) - (statusOrder[b.status] || 5);
        if (statusDiff !== 0) return statusDiff;

        return new Date(b.started_at || 0) - new Date(a.started_at || 0);
    });

    taskList.innerHTML = tasks.map(task => createTaskCard(task)).join('');
}

// Create HTML for a single task card
function createTaskCard(task) {
    const statusIcons = {
        pending: 'clock',
        downloading: 'arrow-down-circle',
        completed: 'check-circle',
        failed: 'x-circle',
        cancelled: 'dash-circle'
    };

    const statusColors = {
        pending: 'secondary',
        downloading: 'primary',
        completed: 'success',
        failed: 'danger',
        cancelled: 'warning'
    };

    const icon = statusIcons[task.status] || 'circle';
    const color = statusColors[task.status] || 'secondary';

    let progressBar = '';
    if (task.status === 'downloading' || task.status === 'completed') {
        const progressWidth = task.status === 'completed' ? 100 : task.progress;
        progressBar = `
            <div class="mb-2">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-muted">Progress</small>
                    <small class="text-muted"><strong>${progressWidth}%</strong></small>
                </div>
                <div class="progress" style="height: 8px;">
                    <div class="progress-bar progress-bar-striped ${task.status === 'downloading' ? 'progress-bar-animated' : ''} bg-${color}"
                         role="progressbar" style="width: ${progressWidth}%" 
                         aria-valuenow="${progressWidth}" aria-valuemin="0" aria-valuemax="100"></div>
                </div>
            </div>
        `;
    }

    let errorMessage = '';
    if (task.error) {
        // Preserve line breaks and format error messages nicely
        const formattedError = escapeHtml(task.error).replace(/\n/g, '<br>');
        errorMessage = `
            <div class="alert alert-danger mb-2">
                <strong><i class="bi bi-exclamation-triangle"></i> Error:</strong><br>
                <small style="white-space: pre-wrap;">${formattedError}</small>
            </div>
        `;
    }

    let outputFile = '';
    if (task.output_file) {
        outputFile = `
            <div class="mt-2">
                <small class="text-success">
                    <i class="bi bi-file-earmark-check"></i> ${escapeHtml(task.output_file)}
                </small>
            </div>
        `;
    }

    const downloadingClass = task.status === 'downloading' ? 'downloading-indicator' : '';

    return `
        <div class="card mb-3 task-card status-${task.status}" data-task-id="${task.task_id}">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">
                            <i class="bi bi-${icon} text-${color} ${downloadingClass}"></i>
                            <span class="status-badge badge bg-${color}">${task.status.toUpperCase()}</span>
                        </h6>
                        <p class="task-url mb-1 url-clickable" 
                           data-url="${escapeHtml(task.url)}" 
                           onclick="copyUrlToInput('${escapeHtml(task.url)}')"
                           title="Click to re-add this URL to the download form">
                            ${escapeHtml(truncateUrl(task.url, 80))}
                        </p>
                        <small class="text-muted">${escapeHtml(task.message)}</small>
                    </div>
                    <div class="d-flex gap-1">
                        ${task.status === 'downloading' ? `
                            <button class="btn btn-sm btn-outline-danger" onclick="cancelTask('${task.task_id}')" title="Cancel download">
                                <i class="bi bi-x"></i>
                            </button>
                        ` : ''}
                        ${task.status === 'failed' ? `
                            <button class="btn btn-sm btn-outline-primary" onclick="retryTask('${escapeHtml(task.url)}')" title="Retry download">
                                <i class="bi bi-arrow-clockwise"></i> Retry
                            </button>
                        ` : ''}
                    </div>
                </div>
                ${progressBar}
                ${errorMessage}
                ${outputFile}
                ${formatTimestamp(task)}
            </div>
        </div>
    `;
}

// Cancel a task
async function cancelTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/cancel`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('Failed to cancel task');
        }

        showNotification('Download cancelled', 'warning');
        await loadTasks();

    } catch (error) {
        console.error('Error cancelling task:', error);
        showNotification('Failed to cancel download', 'danger');
    }
}

// Retry a failed download
async function retryTask(url) {
    const urlsTextarea = document.getElementById('urls');
    if (urlsTextarea) {
        // Add the URL to the textarea
        const currentValue = urlsTextarea.value.trim();
        urlsTextarea.value = currentValue ? currentValue + '\n' + url : url;

        // Scroll to the form
        urlsTextarea.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Highlight the textarea briefly
        urlsTextarea.classList.add('highlight-input');
        setTimeout(() => {
            urlsTextarea.classList.remove('highlight-input');
        }, 1500);

        showNotification('URL added to download form. Click "Start Download" when ready.', 'info');
    }
}

// Copy URL to input field
function copyUrlToInput(url) {
    const urlsTextarea = document.getElementById('urls');
    if (urlsTextarea) {
        // Add the URL to the textarea
        const currentValue = urlsTextarea.value.trim();
        urlsTextarea.value = currentValue ? currentValue + '\n' + url : url;

        // Scroll to the form
        urlsTextarea.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Highlight the textarea briefly
        urlsTextarea.classList.add('highlight-input');
        setTimeout(() => {
            urlsTextarea.classList.remove('highlight-input');
        }, 1500);

        showNotification('URL added to download form', 'success');
    }
}

// Clear completed tasks
async function clearCompleted() {
    try {
        const response = await fetch('/api/tasks/clear', {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('Failed to clear tasks');
        }

        showNotification('Cleared completed tasks', 'info');
        await loadTasks();

    } catch (error) {
        console.error('Error clearing tasks:', error);
        showNotification('Failed to clear tasks', 'danger');
    }
}

// Show notification (temporary alert)
function showNotification(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
    alertDiv.style.zIndex = '9999';
    alertDiv.style.minWidth = '300px';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(alertDiv);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Start polling for task updates
function startPolling() {
    if (updateInterval) {
        clearInterval(updateInterval);
    }

    // Poll every 2 seconds
    updateInterval = setInterval(async () => {
        await loadTasks();
    }, 2000);
}

// Stop polling (cleanup)
function stopPolling() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }
}

// Format timestamp display
function formatTimestamp(task) {
    if (!task.started_at) return '';

    const started = new Date(task.started_at);
    let html = `<small class="text-muted">Started: ${started.toLocaleString()}</small>`;

    if (task.completed_at) {
        const completed = new Date(task.completed_at);
        const duration = Math.round((completed - started) / 1000);
        html += ` <small class="text-muted">| Duration: ${formatDuration(duration)}</small>`;
    }

    return `<div class="mt-2">${html}</div>`;
}

// Format duration in human-readable format
function formatDuration(seconds) {
    if (seconds < 60) return `${seconds}s`;

    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;

    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours}h ${remainingMinutes}m`;
}

// Truncate URL for display
function truncateUrl(url, maxLength) {
    if (url.length <= maxLength) return url;
    return url.substring(0, maxLength - 3) + '...';
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cleanup on page unload
window.addEventListener('beforeunload', function () {
    stopPolling();
});
