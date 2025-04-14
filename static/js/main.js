/**
 * RPS Arena - Main JavaScript
 * This file handles all interactive functionality for the web interface
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips and popovers
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    const popoverList = [...popoverTriggerList].map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
    
    // Dashboard - Handle withdrawal approvals/rejections
    setupWithdrawalActions();
    
    // Dashboard - User search functionality
    setupUserSearch();
    
    // Admin panel functionality
    if (document.getElementById('adminTabs')) {
        setupAdminPanel();
    }
    
    // Handle any game animations on the home page
    setupHomePageAnimations();
    
    // Initialize any charts if they exist on the page
    initializeCharts();
});

/**
 * Set up withdrawal approval/rejection handling
 */
function setupWithdrawalActions() {
    // Approve withdrawal buttons
    document.querySelectorAll('.approve-withdrawal').forEach(button => {
        button.addEventListener('click', function() {
            const withdrawalId = this.getAttribute('data-id');
            approveWithdrawal(withdrawalId);
        });
    });
    
    // Reject withdrawal buttons
    document.querySelectorAll('.reject-withdrawal').forEach(button => {
        button.addEventListener('click', function() {
            const withdrawalId = this.getAttribute('data-id');
            rejectWithdrawal(withdrawalId);
        });
    });
}

/**
 * Approve a withdrawal request
 * @param {string} withdrawalId - The ID of the withdrawal to approve
 */
