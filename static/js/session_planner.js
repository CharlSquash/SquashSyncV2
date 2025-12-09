document.addEventListener('DOMContentLoaded', () => {
    const app = {
        // STATE
        allPlayersForDisplay: [],

        // DOM ELEMENTS
        elements: {
            appContainer: document.getElementById('session-planner-app'),
            attendanceList: document.getElementById('attendance-list'),
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
        },

        // --- RENDERING FUNCTIONS ---

        renderAttendanceList() {
            const container = this.elements.attendanceList;
            if (!container) return;
            container.innerHTML = '';
            this.allPlayersForDisplay.sort((a, b) => a.name.localeCompare(b.name));
            
            this.allPlayersForDisplay.forEach(player => {
                const badgeClass = player.status === 'ATTENDING' ? 'text-bg-success' : player.status === 'DECLINED' ? 'text-bg-danger' : 'text-bg-secondary';
                
                container.innerHTML += `
                    <div class="player-attendance-item" data-player-id="${player.id}" title="Click to cycle status">
                        <a href="/players/${player.id}/" class="player-name-link">${player.name}</a>
                        <span class="badge rounded-pill ${badgeClass}">${player.status}</span>
                    </div>`;
            });
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

        // --- EVENT HANDLERS ---
        
        handleAppClick(e) {
            const target = e.target;
    
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
