document.addEventListener('DOMContentLoaded', () => {
    const app = {
        // STATE
        plan: {},
        players: [],
        drills: [],

        // DOM ELEMENTS
        elements: {
            appContainer: document.getElementById('session-planner-app'),
            attendanceList: document.getElementById('attendance-list'),
            unassignedPlayers: document.getElementById('unassigned-players'),
            sessionGroupsContainer: document.getElementById('session-groups-container'),
            timelineContainer: document.getElementById('timeline-container'),
            saveBtn: document.getElementById('save-plan-btn'),
            addPhaseModal: new bootstrap.Modal(document.getElementById('addPhaseModal')),
            addPhaseModalEl: document.getElementById('addPhaseModal'),
            activityModal: new bootstrap.Modal(document.getElementById('activityModal')),
            activityModalEl: document.getElementById('activityModal'),
            activityModalLabel: document.getElementById('activityModalLabel'),
            activityListContainer: document.getElementById('activity-list-container'),
            addActivityFormContainer: document.getElementById('add-activity-form-container'),
        },

        // RUNTIME STATE
        draggedElement: null,
        sessionStartTime: null,
        activeContext: { phaseId: null, courtId: null },

        // --- APPLICATION FLOW ---

        init() {
            console.log("Session Planner Initializing (Phase-Based)...");
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

            this.addEventListeners();
            this.render();
            console.log("Planner setup complete. UI should be interactive.");
        },

        render() {
            this.renderAttendanceList();
            this.renderGroupingSection();
            this.renderTimeline();
        },

        addEventListeners() {
            this.elements.appContainer.addEventListener('click', this.handleAppClick.bind(this));
            this.elements.appContainer.addEventListener('change', this.handleAppChange.bind(this));
            this.elements.appContainer.addEventListener('dragstart', this.handleDragStart.bind(this));
            this.elements.appContainer.addEventListener('dragend', this.handleDragEnd.bind(this));
            this.elements.appContainer.addEventListener('dragover', this.handleDragOver.bind(this));
            this.elements.appContainer.addEventListener('dragleave', this.handleDragLeave.bind(this));
            this.elements.appContainer.addEventListener('drop', this.handleDrop.bind(this));

            this.elements.addPhaseModalEl.addEventListener('click', e => {
                const phaseType = e.target.dataset.phaseType || e.target.closest('[data-phase-type]')?.dataset.phaseType;
                if (phaseType) this.addPhase(phaseType);
            });

            this.elements.activityModalEl.addEventListener('submit', this.handleActivityFormSubmit.bind(this));
        },

        // --- RENDERING ---

        renderAttendanceList() {
            const container = this.elements.attendanceList;
            if (!container) return;
            container.innerHTML = '';
            this.players.forEach(player => {
                const badgeClass = player.status === 'ATTENDING' ? 'text-bg-success' : player.status === 'DECLINED' ? 'text-bg-danger' : 'text-bg-secondary';
                container.innerHTML += `
                    <div class="player-attendance-item d-flex justify-content-between align-items-center mb-2">
                        <span>${player.name}</span>
                        <button class="btn btn-sm badge rounded-pill ${badgeClass}" data-player-id="${player.id}" title="Click to cycle status">${player.status}</button>
                    </div>`;
            });
        },

        renderGroupingSection() {
            if (!this.elements.unassignedPlayers || !this.elements.sessionGroupsContainer) return;
            this.elements.unassignedPlayers.innerHTML = '';
            const confirmedPlayers = this.players.filter(p => p.status === 'ATTENDING');
            const assignedPlayerIds = new Set(this.plan.playerGroups.flatMap(g => g.player_ids));
            
            confirmedPlayers.forEach(player => {
                if (!assignedPlayerIds.has(player.id)) {
                    this.elements.unassignedPlayers.appendChild(this.createPlayerCard(player));
                }
            });

            this.elements.sessionGroupsContainer.innerHTML = '';
            this.plan.playerGroups.forEach(group => {
                const groupCol = document.createElement('div');
                groupCol.className = 'col-lg-4 col-md-6 mb-3';
                groupCol.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <h6>${group.name} (${group.player_ids.length})</h6>
                        <button class="btn btn-sm btn-outline-danger remove-group-btn" data-group-id="${group.id}" title="Remove Group">&times;</button>
                    </div>
                    <div class="group-container" data-group-id="${group.id}"></div>`;
                const groupContainer = groupCol.querySelector('.group-container');
                group.player_ids.forEach(playerId => {
                    const player = this.players.find(p => p.id === playerId);
                    if (player) groupContainer.appendChild(this.createPlayerCard(player));
                });
                this.elements.sessionGroupsContainer.appendChild(groupCol);
            });
            
            const addGroupCol = document.createElement('div');
            addGroupCol.className = 'col-lg-4 col-md-6 mb-3 d-flex align-items-center justify-content-center';
            addGroupCol.innerHTML = `<button class="btn btn-secondary w-100 add-group-btn"><i class="bi bi-plus-lg"></i> Add Group</button>`;
            this.elements.sessionGroupsContainer.appendChild(addGroupCol);
        },

        renderTimeline() {
            const container = this.elements.timelineContainer;
            if (!container) return;
            container.innerHTML = '';
            let cumulativeTime = 0;

            (this.plan.timeline || []).forEach(phase => {
                const phaseEl = this.renderPhase(phase, cumulativeTime);
                container.appendChild(phaseEl);
                cumulativeTime += phase.duration;
            });

            container.innerHTML += `
                <div id="add-phase-btn-container">
                    <button class="btn btn-secondary" data-bs-toggle="modal" data-bs-target="#addPhaseModal">
                        <i class="bi bi-plus-lg"></i> Add New Phase
                    </button>
                </div>`;
        },

        renderPhase(phase, startTimeOffset) {
            const phaseEl = document.createElement('div');
            const isOpen = phase.isOpen === false ? '' : 'is-open'; // Default to open
            phaseEl.className = `planner-section phase-block ${isOpen} type-${phase.type.toLowerCase()}`;
            phaseEl.dataset.phaseId = phase.id;

            const phaseStartTime = this.minutesToTimeStr(startTimeOffset);
            const phaseEndTime = this.minutesToTimeStr(startTimeOffset + phase.duration);
            
            phaseEl.innerHTML = `
                <div class="planner-header">
                    <h4><i class="bi bi-grip-vertical"></i> ${phase.type}</h4>
                    <div class="d-flex align-items-center gap-3">
                        <span class="text-muted small">${phaseStartTime} - ${phaseEndTime}</span>
                        <button class="btn btn-sm btn-outline-danger delete-phase-btn" data-phase-id="${phase.id}" title="Delete Phase">&times;</button>
                        <i class="bi bi-chevron-down arrow"></i>
                    </div>
                </div>
                <div class="planner-content">
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Phase Name</label>
                            <input type="text" class="form-control phase-name-input" data-phase-id="${phase.id}" value="${phase.name}">
                        </div>
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Duration (minutes)</label>
                            <input type="number" class="form-control phase-duration-input" data-phase-id="${phase.id}" value="${phase.duration}" min="5" step="5">
                        </div>
                    </div>
                    <hr>
                    <div class="phase-content-body">${this.getPhaseContentHTML(phase)}</div>
                </div>`;
            return phaseEl;
        },

        getPhaseContentHTML(phase) {
            const groupChipsHTML = this.plan.playerGroups
                .filter(g => g.player_ids.length > 0)
                .map(g => this.createGroupChip(g, false, phase.id, null).outerHTML)
                .join('');

            const content = `<div class="d-flex flex-wrap gap-2 mb-4 group-chip-palette">${groupChipsHTML}</div>`;

            if (phase.type === 'Rotation') {
                return content + this.getRotationPhaseContentHTML(phase);
            }
            return content + this.getStandardPhaseContentHTML(phase);
        },

        getStandardPhaseContentHTML(phase) {
            let courtsHTML = '<div class="courts-grid">';
            if (phase.courts) {
                phase.courts.forEach(court => {
                    const assignedGroupsHTML = (court.assignedGroupIds || [])
                        .map(gid => {
                            const group = this.plan.playerGroups.find(g => g.id === gid);
                            return group ? this.createGroupChip(group, true, phase.id, court.id).outerHTML : '';
                        }).join('');

                    courtsHTML += `
                        <div class="court-container" data-court-id="${court.id}" data-phase-id="${phase.id}">
                            <div class="d-flex justify-content-between align-items-center">
                                <div class="court-name">${court.name}</div>
                                <button class="btn-close btn-sm remove-court-btn" data-court-id="${court.id}" data-phase-id="${phase.id}" title="Remove Court"></button>
                            </div>
                            <div class="assigned-groups-container mt-2">${assignedGroupsHTML}</div>
                        </div>`;
                });
            }
            courtsHTML += `
                <button class="btn btn-outline-secondary btn-sm add-court-btn" data-phase-id="${phase.id}">
                    <i class="bi bi-plus-lg"></i> Add Court
                </button></div>`;
            return courtsHTML;
        },

        getRotationPhaseContentHTML(phase) {
            let html = `
                <h6>Rotation Courts</h6>
                <p class="text-muted small">Groups assigned to any court below will be included in the rotation.</p>
                ${this.getStandardPhaseContentHTML(phase)}
                <hr class="my-4">
                <h6>Rotation Schedule <span class="badge bg-secondary">${phase.rotationDuration || 0} min rotations</span></h6>`;

            if (phase.sub_blocks && phase.sub_blocks.length > 0) {
                html += '<div class="vstack gap-2">';
                phase.sub_blocks.forEach(block => {
                    let assignmentsHTML = '';
                    for (const [courtId, groupId] of Object.entries(block.assignments)) {
                        const court = (phase.courts || []).find(c => c.id === courtId);
                        const group = this.plan.playerGroups.find(g => g.id === groupId);
                        if (court && group) {
                            assignmentsHTML += `<span class="badge text-bg-light me-2">${court.name}: ${group.name}</span>`;
                        }
                    }
                    html += `
                        <div class="p-2 bg-light border rounded">
                            <strong>${block.startTime} - ${block.endTime}:</strong> ${assignmentsHTML}
                        </div>`;
                });
                html += '</div>';
            } else {
                html += '<p class="text-muted">The rotation schedule will appear here once courts are added and groups are assigned to them.</p>';
            }
            return html;
        },

        renderActivityModalContent() {
            const { phase, court } = this.getActiveContext();
            if (!phase || !court) return;

            const groupNames = (court.assignedGroupIds || [])
                .map(gid => this.plan.playerGroups.find(g => g.id === gid)?.name || '')
                .join(', ');

            this.elements.activityModalLabel.textContent = `Activities for ${groupNames || 'Group'} on ${court.name}`;

            const listContainer = this.elements.activityListContainer;
            listContainer.innerHTML = '';
            if (!court.activities || court.activities.length === 0) {
                listContainer.innerHTML = '<p class="text-muted">No activities planned for this block yet.</p>';
            } else {
                const ul = document.createElement('ul');
                ul.className = 'list-group';
                court.activities.forEach((activity, index) => {
                    const li = document.createElement('li');
                    li.className = 'list-group-item d-flex justify-content-between align-items-center';
                    li.innerHTML = `
                        <span>${activity.name}</span>
                        <div>
                            <span class="badge bg-secondary me-2">${activity.duration} min</span>
                            <button type="button" class="btn btn-sm btn-outline-danger remove-activity-btn" data-index="${index}">&times;</button>
                        </div>`;
                    ul.appendChild(li);
                });
                listContainer.appendChild(ul);
            }

            const formContainer = this.elements.addActivityFormContainer;
            formContainer.innerHTML = `
                <form id="add-activity-form">
                    <h6 class="mt-4">Add New Activity</h6>
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
                        <button type="submit" class="btn btn-primary w-100">Add to Plan</button>
                    </div>
                </form>
            `;
            this.updateActivityNameInput();
            formContainer.querySelector('#activity-type').addEventListener('change', () => this.updateActivityNameInput());
        },

        updateActivityNameInput() {
            const type = document.getElementById('activity-type')?.value;
            const container = document.getElementById('activity-name-container');
            if (!type || !container) return;

            if (type === 'drill') {
                const options = this.drills.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
                container.innerHTML = `<label for="drill-select" class="form-label">Select Drill</label><select id="drill-select" class="form-select">${options}</select>`;
            } else {
                container.innerHTML = `<label for="custom-activity-name" class="form-label">Custom Activity Name</label><input type="text" id="custom-activity-name" class="form-control" placeholder="e.g., Forehand boasts" required>`;
            }
        },

        // --- LOGIC & ACTIONS ---

        calculateAndApplyRotations(phaseId) {
            const phase = this.plan.timeline.find(p => p.id === phaseId);
            if (!phase || phase.type !== 'Rotation' || !phase.courts) return;

            const assignedGroupIds = new Set((phase.courts || []).flatMap(c => c.assignedGroupIds || []));
            const groupsInRotation = this.plan.playerGroups.filter(g => assignedGroupIds.has(g.id));
            const courtsInRotation = phase.courts;

            if (groupsInRotation.length === 0 || courtsInRotation.length === 0) {
                phase.sub_blocks = [];
                phase.rotationDuration = 0;
                return;
            }

            const numRotations = Math.max(groupsInRotation.length, courtsInRotation.length);
            const rotationDuration = numRotations > 0 ? Math.floor(phase.duration / numRotations) : 0;
            phase.rotationDuration = rotationDuration;

            let phaseStartTimeOffset = 0;
            for (const p of this.plan.timeline) {
                if (p.id === phaseId) break;
                phaseStartTimeOffset += p.duration;
            }

            const newSubBlocks = [];
            let cumulativeTimeInPhase = 0;
            for (let i = 0; i < numRotations; i++) {
                if (rotationDuration <= 0) continue;
                const assignments = {};
                for (let j = 0; j < groupsInRotation.length; j++) {
                    const group = groupsInRotation[j];
                    const courtIndex = (j + i) % courtsInRotation.length;
                    const court = courtsInRotation[courtIndex];
                    if (court) {
                        assignments[court.id] = group.id;
                    }
                }

                newSubBlocks.push({
                    startTime: this.minutesToTimeStr(phaseStartTimeOffset + cumulativeTimeInPhase),
                    endTime: this.minutesToTimeStr(phaseStartTimeOffset + cumulativeTimeInPhase + rotationDuration),
                    assignments: assignments
                });
                cumulativeTimeInPhase += rotationDuration;
            }
            phase.sub_blocks = newSubBlocks;
        },

        addPhase(type) {
            const newPhase = {
                id: `phase_${Date.now()}`, type: type, name: type,
                duration: 15, courts: [], isOpen: true,
            };
            if (type === 'Rotation') {
                newPhase.sub_blocks = [];
                newPhase.rotationDuration = 15;
            }
            this.plan.timeline.push(newPhase);
            this.elements.addPhaseModal.hide();
            this.render();
        },
        deletePhase(phaseId) {
            this.plan.timeline = this.plan.timeline.filter(p => p.id !== phaseId);
            this.render();
        },
        addCourtToPhase(phaseId) {
            const phase = this.plan.timeline.find(p => p.id === phaseId);
            if (!phase) return;
            if (!phase.courts) phase.courts = [];
            const newCourtNum = phase.courts.length + 1;
            phase.courts.push({
                id: `court_${Date.now()}`, name: `Court ${newCourtNum}`,
                assignedGroupIds: [], activities: []
            });
            this.calculateAndApplyRotations(phaseId);
            this.render();
        },
        removeCourtFromPhase(phaseId, courtId) {
            const phase = this.plan.timeline.find(p => p.id === phaseId);
            if (!phase || !phase.courts) return;
            phase.courts = phase.courts.filter(c => c.id !== courtId);
            this.calculateAndApplyRotations(phaseId);
            this.render();
        },
        addNewGroup() {
            const newGroupLetter = String.fromCharCode(65 + this.plan.playerGroups.length);
            this.plan.playerGroups.push({ id: `group${Date.now()}`, name: `Group ${newGroupLetter}`, player_ids: [] });
            this.render();
        },
        removeGroup(groupId) {
            this.plan.playerGroups = this.plan.playerGroups.filter(g => g.id !== groupId);
            this.plan.timeline.forEach(phase => {
                (phase.courts || []).forEach(court => {
                    court.assignedGroupIds = (court.assignedGroupIds || []).filter(id => id !== groupId);
                });
                this.calculateAndApplyRotations(phase.id);
            });
            this.render();
        },

        cyclePlayerStatus(playerId) {
            const player = this.players.find(p => p.id === playerId);
            if (!player) return;
            const statusOrder = ['PENDING', 'ATTENDING', 'DECLINED'];
            player.status = statusOrder[(statusOrder.indexOf(player.status) + 1) % statusOrder.length];
            this.render();

            const sessionId = this.elements.appContainer.dataset.sessionId;
            const csrfToken = document.querySelector('form#logout-form [name=csrfmiddlewaretoken]')?.value || '';
            fetch(`/schedule/api/session/${sessionId}/update_attendance/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ player_id: playerId, status: player.status }),
            }).catch(error => console.error("Error saving attendance:", error));
        },

        savePlan() {
            const btn = this.elements.saveBtn;
            const url = this.elements.appContainer.dataset.saveUrl;
            const csrfToken = document.querySelector('form#logout-form [name=csrfmiddlewaretoken]')?.value || '';
            btn.innerHTML = '<i class="bi bi-arrow-repeat"></i> Saving...';
            btn.disabled = true;

            fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify(this.plan)
            }).then(response => response.json()).then(data => {
                btn.innerHTML = data.status === 'success' ? '<i class="bi bi-check-lg"></i> Saved!' : '<i class="bi bi-exclamation-triangle-fill"></i> Error';
            }).catch(error => {
                console.error('Error saving plan:', error);
                btn.innerHTML = '<i class="bi bi-exclamation-triangle-fill"></i> Error';
            }).finally(() => {
                setTimeout(() => {
                    btn.innerHTML = '<i class="bi bi-save-fill"></i> Save Plan';
                    btn.disabled = false;
                }, 2000);
            });
        },

        openActivityModal(phaseId, courtId) {
            this.activeContext = { phaseId, courtId };
            this.renderActivityModalContent();
            this.elements.activityModal.show();
        },

        removeActivity(index) {
            const { court } = this.getActiveContext();
            if (court && court.activities) {
                court.activities.splice(index, 1);
                this.renderActivityModalContent();
            }
        },

        // --- EVENT HANDLERS ---
        handleAppClick(e) {
            const target = e.target;
            
            // Priority 1: Handle specific button clicks first.
            const button = target.closest('button');
            if (button) {
                 if (button.matches('.remove-activity-btn')) {
                    this.removeActivity(parseInt(button.dataset.index, 10));
                    return; // Stop processing
                }
                if (button.closest('.planner-header')) { // It's a button inside a header
                    if (button.matches('.delete-phase-btn')) {
                        if (confirm('Delete this phase?')) {
                           this.deletePhase(button.dataset.phaseId);
                        }
                    }
                    return; // Stop further processing for clicks in the header
                }
                 if (button.matches('.player-attendance-item button')) this.cyclePlayerStatus(parseInt(button.dataset.playerId));
                else if (button.matches('.add-group-btn')) this.addNewGroup();
                else if (button.matches('.remove-group-btn')) { if (confirm('Are you sure?')) this.removeGroup(button.dataset.groupId); }
                else if (button.matches('.add-court-btn')) this.addCourtToPhase(button.dataset.phaseId);
                else if (button.matches('.remove-court-btn')) this.removeCourtFromPhase(button.dataset.phaseId, button.dataset.courtId);
                else if (button.id === 'save-plan-btn') this.savePlan();
                return;
            }

            // Priority 2: Handle click on an assigned group chip to open modal
            const assignedChip = target.closest('.group-chip.is-assigned');
            if (assignedChip) {
                this.openActivityModal(assignedChip.dataset.phaseId, assignedChip.dataset.courtId);
                return;
            }

            // Priority 3: Handle click on a header to toggle the accordion
            const header = target.closest('.planner-header');
            if (header) {
                const section = header.parentElement;
                if (section.matches('.planner-section')) {
                    section.classList.toggle('is-open');
                    if (section.matches('.phase-block')) {
                        const phase = this.plan.timeline.find(p => p.id === section.dataset.phaseId);
                        if (phase) phase.isOpen = section.classList.contains('is-open');
                    }
                }
            }
        },

        handleAppChange(e) {
            const target = e.target;
            const phaseId = target.dataset.phaseId;
            if (!phaseId) return;
            const phase = this.plan.timeline.find(p => p.id === phaseId);
            if (!phase) return;

            if (target.matches('.phase-name-input')) {
                phase.name = target.value;
            } else if (target.matches('.phase-duration-input')) {
                phase.duration = parseInt(target.value, 10) || 0;
            }
            this.calculateAndApplyRotations(phaseId);
            this.render();
        },

        handleActivityFormSubmit(e) {
            e.preventDefault();
            if (e.target.id !== 'add-activity-form') return;

            const { court } = this.getActiveContext();
            if (!court) return;

            const type = document.getElementById('activity-type').value;
            const duration = parseInt(document.getElementById('activity-duration').value, 10);
            let name, drillId = null;

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

            if (!court.activities) court.activities = [];
            court.activities.push({ name: name, drill_id: drillId, duration: duration });

            this.renderActivityModalContent();
        },

        handleDragStart(e) {
            const target = e.target;
            if (target.matches('.player-card')) {
                this.draggedElement = { type: 'player', id: parseInt(target.dataset.playerId) };
                target.classList.add('dragging');
            } else if (target.matches('.group-chip') && target.draggable) {
                this.draggedElement = { type: 'group', id: target.dataset.groupId };
                target.classList.add('dragging');
            }
        },
        handleDragEnd(e) {
            this.draggedElement = null;
            document.querySelectorAll('.dragging, .drag-over').forEach(el => el.classList.remove('dragging', 'drag-over'));
        },
        handleDragOver(e) {
            e.preventDefault();
            const dropTarget = e.target.closest('.group-container, .player-list, .court-container');
            if (dropTarget) dropTarget.classList.add('drag-over');
        },
        handleDragLeave(e) {
            e.target.closest('.group-container, .player-list, .court-container')?.classList.remove('drag-over');
        },
        handleDrop(e) {
            e.preventDefault();
            if (!this.draggedElement) return;
            const dropTarget = e.target.closest('.group-container, .player-list, .court-container');
            if (!dropTarget) return;
            dropTarget.classList.remove('drag-over');

            if (this.draggedElement.type === 'player') {
                const targetGroupId = dropTarget.dataset.groupId;
                this.plan.playerGroups.forEach(g => { g.player_ids = g.player_ids.filter(id => id !== this.draggedElement.id); });
                if (targetGroupId) {
                    const targetGroup = this.plan.playerGroups.find(g => g.id === targetGroupId);
                    if (targetGroup) targetGroup.player_ids.push(this.draggedElement.id);
                }
                this.render();
            } else if (this.draggedElement.type === 'group') {
                const phaseId = dropTarget.dataset.phaseId;
                const courtId = dropTarget.dataset.courtId;
                const phase = this.plan.timeline.find(p => p.id === phaseId);
                const court = phase ? (phase.courts || []).find(c => c.id === courtId) : null;
                if (court) {
                    if (!court.assignedGroupIds) court.assignedGroupIds = [];
                    if (!court.assignedGroupIds.includes(this.draggedElement.id)) {
                        court.assignedGroupIds.push(this.draggedElement.id);
                    }
                    this.calculateAndApplyRotations(phaseId);
                    this.render();
                }
            }
        },

        // --- UTILITY ---
        minutesToTimeStr(minutes) {
            if (typeof this.sessionStartTime !== 'string' || !this.sessionStartTime.includes(':')) return '00:00';
            const [startHours, startMinutes] = this.sessionStartTime.split(':').map(Number);
            const totalStartMinutes = startHours * 60 + startMinutes;
            const newTotalMinutes = totalStartMinutes + minutes;
            const h = Math.floor(newTotalMinutes / 60) % 24;
            const m = newTotalMinutes % 60;
            return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
        },
        createPlayerCard(player) {
            const card = document.createElement('div');
            card.className = 'player-card';
            card.draggable = true;
            card.dataset.playerId = player.id;
            card.dataset.type = 'player';
            card.textContent = player.name;
            return card;
        },
        createGroupChip(group, isAssigned = false, phaseId = null, courtId = null) {
            const chip = document.createElement('div');
            chip.className = 'group-chip';
            chip.dataset.groupId = group.id;
            chip.innerHTML = `<i class="bi bi-people-fill me-2"></i> ${group.name} (${group.player_ids.length})`;

            if (isAssigned) {
                chip.classList.add('is-assigned');
            } else {
                chip.draggable = true;
                chip.dataset.type = 'group';
            }
            chip.dataset.phaseId = phaseId;
            chip.dataset.courtId = courtId;
            return chip;
        },
        getActiveContext() {
            const phase = this.plan.timeline.find(p => p.id === this.activeContext.phaseId);
            const court = phase ? (phase.courts || []).find(c => c.id === this.activeContext.courtId) : null;
            return { phase, court };
        },
    };

    app.init();
});