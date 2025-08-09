document.addEventListener('DOMContentLoaded', () => {
    const app = {
        // STATE
        plan: {},
        players: [],
        drills: [],
        allTags: [],

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
        activityFilters: {
            primaryTagId: null,
            secondaryTagIds: new Set(),
        },

        // --- APPLICATION FLOW ---

        init() {
            console.log("Session Planner Initializing...");
            try {
                this.plan = JSON.parse(document.getElementById('plan-data').textContent);
                this.players = JSON.parse(document.getElementById('players-data').textContent);
                this.drills = JSON.parse(document.getElementById('drills-data').textContent);
                const allTagsData = document.getElementById('all-tags-data');
                if (allTagsData) {
                    this.allTags = JSON.parse(allTagsData.textContent);
                } else {
                    this.allTags = [];
                    console.warn("Warning: 'all-tags-data' script element not found.");
                }
            } catch (e) {
                console.error("Fatal Error: Could not parse data from Django.", e);
                this.elements.appContainer.innerHTML = `<div class="alert alert-danger"><h4>Application Error</h4><p>Could not load session data.</p></div>`;
                return;
            }
            this.sessionStartTime = this.elements.appContainer.dataset.sessionStartTime;

            this.addEventListeners();
            this.updateCourtsBasedOnGroups(true);
            this.render();
            console.log("Planner setup complete.");
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

        // --- RENDERING FUNCTIONS ---

        renderAttendanceList() {
            const container = this.elements.attendanceList;
            if (!container) return;
            container.innerHTML = '';
            this.players.forEach(player => {
                const badgeClass = player.status === 'ATTENDING' ? 'text-bg-success' : player.status === 'DECLINED' ? 'text-bg-danger' : 'text-bg-secondary';
                container.innerHTML += `
                    <div class="player-attendance-item" data-player-id="${player.id}" title="Click to cycle status">
                        <span class="player-name">${player.name}</span>
                        <span class="badge rounded-pill ${badgeClass}">${player.status}</span>
                    </div>`;
            });
        },

        renderGroupingSection() {
            if (!this.elements.unassignedPlayers || !this.elements.sessionGroupsContainer) return;
            this.elements.unassignedPlayers.innerHTML = '';
            const confirmedPlayers = this.players.filter(p => p.status === 'ATTENDING');
            const assignedPlayerIds = new Set((this.plan.playerGroups || []).flatMap(g => g.player_ids));

            confirmedPlayers.forEach(player => {
                if (!assignedPlayerIds.has(player.id)) {
                    this.elements.unassignedPlayers.appendChild(this.createPlayerCard(player));
                }
            });

            this.elements.sessionGroupsContainer.innerHTML = '';
            (this.plan.playerGroups || []).forEach(group => {
                const groupCol = document.createElement('div');
                groupCol.className = 'col-lg-4 col-md-6 mb-3';
                groupCol.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <h6>${group.name} (${group.player_ids.length})</h6>
                        <button class="btn btn-sm btn-outline-danger remove-group-btn" data-group-id="${group.id}" title="Remove Group">×</button>
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
            const isOpenClass = phase.isOpen === false ? '' : 'is-open';
            phaseEl.className = `planner-section phase-block ${isOpenClass} type-${phase.type.toLowerCase()}`;
            phaseEl.dataset.phaseId = phase.id;

            const phaseStartTime = this.minutesToTimeStr(startTimeOffset);
            const phaseEndTime = this.minutesToTimeStr(startTimeOffset + phase.duration);

            phaseEl.innerHTML = `
                <div class="planner-header">
                    <h4><i class="bi bi-grip-vertical"></i> ${phase.type}</h4>
                    <div class="d-flex align-items-center gap-3">
                        <span class="text-muted small">${phaseStartTime} - ${phaseEndTime}</span>
                        <button class="btn btn-sm btn-outline-danger delete-phase-btn" data-phase-id="${phase.id}" title="Delete Phase">×</button>
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

            const header = phaseEl.querySelector('.planner-header');
            if (header) {
                header.addEventListener('click', (e) => this.togglePhase(e, phase.id));
            }

            return phaseEl;
        },

        getPhaseContentHTML(phase) {
            if (phase.type === 'Rotation') {
                return this.getRotationPhaseContentHTML(phase);
            }
            return this.getStandardPhaseContentHTML(phase);
        },

        getStandardPhaseContentHTML(phase) {
            let courtsHTML = '<div class="courts-grid">';
            (phase.courts || []).forEach(court => {
                let assignedGroupsHTML = '';

                if (phase.type !== 'Rotation') {
                    assignedGroupsHTML = (court.assignedGroupIds || [])
                        .map(gid => {
                            const group = this.plan.playerGroups.find(g => g.id === gid);
                            return group ? `<span class="group-chip-assigned">${group.name}</span>` : '';
                        }).join(' ');
                }

                let activitiesHTML = '';
                if (court.activities && court.activities.length > 0) {
                    activitiesHTML = `
                        <div class="court-activities-container">
                            <ul class="court-activities-list list-unstyled mb-0">
                                ${court.activities.map(act => `
                                    <li class="court-activity-item">
                                        <span>${act.name}</span>
                                        <span class="badge bg-light text-dark">${act.duration}m</span>
                                    </li>`
                                ).join('')}
                            </ul>
                        </div>`;
                } else {
                    // --- THIS IS THE NEW PART ---
                    // If there are no activities, show a helpful prompt.
                    activitiesHTML = `
                        <div class="court-activities-placeholder">
                            <i class="bi bi-plus-circle-dotted"></i>
                            <span>Add Activities</span>
                        </div>
                    `;
                    // --- END OF NEW PART ---
                }

                courtsHTML += `
                    <div class="court-container court-clickable" data-court-id="${court.id}" data-phase-id="${phase.id}" title="Click to add or edit activities">
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="court-name">${court.name}</div>
                        </div>
                        <div class="assigned-groups-container mt-2">${assignedGroupsHTML}</div>
                        ${activitiesHTML}
                    </div>`;
            });
            courtsHTML += `</div>`;
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
            const { court } = this.getActiveContext();
            if (!court) return;

            const groupNames = (court.assignedGroupIds || [])
                .map(gid => this.plan.playerGroups.find(g => g.id === gid)?.name || '')
                .join(', ');

            this.elements.activityModalLabel.textContent = `Activities for ${groupNames || 'Group'} on ${court.name}`;

            this.renderActivityList();
            this.renderActivityForm();
        },

        renderActivityList() {
            const { court } = this.getActiveContext();
            const listContainer = this.elements.activityListContainer;
            listContainer.innerHTML = '';
            if (!court || !court.activities || court.activities.length === 0) {
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
                            <button type="button" class="btn btn-sm btn-outline-danger remove-activity-btn" data-index="${index}">×</button>
                        </div>`;
                    ul.appendChild(li);
                });
                listContainer.appendChild(ul);
            }
        },

        renderActivityForm() {
            const formContainer = this.elements.addActivityFormContainer;
            formContainer.innerHTML = `
                <form id="add-activity-form" novalidate>
                    <h6 class="mt-4">Add New Activity</h6>
                    ${this.buildFilterControlsHTML()} 
                    <div class="row g-2 mt-3 align-items-end">
                        <div class="col">
                            <label for="drill-select" class="form-label">Select Drill</label>
                            <select id="drill-select" class="form-select"></select>
                        </div>
                        <div class="col-auto">
                            <button type="button" class="btn btn-secondary preview-drill-btn" title="Preview Selected Drill">
                                <i class="bi bi-play-btn-fill"></i> Preview
                            </button>
                        </div>
                        <div class="col-md-3">
                            <label for="activity-duration" class="form-label">Duration (min)</label>
                            <input type="number" id="activity-duration" class="form-control" value="10" min="1">
                        </div>
                    </div>
                    <div id="youtube-preview-container" class="mt-3"></div>
                    <div class="mt-3">
                        <button type="submit" class="btn btn-primary w-100">Add to Plan</button>
                    </div>
                </form>
            `;
            this.renderFilteredDrillList();
            formContainer.querySelector('#primary-tag-filter').addEventListener('change', this.handleFilterChange.bind(this));
            formContainer.querySelectorAll('.secondary-tag-filter').forEach(el => {
                el.addEventListener('change', this.handleFilterChange.bind(this));
            });
            formContainer.querySelector('#drill-select').addEventListener('change', () => {
                document.getElementById('youtube-preview-container').innerHTML = '';
            });
            formContainer.querySelector('.preview-drill-btn').addEventListener('click', () => this.showYoutubePreview());
        },

        buildFilterControlsHTML() {
            if (!this.allTags || this.allTags.length === 0) return '';

            const { phase } = this.getActiveContext();
            const phaseTypeToTagName = {
                'Fun Games': 'Fun Games',
                'Rotation': 'Rotation Drill',
                'Fitness': 'Fitness'
            };
            const defaultTagName = phase ? phaseTypeToTagName[phase.type] || '' : '';
            const defaultTag = this.allTags.find(t => t.name === defaultTagName);
            this.activityFilters.primaryTagId = defaultTag ? defaultTag.id : null;

            const primaryOptions = this.allTags.map(tag =>
                `<option value="${tag.id}" ${tag.id === this.activityFilters.primaryTagId ? 'selected' : ''}>${tag.name}</option>`
            ).join('');

            const secondaryCheckboxes = this.allTags.map(tag => `
                <div class="form-check form-check-inline">
                    <input class="form-check-input secondary-tag-filter" type="checkbox" value="${tag.id}" id="tag-${tag.id}">
                    <label class="form-check-label" for="tag-${tag.id}">${tag.name}</label>
                </div>
            `).join('');

            return `
                <div class="row g-2">
                    <div class="col-md-6">
                        <label for="primary-tag-filter" class="form-label">Drill Category</label>
                        <select id="primary-tag-filter" class="form-select">
                            <option value="">All Drills</option>
                            ${primaryOptions}
                        </select>
                    </div>
                </div>
                <div class="mt-2">
                    <label class="form-label">Additional Filters</label>
                    <div class="border p-2 rounded" style="max-height: 100px; overflow-y: auto;">
                        ${secondaryCheckboxes}
                    </div>
                </div>
            `;
        },

        renderFilteredDrillList() {
            const selectEl = document.getElementById('drill-select');
            if (!selectEl) return;

            const { primaryTagId, secondaryTagIds } = this.activityFilters;

            const filteredDrills = this.drills.filter(drill => {
                const hasPrimaryTag = primaryTagId ? (drill.tag_ids || []).includes(primaryTagId) : true;
                const hasAllSecondaryTags = [...secondaryTagIds].every(tagId => (drill.tag_ids || []).includes(tagId));
                return hasPrimaryTag && hasAllSecondaryTags;
            });

            selectEl.innerHTML = filteredDrills.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
        },

        // --- LOGIC & ACTIONS ---

        showYoutubePreview() {
            const drillSelect = document.getElementById('drill-select');
            const previewContainer = document.getElementById('youtube-preview-container');
            if (!drillSelect || !previewContainer) return;

            if (!drillSelect.value) {
                previewContainer.innerHTML = `<p class="text-muted small mt-2">Please select a drill to preview.</p>`;
                return;
            }

            const drillId = parseInt(drillSelect.value);
            const drill = this.drills.find(d => d.id === drillId);

            if (drill && drill.youtube_link) {
                let videoId = null;
                const link = drill.youtube_link.trim();

                try {
                    const parts = link.split('/');
                    const potentialId = parts[parts.length - 1];
                    if (potentialId) {
                        videoId = potentialId;
                    }
                } catch (e) {
                    console.error("An error occurred while splitting the URL.", e);
                }

                if (videoId) {
                    previewContainer.innerHTML = `
                        <div class="youtube-preview-container">
                            <iframe src="https://www.youtube.com/embed/${videoId}" 
                                    frameborder="0" 
                                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                                    allowfullscreen>
                            </iframe>
                        </div>`;
                } else {
                     previewContainer.innerHTML = `<p class="text-danger small mt-2"><b>Error:</b> Could not extract a Video ID from the link. The URL appears to be malformed.</p>`;
                }
            } else {
                previewContainer.innerHTML = `<p class="text-muted small mt-2">No video preview available for this drill.</p>`;
            }
        },

        updateCourtsBasedOnGroups() {
            const groups = this.plan.playerGroups || [];
            const numGroups = groups.length;

            (this.plan.timeline || []).forEach(phase => {
                let targetCourtCount = 0;
                let autoAssign = false;

                // Define rules for each phase type
                if (phase.type === 'Warmup' || phase.type === 'Fitness') {
                    targetCourtCount = 1; // Always one court for Warmup and Fitness
                    autoAssign = true;
                } else if (phase.type === 'Rotation' || phase.type === 'Freeplay') {
                    targetCourtCount = numGroups > 0 ? numGroups : 1; // One court per group
                    autoAssign = true;
                }

                // Synchronize the number of courts
                let currentCourts = phase.courts || [];
                while (currentCourts.length < targetCourtCount) {
                    currentCourts.push({
                        id: `court_${Date.now()}_${currentCourts.length + 1}`,
                        name: `Court ${currentCourts.length + 1}`,
                        assignedGroupIds: [], activities: []
                    });
                }
                if (currentCourts.length > targetCourtCount) {
                    currentCourts.splice(targetCourtCount); // Remove extra courts
                }
                phase.courts = currentCourts;

                // Perform automatic group assignment
                if (autoAssign) {
                    if ((phase.type === 'Warmup' || phase.type === 'Fitness') && phase.courts.length > 0) {
                        // Assign all groups to the single court
                        phase.courts[0].assignedGroupIds = groups.map(g => g.id);
                    } else if (phase.type === 'Rotation' || phase.type === 'Freeplay') {
                        // Assign groups one-to-one to courts
                        for (let i = 0; i < phase.courts.length; i++) {
                            if (groups[i]) {
                                phase.courts[i].assignedGroupIds = [groups[i].id];
                            } else {
                                phase.courts[i].assignedGroupIds = [];
                            }
                        }
                    }
                }

                this.calculateAndApplyRotations(phase.id);
            });
        },

        calculateAndApplyRotations(phaseId) {
            const phase = this.plan.timeline.find(p => p.id === phaseId);
            if (!phase || phase.type !== 'Rotation') return;

            const courtsInRotation = phase.courts || [];
            const initialGroupOrder = courtsInRotation
                .map(c => (c.assignedGroupIds && c.assignedGroupIds.length > 0) ? c.assignedGroupIds[0] : null)
                .filter(Boolean); 

            if (initialGroupOrder.length === 0 || courtsInRotation.length === 0 || initialGroupOrder.length !== courtsInRotation.length) {
                phase.sub_blocks = [];
                phase.rotationDuration = 0;
                return;
            }

            const numRotations = initialGroupOrder.length;
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
                for (let j = 0; j < courtsInRotation.length; j++) { 
                    const court = courtsInRotation[j];
                    const groupIndex = ((j - i) % numRotations + numRotations) % numRotations;
                    const groupIdToAssign = initialGroupOrder[groupIndex];

                    assignments[court.id] = groupIdToAssign;
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
            this.updateCourtsBasedOnGroups();
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
                assignedGroupIds: [], activities: [], isDefault: false 
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
            if (!this.plan.playerGroups) this.plan.playerGroups = [];
            const newGroupLetter = String.fromCharCode(65 + (this.plan.playerGroups || []).length);
            this.plan.playerGroups.push({ id: `group${Date.now()}`, name: `Group ${newGroupLetter}`, player_ids: [] });
            this.updateCourtsBasedOnGroups();
            this.render();
        },
        removeGroup(groupId) {
            this.plan.playerGroups = this.plan.playerGroups.filter(g => g.id !== groupId);
            (this.plan.timeline || []).forEach(phase => {
                (phase.courts || []).forEach(court => {
                    court.assignedGroupIds = (court.assignedGroupIds || []).filter(id => id !== groupId);
                });
                this.calculateAndApplyRotations(phase.id);
            });
            this.updateCourtsBasedOnGroups();
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
                this.render(); 
            }
        },

        // --- EVENT HANDLERS ---

        togglePhase(event, phaseId) {
            if (event.target.closest('button, input')) {
                return;
            }
            const phaseElement = document.querySelector(`.phase-block[data-phase-id="${phaseId}"]`);
            if (!phaseElement) return;

            const phaseData = this.plan.timeline.find(p => p.id === phaseId);
            if (!phaseData) return;

            const newIsOpenState = !phaseElement.classList.contains('is-open');
            phaseElement.classList.toggle('is-open', newIsOpenState);
            phaseData.isOpen = newIsOpenState;
        },

        handleAppClick(e) {
            const target = e.target;

            const attendanceItem = target.closest('.player-attendance-item');
            if (attendanceItem) {
                this.cyclePlayerStatus(parseInt(attendanceItem.dataset.playerId));
                return;
            }

            // NEW: Handle clicks on the court container to open the activity modal
            const courtContainer = target.closest('.court-clickable');
            if (courtContainer) {
                this.openActivityModal(courtContainer.dataset.phaseId, courtContainer.dataset.courtId);
                return;
            }

            const button = target.closest('button');
            if (button) {
                if (button.matches('.delete-phase-btn')) {
                    if (confirm('Delete this phase?')) this.deletePhase(button.dataset.phaseId);
                } else if (button.matches('.add-group-btn')) {
                    this.addNewGroup();
                } else if (button.matches('.remove-group-btn')) {
                    if (confirm('Are you sure?')) this.removeGroup(button.dataset.groupId);
                } else if (button.matches('.remove-activity-btn')) { // This is inside the modal
                    this.removeActivity(parseInt(button.dataset.index, 10));
                } else if (button.id === 'save-plan-btn') {
                    this.savePlan();
                }
                return;
            }

            const header = target.closest('.planner-header');
            if (header && !header.parentElement.matches('.phase-block')) {
                header.parentElement.classList.toggle('is-open');
            }
        },

        handleAppChange(e) {
            const target = e.target;
            if (target.matches('#primary-tag-filter') || target.matches('.secondary-tag-filter')) {
                this.handleFilterChange();
            } else if (target.matches('.phase-name-input, .phase-duration-input')) {
                const phaseId = target.dataset.phaseId;
                const phase = this.plan.timeline.find(p => p.id === phaseId);
                if (!phase) return;

                if (target.matches('.phase-name-input')) phase.name = target.value;
                else if (target.matches('.phase-duration-input')) phase.duration = parseInt(target.value, 10) || 0;

                this.calculateAndApplyRotations(phaseId);
                this.render();
            }
        },

        handleFilterChange() {
            const primaryFilter = document.getElementById('primary-tag-filter');
            if (!primaryFilter) return;
            this.activityFilters.primaryTagId = primaryFilter.value ? parseInt(primaryFilter.value) : null;

            this.activityFilters.secondaryTagIds.clear();
            document.querySelectorAll('.secondary-tag-filter:checked').forEach(el => {
                this.activityFilters.secondaryTagIds.add(parseInt(el.value));
            });

            this.renderFilteredDrillList();
        },

        handleActivityFormSubmit(e) {
            e.preventDefault();
            if (e.target.id !== 'add-activity-form') return;

            const { court } = this.getActiveContext();
            if (!court) return;

            const select = document.getElementById('drill-select');
            const duration = parseInt(document.getElementById('activity-duration').value, 10);

            if (!select.value) {
                alert("No drill selected. Please select a drill from the list.");
                return;
            }

            const drillId = parseInt(select.value, 10);
            const name = select.options[select.selectedIndex].text;

            if (!name || !(duration > 0)) {
                alert("Please provide a valid duration.");
                return;
            }

            if (!court.activities) court.activities = [];
            court.activities.push({ name: name, drill_id: drillId, duration: duration });

            this.renderActivityList();
            this.render();
        },

        handleDragStart(e) {
            const target = e.target;
            if (target.matches('.player-card')) {
                this.draggedElement = { type: 'player', id: parseInt(target.dataset.playerId) };
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
                (this.plan.playerGroups || []).forEach(g => { g.player_ids = g.player_ids.filter(id => id !== this.draggedElement.id); });
                if (targetGroupId) {
                    const targetGroup = this.plan.playerGroups.find(g => g.id === targetGroupId);
                    if (targetGroup) targetGroup.player_ids.push(this.draggedElement.id);
                }
                this.updateCourtsBasedOnGroups();
                this.render();
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
            const phase = (this.plan.timeline || []).find(p => p.id === this.activeContext.phaseId);
            const court = phase ? (phase.courts || []).find(c => c.id === this.activeContext.courtId) : null;
            return { phase, court };
        },
    };

    app.init();
});