function approveWithdrawal(withdrawalId) {
    // Show confirmation dialog
    const confirmationMessage = `Are you sure you want to approve withdrawal #${withdrawalId}?`;
    if (confirm(confirmationMessage)) {
        // Make API request to approve withdrawal
        fetch(`/api/approve_withdrawal/${withdrawalId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast('Success', data.message, 'success');
                // Remove the withdrawal row or update its status
                const withdrawalRow = document.querySelector(`tr[data-withdrawal-id="${withdrawalId}"]`);
                if (withdrawalRow) {
                    withdrawalRow.remove();
                }
            } else {
                showToast('Error', data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('Error', 'Failed to process withdrawal approval', 'danger');
        });
    }
}

/**
 * Reject a withdrawal request
 * @param {string} withdrawalId - The ID of the withdrawal to reject
 */
function rejectWithdrawal(withdrawalId) {
    // Show confirmation dialog
    const confirmationMessage = `Are you sure you want to reject withdrawal #${withdrawalId}?`;
    if (confirm(confirmationMessage)) {
        // Make API request to reject withdrawal
        fetch(`/api/reject_withdrawal/${withdrawalId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast('Success', data.message, 'success');
                // Remove the withdrawal row or update its status
                const withdrawalRow = document.querySelector(`tr[data-withdrawal-id="${withdrawalId}"]`);
                if (withdrawalRow) {
                    withdrawalRow.remove();
                }
            } else {
                showToast('Error', data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('Error', 'Failed to process withdrawal rejection', 'danger');
        });
    }
}

/**
 * Set up user search functionality
 */
function setupUserSearch() {
    const userSearchBtn = document.getElementById('userSearchBtn');
    if (userSearchBtn) {
        userSearchBtn.addEventListener('click', function() {
            const searchInput = document.getElementById('userSearchInput');
            if (searchInput && searchInput.value.trim() !== '') {
                searchUsers(searchInput.value);
            }
        });
    }
    
    // Admin panel user search
    const adminUserSearchBtn = document.getElementById('adminUserSearchBtn');
    if (adminUserSearchBtn) {
        adminUserSearchBtn.addEventListener('click', function() {
            const searchInput = document.getElementById('adminUserSearch');
            if (searchInput && searchInput.value.trim() !== '') {
                adminSearchUsers(searchInput.value);
            }
        });
    }
}

/**
 * Search for users with the given query
 * @param {string} query - The search query
 */
function searchUsers(query) {
    fetch(`/api/search_user?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayUserSearchResults(data.users);
            } else {
                showToast('Error', data.message || 'Search failed', 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('Error', 'Failed to search users', 'danger');
        });
}

/**
 * Display search results in the search modal
 * @param {Array} users - Array of user objects
 */
function displayUserSearchResults(users) {
    const searchModal = new bootstrap.Modal(document.getElementById('userSearchModal'));
    const resultsContainer = document.getElementById('userSearchResults');
    
    if (users.length === 0) {
        resultsContainer.innerHTML = '<div class="text-center py-4"><p>No users found matching your search.</p></div>';
    } else {
        let html = '<div class="list-group">';
        users.forEach(user => {
            html += `
                <div class="list-group-item list-group-item-action">
                    <div class="d-flex w-100 justify-content-between">
                        <h5 class="mb-1">${user.username}</h5>
                        <small>ID: ${user.id}</small>
                    </div>
                    <p class="mb-1">Balance: $${user.balance.toFixed(2)} | Games: ${user.games_played} | Win Rate: ${user.win_rate.toFixed(1)}%</p>
                    <small>Created: ${user.created_at}</small>
                </div>
            `;
        });
        html += '</div>';
        resultsContainer.innerHTML = html;
    }
    
    searchModal.show();
}

/**
 * Admin panel user search
 * @param {string} query - The search query
 */
function adminSearchUsers(query) {
    fetch(`/api/search_user?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayAdminUserSearchResults(data.users);
            } else {
                showToast('Error', data.message || 'Search failed', 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('Error', 'Failed to search users', 'danger');
        });
}

/**
 * Display user search results in the admin panel
 * @param {Array} users - Array of user objects
 */
function displayAdminUserSearchResults(users) {
    const resultsContainer = document.getElementById('userSearchResults');
    
    if (!resultsContainer) return;
    
    if (users.length === 0) {
        resultsContainer.innerHTML = '<div class="text-center py-4"><p>No users found matching your search.</p></div>';
    } else {
        let html = '<div class="list-group">';
        users.forEach(user => {
            html += `
                <div class="list-group-item list-group-item-action user-search-item" data-user-id="${user.id}">
                    <div class="d-flex w-100 justify-content-between">
                        <h5 class="mb-1">${user.username}</h5>
                        <small class="text-muted">ID: ${user.id}</small>
                    </div>
                    <p class="mb-1">Balance: $${user.balance.toFixed(2)} | Games: ${user.games_played} | Win Rate: ${user.win_rate.toFixed(1)}%</p>
                    <div class="d-flex justify-content-between align-items-center mt-2">
                        <small class="text-muted">Created: ${user.created_at}</small>
                        <button class="btn btn-primary btn-sm view-user-details" data-user-id="${user.id}">
                            View Details
                        </button>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        resultsContainer.innerHTML = html;
        
        // Add event listeners to view user details buttons
        document.querySelectorAll('.view-user-details').forEach(button => {
            button.addEventListener('click', function() {
                const userId = this.getAttribute('data-user-id');
                loadUserDetails(userId);
            });
        });
    }
}

/**
 * Load user details for the admin panel
 * @param {string} userId - The ID of the user
 */
function loadUserDetails(userId) {
    // In a real app, this would fetch detailed user info from the server
    // For now, we'll use the user data we already have from the search results
    
    // Find the user in the search results
    const userElement = document.querySelector(`.user-search-item[data-user-id="${userId}"]`);
    if (!userElement) return;
    
    // Get basic user info from the DOM element
    const username = userElement.querySelector('h5').textContent;
    const balanceText = userElement.querySelector('p.mb-1').textContent;
    const balance = balanceText.match(/Balance: \$([\d.]+)/)[1];
    const gamesPlayed = balanceText.match(/Games: (\d+)/)[1];
    const winRate = balanceText.match(/Win Rate: ([\d.]+)%/)[1];
    const created = userElement.querySelector('small.text-muted').textContent.replace('Created: ', '');
    
    // Display user details in the user details section
    document.getElementById('userDetailsUsername').textContent = username;
    document.getElementById('userDetailsID').textContent = `ID: ${userId}`;
    document.getElementById('userDetailsBalance').textContent = `Balance: $${balance}`;
    document.getElementById('userDetailsCreated').textContent = `Created: ${created}`;
    document.getElementById('userDetailsGamesPlayed').textContent = `Games Played: ${gamesPlayed}`;
    document.getElementById('userDetailsWinRate').textContent = `Win Rate: ${winRate}%`;
    
    // Show the user details section
    document.getElementById('userDetails').classList.remove('d-none');
    
    // In a real app, you would load additional data like transaction history
    // For now we'll just show a placeholder
    document.getElementById('userTransactionsList').innerHTML = `
        <tr>
            <td colspan="4" class="text-center">Loading transaction history...</td>
        </tr>
    `;
    
    // Scroll to the user details section
    document.getElementById('userDetails').scrollIntoView({ behavior: 'smooth' });
}

/**
 * Set up the admin panel functionality
 */
function setupAdminPanel() {
    // User management - Save changes button
    const saveUserChangesBtn = document.getElementById('saveUserChanges');
    if (saveUserChangesBtn) {
        saveUserChangesBtn.addEventListener('click', function() {
            // Get updated user data
            const userId = document.getElementById('userDetailsID').textContent.replace('ID: ', '');
            const isAdmin = document.getElementById('userIsAdmin').checked;
            
            // In a real app, this would make an API call to update the user
            showToast('Success', 'User details updated successfully', 'success');
        });
    }
    
    // User management - Delete user button
    const deleteUserBtn = document.getElementById('deleteUser');
    if (deleteUserBtn) {
        deleteUserBtn.addEventListener('click', function() {
            const userId = document.getElementById('userDetailsID').textContent.replace('ID: ', '');
            const username = document.getElementById('userDetailsUsername').textContent;
            
            showConfirmationModal(
                'Delete User',
                `Are you sure you want to delete user ${username}? This action cannot be undone.`,
                function() {
                    // In a real app, this would make an API call to delete the user
                    showToast('Success', `User ${username} has been deleted`, 'success');
                    document.getElementById('userDetails').classList.add('d-none');
                }
            );
        });
    }
    
    // Settings - Save settings button
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', function() {
            // Get all form values
            const defaultBetAmount = document.getElementById('defaultBetAmount').value;
            const platformFee = document.getElementById('platformFee').value;
            const cooldownSeconds = document.getElementById('cooldownSeconds').value;
            const minDeposit = document.getElementById('minDeposit').value;
            const maxDeposit = document.getElementById('maxDeposit').value;
            const minWithdraw = document.getElementById('minWithdraw').value;
            const maxWithdraw = document.getElementById('maxWithdraw').value;
            const adminUserIds = document.getElementById('adminUserIds').value;
            
            // In a real app, this would make an API call to update the settings
            showToast('Success', 'System settings updated successfully', 'success');
        });
    }
    
    // Settings - Reset settings button
    const resetSettingsBtn = document.getElementById('resetSettingsBtn');
    if (resetSettingsBtn) {
        resetSettingsBtn.addEventListener('click', function() {
            showConfirmationModal(
                'Reset Settings',
                'Are you sure you want to reset all settings to their default values?',
                function() {
                    // Reset form values to defaults
                    document.getElementById('defaultBetAmount').value = '10';
                    document.getElementById('platformFee').value = '5';
                    document.getElementById('cooldownSeconds').value = '5';
                    document.getElementById('minDeposit').value = '5';
                    document.getElementById('maxDeposit').value = '1000';
                    document.getElementById('minWithdraw').value = '10';
                    document.getElementById('maxWithdraw').value = '500';
                    document.getElementById('adminUserIds').value = '';
                    
                    showToast('Success', 'Settings have been reset to defaults', 'success');
                }
            );
        });
    }
}

