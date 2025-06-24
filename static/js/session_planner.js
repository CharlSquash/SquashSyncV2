// static/js/session_planner.js

document.addEventListener('DOMContentLoaded', () => {
    // --- STATE MANAGEMENT ---
    const app = {
        // Initialize state with default empty values
        plan: {}, players: [], drills: [],
        
        elements: {
            appContainer: document.getElementById('session-planner-app'),
            setupSection: document.getElementById('setup-section'),
            groupingSection: document.getElementById('grouping-section'),
            timelineSection: document.getElementById('timeline-section'),
            attendanceList: document.getElementById('attendance-list'),
            unassignedPlayers: document.getElementById('unassigned-players'),
            sessionGroupsContainer: document.getElementById('session-groups-container'),
            timelineContainer: document.getElementById('timeline-container'),
            saveBtn: document.getElementById('save-plan-btn'),
            structureControls: document.getElementById('structure-controls'),
            activityModal: new bootstrap.Modal(document.getElementById('activityModal')),
            activityModalLabel: document.getElementById('activityModalLabel'),
            activityListContainer: document.getElementById('activity-list-container'),
            addActivityFormContainer: document.getElementById('add-activity-form-container'),
        },
        
        draggedElement: null,
        sessionStartTime: null,
        sessionDuration: null,
        activeCourtId: null,

        // --- APPLICATION METHODS ---
        init() {
            console.log("Session Planner Initializing...");
            try {
                this.plan = JSON.parse(document.getElementById('plan-data').textContent);
                this.players = JSON.parse(document.getElementById('players-data').textContent);
                this.drills = JSON.parse(document.getElementById('drills-data').textContent);
            } catch (e) {
                console.error("Fatal Error: Could not parse data from Django.", e);
                this.elements.appContainer.innerHTML = `<div class="alert alert-danger"><h4>Application Error</h4><p>Could not load session data.</p></div>`;
                return;
            }
            this.sessionStartTime = this.elements.appContainer.dataset.sessionStartTime;
            this.sessionDuration = parseInt(this.elements.appContainer.dataset.sessionDuration, 10);
            
            this.addEventListeners();
            this.updateTimelineBlocks();
            this.render();

            this.elements.setupSection.classList.add('is-open');
            this.elements.groupingSection.classList.add('is-open');
            this.elements.timelineSection.classList.add('is-open');
        },

        render() {
            this.renderAttendanceList();
            this.renderSetupControls();
            this.renderGroupingSection();
            this.renderTimelineSection();
        },

        // --- RENDER FUNCTIONS ---
        renderAttendanceList() {
            this.elements.attendanceList.innerHTML = '';
            if (this.players.length === 0) {
                this.elements.attendanceList.innerHTML = '<p class="text-muted">No players in this group.</p>';
                return;
            }
            this.players.forEach(player => {
                const playerEl = document.createElement('div');
                playerEl.className = 'player-attendance-item d-flex justify-content-between align-items-center mb-2';
                let badgeClass = 'text-bg-secondary';
                if (player.status === 'ATTENDING') badgeClass = 'text-bg-success';
                if (player.status === 'DECLINED') badgeClass = 'text-bg-danger';
                playerEl.innerHTML = `
                    <span>${player.name}</span>
                    <button class="btn btn-sm badge rounded-pill ${badgeClass}" data-player-id="${player.id}" title="Click to cycle status">
                        ${player.status}
                    </button>
                `;
                this.elements.attendanceList.appendChild(playerEl);
            });
        },

        renderSetupControls() {
            const el = this.elements.structureControls;
            el.innerHTML = '';
            const rotationGroup = document.createElement('div');
            rotationGroup.className = 'mb-3';
            rotationGroup.innerHTML = `<label for="rotation-duration" class="form-label">Rotation Duration (minutes)</label><input type="number" class="form-control" id="rotation-duration" value="${this.plan.rotationDuration}">`;
            el.appendChild(rotationGroup);
            rotationGroup.querySelector('#rotation-duration').addEventListener('change', (e) => {
                const newDuration = parseInt(e.target.value, 10);
                if (newDuration > 0) {
                    this.plan.rotationDuration = newDuration;
                    this.updateTimelineBlocks();
                    this.render();
                }
            });
        },

        renderGroupingSection() {
            this.elements.unassignedPlayers.innerHTML = '';
            const confirmedPlayers = this.players.filter(p => p.status === 'ATTENDING');
            const assignedPlayerIds = new Set(this.plan.playerGroups.flatMap(g => g.player_ids));
            confirmedPlayers.forEach(player => {
                if (!assignedPlayerIds.has(player.id)) {
                    const card = this.createPlayerCard(player);
                    this.elements.unassignedPlayers.appendChild(card);
                }
            });

            this.elements.sessionGroupsContainer.innerHTML = '';
            this.plan.playerGroups.forEach(group => {
                const groupCol = document.createElement('div');
                groupCol.className = 'col-md-4 mb-3';
                groupCol.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <h6>${group.name} (${group.player_ids.length})</h6>
                        <button class="btn btn-sm btn-outline-danger remove-group-btn" data-group-id="${group.id}" title="Remove Group">&times;</button>
                    </div>
                    <div class="group-container" data-group-id="${group.id}"></div>
                `;
                const groupContainer = groupCol.querySelector('.group-container');
                group.player_ids.forEach(playerId => {
                    const player = this.players.find(p => p.id === playerId);
                    if (player) {
                        const card = this.createPlayerCard(player);
                        groupContainer.appendChild(card);
                    }
                });
                this.elements.sessionGroupsContainer.appendChild(groupCol);
            });
            
            const addGroupCol = document.createElement('div');
            addGroupCol.className = 'col-md-4 mb-3 d-flex align-items-center justify-content-center';
            addGroupCol.innerHTML = `<button class="btn btn-secondary w-100" id="add-group-btn"><i class="bi bi-plus-lg"></i> Add Group</button>`;
            this.elements.sessionGroupsContainer.appendChild(addGroupCol);
        },
        
        renderTimelineSection() {
            const container = this.elements.timelineContainer;
            container.innerHTML = '';
            const groupChipsContainer = document.createElement('div');
            groupChipsContainer.className = 'd-flex flex-wrap gap-2 mb-4 group-chip-palette';
            this.plan.playerGroups.forEach(group => {
                if (group.player_ids.length > 0) {
                    const chip = this.createGroupChip(group);
                    groupChipsContainer.appendChild(chip);
                }
            });
            container.appendChild(groupChipsContainer);
            this.plan.timeline.forEach((block, blockIndex) => {
                const blockEl = document.createElement('div');
                blockEl.className = 'timeline-block';
                blockEl.innerHTML = `<div class="timeline-block-header"><h5>${block.startTime} - ${block.endTime}</h5></div>`;
                const courtsContainer = document.createElement('div');
                courtsContainer.className = 'courts-grid';
                block.courts.forEach(court => {
                    const courtEl = document.createElement('div');
                    courtEl.className = 'court-container';
                    courtEl.dataset.courtId = court.id;
                    courtEl.innerHTML = `
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="court-name">${court.name}</div>
                            <button class="btn-close btn-sm remove-court-btn" data-court-id="${court.id}" title="Remove Court"></button>
                        </div>
                    `;
                    if (court.assignedGroupIds && court.assignedGroupIds.length > 0) {
                        const groupContainer = document.createElement('div');
                        groupContainer.className = 'assigned-groups-container mt-2';
                        court.assignedGroupIds.forEach(groupId => {
                            const assignedGroup = this.plan.playerGroups.find(g => g.id === groupId);
                            if (assignedGroup) {
                                const chip = this.createGroupChip(assignedGroup);
                                chip.classList.add('is-assigned');
                                chip.setAttribute('draggable', false);
                                chip.dataset.bsToggle = "modal";
                                chip.dataset.bsTarget = "#activityModal";
                                chip.dataset.courtId = court.id;
                                groupContainer.appendChild(chip);
                            }
                        });
                        courtEl.appendChild(groupContainer);
                    }
                    courtsContainer.appendChild(courtEl);
                });
                const addCourtBtn = document.createElement('button');
                addCourtBtn.className = 'btn btn-outline-secondary btn-sm add-court-btn';
                addCourtBtn.innerHTML = '<i class="bi bi-plus-lg"></i> Add Court';
                addCourtBtn.dataset.blockIndex = blockIndex;
                courtsContainer.appendChild(addCourtBtn);
                blockEl.appendChild(courtsContainer);
                container.appendChild(blockEl);
            });
        },

        renderActivityList(court) {
            const container = this.elements.activityListContainer;
            const groupNames = court.assignedGroupIds.map(gid => this.plan.playerGroups.find(g => g.id === gid)?.name || '').join(', ');
            this.elements.activityModalLabel.textContent = `Edit Activities for ${groupNames} on ${court.name}`;
            container.innerHTML = '';
            if (!court.activities || court.activities.length === 0) {
                container.innerHTML = '<p class="text-muted">No activities planned yet.</p>';
                return;
            }
            const list = document.createElement('ul');
            list.className = 'activity-list';
            court.activities.forEach((activity, index) => {
                const item = document.createElement('li');
                item.className = 'activity-item';
                item.innerHTML = `
                    <span>${activity.name}</span>
                    <div>
                        <span class="badge bg-secondary me-2">${activity.duration} min</span>
                        <button class="btn btn-sm btn-outline-danger" data-activity-index="${index}">&times;</button>
                    </div>
                `;
                item.querySelector('button').addEventListener('click', () => this.removeActivity(court, index));
                list.appendChild(item);
            });
            container.appendChild(list);
        },

        renderAddActivityForm() {
            const container = this.elements.addActivityFormContainer;
            container.innerHTML = `
                <form id="add-activity-form">
                    <div class="row g-2">
                        <div class="col-md-6">
                            <label for="activity-type" class="form-label">Activity Type</label>
                            <select id="activity-type" class="form-select">
                                <option value="drill" selected>Pre-defined Drill</option>
                                <option value="custom">Custom Activity</option>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label for="activity-duration" class="form-label">Duration (min)</label>
                            <input type="number" id="activity-duration" class="form-control" value="10" min="1">
                        </div>
                    </div>
                    <div class="mt-2" id="activity-name-container"></div>
                    <div class="mt-3">
                        <button type="submit" class="btn btn-primary w-100">Add Activity</button>
                    </div>
                </form>
            `;
            this.updateActivityNameInput();
            container.querySelector('#activity-type').addEventListener('change', () => this.updateActivityNameInput());
            container.querySelector('form').addEventListener('submit', (e) => this.handleActivityFormSubmit(e));
        },

        updateActivityNameInput() {
            const type = document.getElementById('activity-type').value;
            const container = document.getElementById('activity-name-container');
            if (type === 'drill') {
                const options = this.drills.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
                container.innerHTML = `<label for="drill-select" class="form-label">Select Drill</label><select id="drill-select" class="form-select">${options}</select>`;
            } else {
                container.innerHTML = `<label for="custom-activity-name" class="form-label">Custom Activity Name</label><input type="text" id="custom-activity-name" class="form-control" required>`;
            }
        },

        // --- UTILITY & HELPER FUNCTIONS ---
        createPlayerCard(player) {
            const card = document.createElement('div'); card.className = 'player-card'; card.setAttribute('draggable', 'true'); card.dataset.playerId = player.id; card.dataset.type = 'player'; card.textContent = player.name; return card;
        },
        createGroupChip(group) {
            const chip = document.createElement('div'); chip.className = 'group-chip'; chip.setAttribute('draggable', 'true'); chip.dataset.groupId = group.id; chip.dataset.type = 'group'; chip.innerHTML = `<i class="bi bi-people-fill me-2"></i> ${group.name} (${group.player_ids.length})`; return chip;
        },
        updateTimelineBlocks() {
            const newBlocks = []; let currentTime = 0; if (!this.sessionDuration || !this.plan.rotationDuration) return;
            while (currentTime < this.sessionDuration) {
                const blockEndTime = Math.min(currentTime + this.plan.rotationDuration, this.sessionDuration);
                const startTimeStr = this.minutesToTimeStr(currentTime);
                const existingBlock = this.plan.timeline.find(b => b.startTime === startTimeStr);
                
                const defaultCourts = [
                    {"id": `court1-${currentTime}`, "name": "Court 1", "assignedGroupIds": [], "activities": []},
                    {"id": `court2-${currentTime}`, "name": "Court 2", "assignedGroupIds": [], "activities": []}
                ];

                newBlocks.push({
                    startTime: startTimeStr,
                    endTime: this.minutesToTimeStr(blockEndTime),
                    courts: existingBlock ? existingBlock.courts : defaultCourts
                });
                currentTime += this.plan.rotationDuration;
            }
            this.plan.timeline = newBlocks;
        },
        minutesToTimeStr(minutes) {
            const [startHours, startMinutes] = this.sessionStartTime.split(':').map(Number); const totalStartMinutes = startHours * 60 + startMinutes; const newTotalMinutes = totalStartMinutes + minutes; const h = Math.floor(newTotalMinutes / 60) % 24; const m = newTotalMinutes % 60; return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
        },
        removeActivity(court, index) {
            court.activities.splice(index, 1);
            this.renderActivityList(court);
            this.renderTimelineSection();
        },
        handleActivityFormSubmit(event) {
            event.preventDefault();
            const type = document.getElementById('activity-type').value;
            const duration = parseInt(document.getElementById('activity-duration').value, 10);
            let name, drillId;
            if (type === 'drill') {
                const select = document.getElementById('drill-select');
                name = select.options[select.selectedIndex].text;
                drillId = parseInt(select.value, 10);
            } else {
                name = document.getElementById('custom-activity-name').value;
            }
            if (!name || !(duration > 0)) {
                alert("Please provide a valid name and duration.");
                return;
            }
            const court = this.findCourtById(this.activeCourtId);
            if (court) {
                if(!court.activities) court.activities = [];
                court.activities.push({ name: name, drill_id: drillId || null, duration: duration });
                this.renderActivityList(court);
                this.renderTimelineSection();
            }
        },
        findCourtById(courtId) {
            for (const block of this.plan.timeline) {
                const court = block.courts.find(c => c.id === courtId);
                if (court) return court;
            }
            return null;
        },
        addNewGroup() {
            const newGroupLetter = String.fromCharCode(65 + this.plan.playerGroups.length);
            const newGroup = {
                id: `group${Date.now()}`,
                name: `Group ${newGroupLetter}`,
                player_ids: []
            };
            this.plan.playerGroups.push(newGroup);
            this.renderGroupingSection();
        },
        removeGroup(groupId) {
            const groupToRemove = this.plan.playerGroups.find(g => g.id === groupId);
            if (!groupToRemove) return;
            this.plan.playerGroups = this.plan.playerGroups.filter(g => g.id !== groupId);
            this.plan.timeline.forEach(block => {
                block.courts.forEach(court => {
                    if (court.assignedGroupIds) {
                        court.assignedGroupIds = court.assignedGroupIds.filter(id => id !== groupId);
                    }
                });
            });
            this.renderGroupingSection();
            this.renderTimelineSection();
        },

        // --- EVENT LISTENERS ---
        addEventListeners() {
            this.addAccordionListeners();
            this.addDragAndDropListeners();
            this.addAttendanceListeners();
            this.addSaveListener();
            this.addModalListener();
            this.addTimelineControlsListeners();
            this.addGroupManagementListeners();
        },
        addAccordionListeners() {
            document.querySelectorAll('.planner-header').forEach(header => {
                header.addEventListener('click', () => {
                    header.parentElement.classList.toggle('is-open');
                });
            });
        },
        addDragAndDropListeners() {
            this.elements.appContainer.addEventListener('dragstart', e => { if (e.target.dataset.playerId) { this.draggedElement = { type: 'player', id: parseInt(e.target.dataset.playerId) }; e.target.classList.add('dragging'); } if (e.target.dataset.groupId && !e.target.classList.contains('is-assigned')) { this.draggedElement = { type: 'group', id: e.target.dataset.groupId }; e.target.classList.add('dragging'); } });
            this.elements.appContainer.addEventListener('dragend', e => { if (this.draggedElement) { e.target.classList.remove('dragging'); } this.draggedElement = null; });
            this.elements.appContainer.addEventListener('dragover', e => { e.preventDefault(); const dropTarget = e.target.closest('.group-container, .player-list, .court-container'); if (dropTarget) { dropTarget.classList.add('drag-over'); } });
            this.elements.appContainer.addEventListener('dragleave', e => { const dropTarget = e.target.closest('.group-container, .player-list, .court-container'); if (dropTarget) { dropTarget.classList.remove('drag-over'); } });
            this.elements.appContainer.addEventListener('drop', e => {
                e.preventDefault(); if (!this.draggedElement) return; const dropTarget = e.target.closest('.group-container, .player-list, .court-container'); if (!dropTarget) return; dropTarget.classList.remove('drag-over');
                if (this.draggedElement.type === 'player' && (dropTarget.classList.contains('group-container') || dropTarget.classList.contains('player-list'))) {
                    const targetGroupId = dropTarget.dataset.groupId; this.plan.playerGroups.forEach(g => { g.player_ids = g.player_ids.filter(id => id !== this.draggedElement.id); }); if (targetGroupId) { const targetGroup = this.plan.playerGroups.find(g => g.id === targetGroupId); if (targetGroup) targetGroup.player_ids.push(this.draggedElement.id); } this.renderGroupingSection(); this.renderTimelineSection();
                }
                if (this.draggedElement.type === 'group' && dropTarget.classList.contains('court-container')) {
                    const courtId = dropTarget.dataset.courtId;
                    const court = this.findCourtById(courtId);
                    if (court) {
                        if(!court.assignedGroupIds) court.assignedGroupIds = [];
                        if (!court.assignedGroupIds.includes(this.draggedElement.id)) {
                            court.assignedGroupIds.push(this.draggedElement.id);
                            this.renderTimelineSection();
                        }
                    }
                }
            });
        },
        addTimelineControlsListeners() {
            this.elements.timelineContainer.addEventListener('click', e => {
                if (e.target.classList.contains('add-court-btn')) {
                    const blockIndex = e.target.dataset.blockIndex;
                    const block = this.plan.timeline[blockIndex];
                    const newCourtNum = block.courts.length + 1;
                    block.courts.push({ id: `court${newCourtNum}-${Date.now()}`, name: `Court ${newCourtNum}`, assignedGroupIds: [], activities: [] });
                    this.renderTimelineSection();
                }
                if (e.target.classList.contains('remove-court-btn')) {
                    const courtId = e.target.dataset.courtId;
                    for (const block of this.plan.timeline) {
                        block.courts = block.courts.filter(c => c.id !== courtId);
                    }
                    this.renderTimelineSection();
                }
            });
        },
        addGroupManagementListeners() {
            // Use event delegation on the container for dynamically added buttons
            this.elements.sessionGroupsContainer.addEventListener('click', e => {
                if (e.target.id === 'add-group-btn') {
                    this.addNewGroup();
                }
                const removeBtn = e.target.closest('.remove-group-btn');
                if (removeBtn) {
                    const groupId = removeBtn.dataset.groupId;
                    if (confirm('Are you sure you want to remove this group? All players will be unassigned.')) {
                        this.removeGroup(groupId);
                    }
                }
            });
        },
        addAttendanceListeners() {
            this.elements.attendanceList.addEventListener('click', e => { const target = e.target; if (target.tagName === 'BUTTON' && target.dataset.playerId) { const playerId = parseInt(target.dataset.playerId); this.cyclePlayerStatus(playerId); } });
        },
        cyclePlayerStatus(playerId) {
            const player = this.players.find(p => p.id === playerId); if (!player) return; const statusOrder = ['PENDING', 'ATTENDING', 'DECLINED']; const currentIndex = statusOrder.indexOf(player.status); const nextIndex = (currentIndex + 1) % statusOrder.length; const newStatus = statusOrder[nextIndex]; player.status = newStatus; this.renderAttendanceList(); this.renderGroupingSection(); const sessionId = this.elements.appContainer.dataset.sessionId; const csrfToken = document.querySelector('form#logout-form [name=csrfmiddlewaretoken]').value; fetch(`/schedule/api/session/${sessionId}/update_attendance/`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }, body: JSON.stringify({ player_id: playerId, status: newStatus }), }).then(response => response.json()).then(data => { if (data.status !== 'success') { console.error("Failed to save attendance:", data.message); } }).catch(error => console.error("Error saving attendance:", error));
        },
        addSaveListener() {
            this.elements.saveBtn.addEventListener('click', () => { const url = this.elements.appContainer.dataset.saveUrl; const csrfToken = document.querySelector('form#logout-form [name=csrfmiddlewaretoken]').value; this.elements.saveBtn.innerHTML = '<i class="bi bi-arrow-repeat"></i> Saving...'; this.elements.saveBtn.disabled = true; fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }, body: JSON.stringify(this.plan) }).then(response => response.json()).then(data => { if (data.status === 'success') { this.elements.saveBtn.innerHTML = '<i class="bi bi-check-lg"></i> Saved!'; } else { this.elements.saveBtn.innerHTML = '<i class="bi bi-exclamation-triangle-fill"></i> Error'; } setTimeout(() => { this.elements.saveBtn.innerHTML = '<i class="bi bi-save-fill"></i> Save Plan'; this.elements.saveBtn.disabled = false; }, 2000); }).catch(error => { console.error('Error saving plan:', error); this.elements.saveBtn.innerHTML = '<i class="bi bi-exclamation-triangle-fill"></i> Error'; setTimeout(() => { this.elements.saveBtn.innerHTML = '<i class="bi bi-save-fill"></i> Save Plan'; this.elements.saveBtn.disabled = false; }, 3000); }); });
        },
        addModalListener() {
            document.getElementById('activityModal').addEventListener('show.bs.modal', (event) => {
                const chip = event.relatedTarget;
                this.activeCourtId = chip.dataset.courtId;
                const targetCourt = this.findCourtById(this.activeCourtId);
                if (targetCourt) {
                    this.renderActivityList(targetCourt);
                    this.renderAddActivityForm();
                }
            });
        }
    };
    
    app.init();
});
