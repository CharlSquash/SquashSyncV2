document.addEventListener('DOMContentLoaded', () => {
    const app = {
        // STATE
        allPlayersForDisplay: [],

        // --- DOM ELEMENTS ---
        elements: {
            appContainer: document.getElementById('session-planner-app'),
            attendanceList: document.getElementById('attendance-list'),
            emailModal: new bootstrap.Modal(document.getElementById('emailUpdateModal')),
            emailInput: document.getElementById('playerEmailInput'),
            emailPlayerId: document.getElementById('emailUpdatePlayerId'),
            saveEmailBtn: document.getElementById('saveEmailBtn'),
        },

        // --- APPLICATION FLOW ---

        init() {
            console.log("Session Planner Initializing (Attendance Only)...");
            try {
                this.sessionId = this.elements.appContainer.dataset.sessionId;
                
                // This will parse the full attendance list for the top display section
                // This script tag was preserved in the template
                const displayDataScript = document.getElementById('all-players-data');
                if (displayDataScript) {
                    this.allPlayersForDisplay = JSON.parse(displayDataScript.textContent);
                    this.allPlayersForDisplay.sort((a, b) => a.name.localeCompare(b.name));
                } else {
                    console.warn("Display data script not found");
                    this.allPlayersForDisplay = [];
                }

            } catch (e) {
                console.error("Fatal Error: Could not parse data from Django.", e);
                this.elements.appContainer.innerHTML = `<div class="alert alert-danger"><h4>Application Error</h4><p>Could not load session data.</p></div>`;
                return;
            }

            this.addEventListeners();
            this.render();
            console.log("Planner setup complete.");
        },

        render() {
            this.renderAttendanceList();
        },

        addEventListeners() {
            // Listener for the main planner content (specifically for attendance clicks)
            this.elements.appContainer.addEventListener('click', this.handleAppClick.bind(this));
            
            // Email Modal Save listener
            this.elements.saveEmailBtn.addEventListener('click', this.handleSaveEmail.bind(this));
        },

        // --- RENDERING FUNCTIONS ---

        renderAttendanceList() {
            const container = this.elements.attendanceList;
            if (!container) return;
            container.innerHTML = '';
            this.allPlayersForDisplay.sort((a, b) => a.name.localeCompare(b.name));
            
            this.allPlayersForDisplay.forEach(player => {
                const badgeClass = player.status === 'ATTENDING' ? 'text-bg-success' : player.status === 'DECLINED' ? 'text-bg-danger' : 'text-bg-secondary';
                
                // --- ADDED: Notification Icon Logic ---
                // Using SVG icons directly for self-contained rendering (similar to Lucide React)
                let notificationIcon = '';
                if (player.has_notification_email) {
                    // Check Circle (Green) - Clickable to edit
                    notificationIcon = `<span class="notification-icon-btn ms-1" style="cursor: pointer;" data-player-id="${player.id}" data-has-email="true" title="Notification Email Verified (Click to Edit)" data-bs-toggle="tooltip"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-success"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><path d="m9 11 3 3L22 4"></path></svg></span>`;
                } else {
                    // Alert Triangle (Orange/Warning) - Clickable to Add
                    notificationIcon = `<span class="notification-icon-btn ms-1" style="cursor: pointer;" data-player-id="${player.id}" data-has-email="false" title="Missing Notification Email (Click to Add)" data-bs-toggle="tooltip"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-warning"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><path d="M12 9v4"></path><path d="M12 17h.01"></path></svg></span>`;
                }

                container.innerHTML += `
                    <div class="player-attendance-item" data-player-id="${player.id}">
                        <div class="d-flex align-items-center">
                            <a href="/players/${player.id}/" class="player-name-link me-2">${player.name}</a>
                            ${notificationIcon}
                        </div>
                        <span class="badge rounded-pill ${badgeClass}" title="Click to cycle status" style="cursor: pointer;">${player.status}</span>
                    </div>`;
            });
            
            // Re-initialize tooltips
            const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
            const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
        },

        // --- LOGIC & ACTIONS ---

        cyclePlayerStatus(playerId) {
            const playerForDisplay = this.allPlayersForDisplay.find(p => p.id === playerId);
            if (!playerForDisplay) return;

            const statusOrder = ['PENDING', 'ATTENDING', 'NOT_ATTENDING'];
            const currentStatusIndex = statusOrder.indexOf(playerForDisplay.status);
            const nextStatus = statusOrder[(currentStatusIndex + 1) % statusOrder.length];
            
            // 1. Update the display list
            playerForDisplay.status = nextStatus;

            // 2. Re-render section to show the change immediately
            this.renderAttendanceList();

            // Send the update to the server in the background
            const url = this.elements.appContainer.dataset.updateAttendanceUrl;
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                              (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
            
            fetch(url.replace('0', this.sessionId), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ player_id: playerId, status: nextStatus }),
            }).catch(error => {
                console.error("Error saving attendance:", error);
                // Optional: revert the change on error
                playerForDisplay.status = statusOrder[currentStatusIndex];
                this.render(); // Re-render everything to revert UI
            });
        },
        
        openEmailModal(playerId) {
            const player = this.allPlayersForDisplay.find(p => p.id === playerId);
            if (!player) return;
            
            this.elements.emailInput.value = ''; // Clear or maybe fetch existing if we had it.
            // We don't have the existing email in `allPlayersForDisplay`, only the boolean.
            // That's fine, we treat it as "Set new email"
            
            this.elements.emailPlayerId.value = playerId;
            this.elements.emailModal.show();
            
            // Focus input
            setTimeout(() => this.elements.emailInput.focus(), 500);
        },

        handleSaveEmail() {
            const playerId = parseInt(this.elements.emailPlayerId.value);
            const email = this.elements.emailInput.value.trim();
            const btn = this.elements.saveEmailBtn;
            
            if (!email) {
                alert("Please enter an email address.");
                return;
            }
            
            // Optimistic Update
            const originalBtnText = btn.innerHTML;
            btn.innerHTML = 'Sending...';
            btn.disabled = true;
            
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                              (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
            
            fetch(`/players/api/update-notification-email/${playerId}/`, {
                 method: 'POST',
                 headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                 body: JSON.stringify({ email: email })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Update Local State - WE DO NOT CHANGE ICON TO GREEN YET
                    // because it is pending verification.
                    
                    alert(`Verification email sent to ${email}. The player must click the link to confirm.`);
                    this.elements.emailModal.hide();
                    
                    // Show success toast logic here if you had a toast system
                } else {
                    alert('Error: ' + data.message);
                }
            })
            .catch(err => {
                console.error(err);
                alert('An unexpected error occurred.');
            })
            .finally(() => {
                btn.innerHTML = originalBtnText;
                btn.disabled = false;
            });
        },

        // --- EVENT HANDLERS ---
        
        handleAppClick(e) {
            const target = e.target;
            
            // Check for Notification Icon Click first
            const notificationIcon = target.closest('.notification-icon-btn');
            if (notificationIcon) {
                e.stopPropagation(); // Stop bubbling so we don't trigger cyclePlayerStatus
                const playerId = parseInt(notificationIcon.dataset.playerId);
                this.openEmailModal(playerId);
                return; 
            }
    
            const attendanceItem = target.closest('.player-attendance-item');
            if (attendanceItem) {
                // If the click is on the link itself, allow default behavior (navigation)
                if (target.classList.contains('player-name-link')) {
                    return;
                }
                
                // Otherwise, cycle status
                this.cyclePlayerStatus(parseInt(attendanceItem.dataset.playerId));
            }
        }
    };

    app.init();
});