/**
 * Initialize charts for the admin panel
 */
function initializeCharts() {
    // Game outcomes chart
    const gameOutcomesChart = document.getElementById('gameOutcomesChart');
    if (gameOutcomesChart) {
        new Chart(gameOutcomesChart, {
            type: 'pie',
            data: {
                labels: ['Player Wins', 'Draws'],
                datasets: [{
                    data: [75, 25],
                    backgroundColor: [
                        'rgba(40, 167, 69, 0.7)',
                        'rgba(108, 117, 125, 0.7)'
                    ],
                    borderColor: [
                        'rgba(40, 167, 69, 1)',
                        'rgba(108, 117, 125, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: true,
                        text: 'Game Outcomes'
                    }
                }
            }
        });
    }
    
    // Player choices chart
    const playerChoicesChart = document.getElementById('playerChoicesChart');
    if (playerChoicesChart) {
        new Chart(playerChoicesChart, {
            type: 'bar',
            data: {
                labels: ['Rock', 'Paper', 'Scissors'],
                datasets: [{
                    label: 'Times Chosen',
                    data: [42, 38, 45],
                    backgroundColor: [
                        'rgba(108, 117, 125, 0.7)',
                        'rgba(13, 110, 253, 0.7)',
                        'rgba(220, 53, 69, 0.7)'
                    ],
                    borderColor: [
                        'rgba(108, 117, 125, 1)',
                        'rgba(13, 110, 253, 1)',
                        'rgba(220, 53, 69, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: 'Player Choices Distribution'
                    }
                }
            }
        });
    }
    
    // Game activity chart
    const gameActivityChart = document.getElementById('gameActivityChart');
    if (gameActivityChart) {
        new Chart(gameActivityChart, {
            type: 'line',
            data: {
                labels: ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5', 'Day 6', 'Day 7'],
                datasets: [{
                    label: 'Games Played',
                    data: [12, 19, 15, 17, 22, 24, 31],
                    borderColor: 'rgba(13, 110, 253, 1)',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Games Played (Last 7 Days)'
                    }
                }
            }
        });
    }
}

/**
 * Set up animations for the home page
 */
function setupHomePageAnimations() {
    // Animate Rock, Paper, Scissors icons
    const rpsIcons = document.querySelectorAll('.rps-icons span');
    if (rpsIcons.length > 0) {
        let currentIndex = 0;
        
        // Initial highlight
        rpsIcons[currentIndex].style.transform = 'scale(1.2)';
        
        // Set interval to cycle through icons
        setInterval(() => {
            // Remove highlight from current icon
            rpsIcons[currentIndex].style.transform = 'scale(1)';
            
            // Move to next icon
            currentIndex = (currentIndex + 1) % rpsIcons.length;
            
            // Add highlight to new current icon
            rpsIcons[currentIndex].style.transform = 'scale(1.2)';
        }, 2000);
    }
}

/**
 * Show a confirmation modal with custom title, message, and callback
 * @param {string} title - The modal title
 * @param {string} message - The confirmation message
 * @param {Function} confirmCallback - The function to call when confirmed
 */
function showConfirmationModal(title, message, confirmCallback) {
    const modal = document.getElementById('confirmationModal');
    if (!modal) return;
    
    const bootstrapModal = new bootstrap.Modal(modal);
    
    document.getElementById('confirmationTitle').textContent = title;
    document.getElementById('confirmationMessage').textContent = message;
    
    // Set up the confirm button
    const confirmBtn = document.getElementById('confirmActionBtn');
    
    // Remove any existing event listeners
    const newConfirmBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
    
    // Add new event listener
    newConfirmBtn.addEventListener('click', function() {
        bootstrapModal.hide();
        if (typeof confirmCallback === 'function') {
            confirmCallback();
        }
    });
    
    bootstrapModal.show();
}

/**
 * Show a toast notification
 * @param {string} title - The toast title
 * @param {string} message - The toast message
 * @param {string} type - The type of toast (success, danger, warning, info)
 */
function showToast(title, message, type = 'info') {
    const toastEl = document.getElementById('adminActionToast') || document.getElementById('adminToast');
    if (!toastEl) return;
    
    const toast = new bootstrap.Toast(toastEl);
    
    // Set toast content
    document.getElementById('toastTitle').textContent = title;
    document.getElementById('toastMessage').textContent = message;
    
    // Set toast header color based on type
    const toastHeader = toastEl.querySelector('.toast-header');
    toastHeader.className = 'toast-header';
    toastHeader.classList.add(`bg-${type}`, type === 'warning' ? 'text-dark' : 'text-white');
    
    toast.show();
}
