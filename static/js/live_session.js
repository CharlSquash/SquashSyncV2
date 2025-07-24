document.addEventListener('DOMContentLoaded', () => {
    // --- Application State ---
    console.log('[DEBUG] 1. Script Loaded: DOMContentLoaded event fired.');
    const appState = {
        sessionId: null,
        currentView: 'all-courts-view',
        selectedCourt: null,
        apiPollInterval: null,
        timers: {},
        lastKnownData: null
    };

    // --- DOM Elements ---
    const elements = {
        container: document.getElementById('live-view-container'),
        loadingIndicator: document.getElementById('loading-indicator'),
        allCourtsView: document.getElementById('all-courts-view'),
        courtCardTemplate: document.getElementById('court-card-template'),
        circleTimerTemplate: document.getElementById('circle-timer-template'),
        masterTimer: document.getElementById('master-session-timer'),
        sessionTitle: document.getElementById('session-title-header'),
        phaseName: document.getElementById('current-phase-name'),
        phaseTimerContainer: document.getElementById('phase-timer-container'),
    };
    console.log('[DEBUG] 2. DOM Elements selected.');

    // --- Main Functions ---
    const init = () => {
        appState.sessionId = elements.container.dataset.sessionId;
        if (!appState.sessionId) {
            console.error('[DEBUG] FATAL: Session ID missing from data-session-id attribute.');
            return;
        }
        console.log(`[DEBUG] 3. Initialization complete. Session ID: ${appState.sessionId}.`);
        fetchSessionState();
        appState.apiPollInterval = setInterval(fetchSessionState, 5000);
    };

    const fetchSessionState = async () => {
        try {
            const url = `/live-session/api/update/${appState.sessionId}/`;
            console.log(`[DEBUG] 4. Fetching data from: ${url}`);
            const response = await fetch(`${url}?_=${new Date().getTime()}`); // Cache-busting
            const data = await response.json();
            
            console.log('[DEBUG] 5. Data Received from API:', JSON.parse(JSON.stringify(data)));

            if (!response.ok || data.status === 'error') {
                throw new Error(data.message || `API request failed: ${response.status}`);
            }
            
            appState.lastKnownData = data;
            updateUI(data);

        } catch (error) {
            console.error('[DEBUG] FINAL ERROR: The process failed inside fetchSessionState.', error);
            elements.container.innerHTML = `<div style="color:red; padding: 2rem;"><h3>Error Fetching Data</h3><p>${error.message}</p></div>`;
            clearInterval(appState.apiPollInterval);
        }
    };

    const updateUI = (data) => {
        console.log('[DEBUG] 6. updateUI function called.');
        if (elements.container.classList.contains('loading')) {
            elements.container.classList.remove('loading');
            console.log('[DEBUG] >> Loading indicator removed.');
        }

        if (data.sessionStatus === 'finished' || !data.currentPhase) {
            console.log('[DEBUG] >> Session is finished. Stopping UI updates.');
            displaySessionFinished();
            return;
        }

        console.log('[DEBUG] >> Updating timers and text content...');
        elements.masterTimer.textContent = formatTime(data.totalTimeLeft);
        elements.sessionTitle.textContent = data.sessionTitle;
        elements.phaseName.textContent = data.currentPhase.name;
        updateCircleTimer(elements.phaseTimerContainer, data.currentPhase.timeLeft, data.currentPhase.duration, "phase-timer");
        
        console.log('[DEBUG] >> Calling updateAllCourtsView...');
        updateAllCourtsView(data.courts);
        console.log('[DEBUG] 7. updateUI function finished.');
    };

    const updateAllCourtsView = (courts) => {
        elements.allCourtsView.innerHTML = ''; // Clear previous content

        if (!courts || courts.length === 0) {
            console.error('[DEBUG] >> CRITICAL: The "courts" array in the received data is empty or missing. Nothing to display.');
            elements.allCourtsView.innerHTML = `<div style="color:orange; padding: 2rem;"><h3>No Courts Found</h3><p>The API returned no court data for the current phase.</p></div>`;
            return;
        }

        console.log(`[DEBUG] >> Found ${courts.length} courts. Creating cards...`);
        courts.forEach((court, index) => {
            console.log(`[DEBUG] >> Processing Court ${index + 1}:`, court);
            const card = elements.courtCardTemplate.content.cloneNode(true).querySelector('.court-card');
            
            card.querySelector('.court-name').textContent = court.courtName;
            card.querySelector('.player-group').textContent = court.playerGroup;
            card.querySelector('.drill-name').textContent = court.currentActivity.name;

            const activityTimerWrapper = card.querySelector('.timer-wrapper[data-timer-type="activity"]');
            updateCircleTimer(activityTimerWrapper, court.currentActivity.timeLeft, court.currentActivity.duration, `activity-${court.courtName}`);
            
            elements.allCourtsView.appendChild(card);
        });
        console.log(`[DEBUG] >> Finished creating all court cards.`);
    };
    
    const updateCircleTimer = (container, timeLeft, totalDuration, timerId) => {
        if (!container) {
            console.warn(`[DEBUG] Timer container not found for timerId: ${timerId}`);
            return;
        }
        //... (rest of function is the same)
        let timer = container.querySelector('.circle-timer');
        if (!timer) {
            timer = elements.circleTimerTemplate.content.cloneNode(true).querySelector('.circle-timer');
            container.innerHTML = '';
            container.appendChild(timer);
        }
        const timerText = timer.querySelector('.timer-text');
        const progressCircle = timer.querySelector('.timer-progress');
        const radius = progressCircle.r.baseVal.value;
        const circumference = 2 * Math.PI * radius;
        progressCircle.style.strokeDasharray = `${circumference} ${circumference}`;
        if (appState.timers[timerId]) clearInterval(appState.timers[timerId]);
        let remaining = Math.round(timeLeft);
        let totalForPercentage = totalDuration > 0 ? totalDuration : remaining > 0 ? remaining : 1;
        const render = () => {
            timerText.textContent = formatTime(remaining);
            const offset = circumference - (remaining / totalForPercentage) * circumference;
            progressCircle.style.strokeDashoffset = Math.max(0, offset);
        };
        render();
        appState.timers[timerId] = setInterval(() => {
            remaining--;
            if (remaining < 0) {
                remaining = 0;
                clearInterval(appState.timers[timerId]);
            }
            render();
        }, 1000);
    };

    const formatTime = (seconds) => {
        if (isNaN(seconds) || seconds < 0) return '00:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.round(seconds % 60);
        return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    };

    const displaySessionFinished = () => {
        clearInterval(appState.apiPollInterval);
        elements.container.innerHTML = `<div class="session-finished-message"><h1>Session Finished</h1></div>`;
    };
    
    // --- Start the Application ---
    init();
});