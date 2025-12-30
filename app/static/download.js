// Download page functionality
// Handles form submission, progress updates, and task management

// Constants
const STATUS_ICONS = {
    pending: 'clock',
    downloading: 'arrow-down-circle',
    completed: 'check-circle',
    failed: 'x-circle',
    cancelled: 'dash-circle'
};

const STATUS_COLORS = {
    pending: 'secondary',
    downloading: 'primary',
    completed: 'success',
    failed: 'danger',
    cancelled: 'warning'
};

let updateInterval = null;
let collapsedTasks = new Set(); // Track which tasks are collapsed

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

        // Ensure polling is active for new downloads
        if (!updateInterval) {
            startPolling();
        }

    } catch (error) {
        console.error('Error starting download:', error);
        showNotification('Failed to start downloads: ' + error.message, 'danger');
    }
}

// Load all tasks from the server
let previousDownloadingCount = 0;
let lastTasksJson = '';

async function loadTasks() {
    try {
        const response = await fetch('/api/tasks');

        if (!response.ok) {
            throw new Error('Failed to load tasks');
        }

        const data = await response.json();

        // Check if data actually changed
        const currentTasksJson = JSON.stringify(data.tasks);
        if (currentTasksJson === lastTasksJson) {
            return; // No changes, skip update
        }
        lastTasksJson = currentTasksJson;

        // Check if all downloads just finished
        const downloadingCount = data.tasks.filter(t => t.status === 'downloading' || t.status === 'pending').length;
        const completedCount = data.tasks.filter(t => t.status === 'completed').length;
        const totalCount = data.tasks.length;

        // If we had downloading tasks before and now none, and we have completed tasks
        if (previousDownloadingCount > 0 && downloadingCount === 0 && completedCount > 0 && totalCount > 0) {
            const failedCount = data.tasks.filter(t => t.status === 'failed').length;
            const message = failedCount > 0
                ? `All downloads finished! ${completedCount} completed, ${failedCount} failed.`
                : `All downloads completed successfully! (${completedCount} total)`;
            showNotification(message, failedCount > 0 ? 'warning' : 'success');
        }

        previousDownloadingCount = downloadingCount;
        displayTasks(data.tasks);

        // Adjust polling based on active tasks
        adjustPolling(downloadingCount);

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

    // Add collapse all button and task cards
    const collapseAllBtn = `
        <div class="mb-3 d-flex justify-content-end">
            <button class="btn btn-sm btn-outline-secondary" id="toggleAllCards" onclick="toggleAllCards()">
                <i class="bi bi-chevron-up"></i> Collapse All
            </button>
        </div>
    `;

    taskList.innerHTML = collapseAllBtn + tasks.map(task => createTaskCard(task)).join('');

    // Restore collapse state after regenerating HTML
    collapsedTasks.forEach(taskId => {
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (card) {
            setTaskCollapsed(card, true);
        }
    });

    // Update button state based on collapsed tasks
    updateToggleAllButton();
}

// Update the toggle all button text based on state
function updateToggleAllButton() {
    const btn = document.getElementById('toggleAllCards');
    if (btn) {
        const hasCollapsed = collapsedTasks.size > 0;
        btn.innerHTML = hasCollapsed
            ? '<i class="bi bi-chevron-down"></i> Show All'
            : '<i class="bi bi-chevron-up"></i> Collapse All';
    }
}

// Set collapse state for a task card
function setTaskCollapsed(card, collapsed) {
    const detailsDiv = card.querySelector('.task-details');
    const chevron = card.querySelector('.collapse-chevron');

    detailsDiv.style.display = collapsed ? 'none' : 'block';
    chevron.classList.toggle('bi-chevron-down', collapsed);
    chevron.classList.toggle('bi-chevron-up', !collapsed);
}

// Toggle all task cards
function toggleAllCards() {
    const isExpanding = collapsedTasks.size > 0;

    document.querySelectorAll('.task-card').forEach(card => {
        const taskId = card.getAttribute('data-task-id');
        setTaskCollapsed(card, !isExpanding);

        if (isExpanding) {
            collapsedTasks.delete(taskId);
        } else {
            collapsedTasks.add(taskId);
        }
    });

    updateToggleAllButton();
}

// Toggle individual task card
function toggleTaskCard(taskId) {
    const card = document.querySelector(`[data-task-id="${taskId}"]`);
    const isCollapsed = collapsedTasks.has(taskId);

    setTaskCollapsed(card, !isCollapsed);

    if (isCollapsed) {
        collapsedTasks.delete(taskId);
    } else {
        collapsedTasks.add(taskId);
    }
}

// Extract service name from URL
function extractServiceName(url) {
    try {
        const urlObj = new URL(url);
        const hostname = urlObj.hostname;
        // Extract main domain (e.g., storytel.com -> storytel)
        const parts = hostname.split('.');
        if (parts.length >= 2) {
            return parts[parts.length - 2].toUpperCase();
        }
        return hostname.toUpperCase();
    } catch {
        return 'UNKNOWN';
    }
}

// Create progress bar HTML
function createProgressBar(task) {
    if (task.status !== 'downloading' && task.status !== 'completed') {
        return '';
    }

    const progressWidth = task.status === 'completed' ? 100 : task.progress;
    const color = STATUS_COLORS[task.status];
    const animated = task.status === 'downloading' ? 'progress-bar-animated' : '';

    return `
        <div class="mb-2">
            <div class="d-flex justify-content-between align-items-center mb-1">
                <small class="text-muted">Progress</small>
                <small class="text-muted"><strong>${progressWidth}%</strong></small>
            </div>
            <div class="progress" style="height: 8px;">
                <div class="progress-bar progress-bar-striped ${animated} bg-${color}"
                     role="progressbar" style="width: ${progressWidth}%" 
                     aria-valuenow="${progressWidth}" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
        </div>
    `;
}

// Create error message HTML
function createErrorDisplay(error) {
    if (!error) return '';

    const formattedError = escapeHtml(error).replace(/\n/g, '<br>');
    return `
        <div class="alert alert-danger mb-2">
            <strong><i class="bi bi-exclamation-triangle"></i> Error:</strong><br>
            <small style="white-space: pre-wrap;">${formattedError}</small>
        </div>
    `;
}

// Create file path display HTML
function createFilePathDisplay(outputFile, status) {
    if (!outputFile || status !== 'completed') return '';

    return `
        <div class="alert alert-info mt-2 mb-2 file-path-alert">
            <div class="d-flex align-items-start">
                <i class="bi bi-file-earmark-check fs-4 me-2 flex-shrink-0"></i>
                <div class="flex-grow-1">
                    <strong class="d-block mb-1">Downloaded File:</strong>
                    <code class="file-path-code">${escapeHtml(outputFile)}</code>
                </div>
            </div>
        </div>
    `;
}

// Create HTML for a single task card
function createTaskCard(task) {
    const icon = STATUS_ICONS[task.status] || 'circle';
    const color = STATUS_COLORS[task.status] || 'secondary';
    const serviceName = extractServiceName(task.url);
    const downloadingClass = task.status === 'downloading' ? 'downloading-indicator' : '';

    return `
        <div class="card mb-3 task-card status-${task.status}" data-task-id="${task.task_id}">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div class="flex-grow-1">
                        <h6 class="mb-1 d-flex align-items-center gap-2">
                            <i class="bi bi-chevron-up collapse-chevron" onclick="toggleTaskCard('${task.task_id}')" style="cursor: pointer;" title="Collapse/Expand"></i>
                            <i class="bi bi-${icon} text-${color} ${downloadingClass}"></i>
                            <span class="status-badge badge bg-${color}">${task.status.toUpperCase()}</span>
                            <span class="badge bg-secondary">${serviceName}</span>
                        </h6>
                        <p class="task-url mb-1 url-clickable" 
                           data-url="${escapeHtml(task.url)}" 
                           onclick="copyUrlToInput('${escapeHtml(task.url)}')"
                           title="Click to re-add this URL to the download form">
                            ${escapeHtml(truncateUrl(task.url, 80))}
                        </p>
                        ${task.metadata ? createMetadataDisplay(task.metadata) : ''}
                    </div>
                    <div class="d-flex gap-1 task-actions">
                        ${task.status === 'downloading' ? `
                            <button class="btn btn-sm btn-outline-danger" onclick="cancelTask('${task.task_id}')" title="Cancel download">
                                <i class="bi bi-x"></i>
                            </button>
                        ` : ''}
                        ${task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled' ? `
                            <button class="btn btn-sm btn-outline-danger remove-task-btn" onclick="removeTask('${task.task_id}')" title="Remove from list">
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
                <div class="task-details">
                    <small class="text-muted d-block mb-2">${escapeHtml(task.message)}</small>
                    ${createProgressBar(task)}
                    ${createErrorDisplay(task.error)}
                    ${createFilePathDisplay(task.output_file, task.status)}
                    ${formatTimestamp(task)}
                </div>
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

// Create metadata display
function createMetadataDisplay(metadata) {
    if (!metadata || Object.keys(metadata).length === 0) {
        return '';
    }

    const items = [];

    if (metadata.title) {
        items.push(`<strong>${escapeHtml(metadata.title)}</strong>`);
    }
    if (metadata.author) {
        items.push(`by ${escapeHtml(metadata.author)}`);
    }
    if (metadata.narrator) {
        items.push(`narrated by ${escapeHtml(metadata.narrator)}`);
    }
    if (metadata.year) {
        items.push(`(${escapeHtml(metadata.year)})`);
    }
    if (metadata.duration) {
        items.push(`<i class="bi bi-clock"></i> ${escapeHtml(metadata.duration)}`);
    }
    if (metadata.size) {
        items.push(`<i class="bi bi-file-earmark"></i> ${escapeHtml(metadata.size)}`);
    }

    return items.length > 0 ? `<div class="task-metadata mb-1"><small class="text-muted">${items.join(' • ')}</small></div>` : '';
}

// Add URL to input field with optional message
function addUrlToInput(url, message = 'URL added to download form') {
    const urlsTextarea = document.getElementById('urls');
    if (!urlsTextarea) return;

    // Add the URL to the textarea
    const currentValue = urlsTextarea.value.trim();
    urlsTextarea.value = currentValue ? currentValue + '\n' + url : url;

    // Scroll to the form
    urlsTextarea.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Highlight the textarea briefly
    urlsTextarea.classList.add('highlight-input');
    setTimeout(() => urlsTextarea.classList.remove('highlight-input'), 1500);

    showNotification(message, 'info');
}

// Retry a failed download
function retryTask(url) {
    addUrlToInput(url, 'URL added to download form. Click "Start Download" when ready.');
}

// Copy URL to input field
function copyUrlToInput(url) {
    addUrlToInput(url, 'URL added to download form');
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

// Remove individual task
async function removeTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to remove task');
        }

        showNotification('Task removed', 'info');
        await loadTasks();

    } catch (error) {
        console.error('Error removing task:', error);
        showNotification('Failed to remove task', 'danger');
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

// Adjust polling interval based on active tasks
function adjustPolling(activeTaskCount) {
    if (activeTaskCount === 0) {
        // Stop polling when no active tasks
        stopPolling();
    } else if (!updateInterval) {
        // Resume polling if we have active tasks but polling stopped
        startPolling();
    }
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
