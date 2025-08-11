// charlsquash/squashsyncv2/SquashSyncV2-9fc5a553efc7a2924c0997725f420d440d0e5dc9/static/js/live_session.js
document.addEventListener('DOMContentLoaded', () => {
    // --- Application State ---
    const appState = {
        sessionId: null,
        currentView: 'all-courts-view',
        selectedCourt: null,
        apiPollInterval: null,
        countdownInterval: null,
        timers: {},
        lastKnownData: null
    };

    // --- DOM Elements ---
    const elements = {
        container: document.getElementById('live-view-container'),
        loadingIndicator: document.getElementById('loading-indicator'),
        waitingScreen: document.getElementById('waiting-screen'),
        waitingTitle: document.getElementById('waiting-session-title'),
        countdownClock: document.getElementById('countdown-clock'),
        coachesList: document.getElementById('coaches-list'),
        attendeesList: document.getElementById('attendees-list'),
        liveHeader: document.getElementById('live-header'),
        liveMain: document.getElementById('live-main-content'),
        masterTimer: document.getElementById('master-session-timer'),
        sessionTitle: document.getElementById('session-title-header'),
        phaseName: document.getElementById('current-phase-name'),
        phaseTimerContainer: document.getElementById('phase-timer-container'),
        viewToggle: document.getElementById('view-toggle'),
        fullscreenToggle: document.getElementById('fullscreen-toggle'),
        fullscreenToggleWaiting: document.getElementById('fullscreen-toggle-waiting'),
        allCourtsView: document.getElementById('all-courts-view'),
        singleCourtView: document.getElementById('single-court-view'),
        singleCourtSelector: document.getElementById('single-court-selector'),
        singleCourtContent: document.getElementById('single-court-content'),
        courtCardTemplate: document.getElementById('court-card-template'),
        singleCourtDisplayTemplate: document.getElementById('single-court-display-template'),
        circleTimerTemplate: document.getElementById('circle-timer-template')
    };

    const cleanup = () => {
        if (appState.apiPollInterval) { clearInterval(appState.apiPollInterval); appState.apiPollInterval = null; }
        if (appState.countdownInterval) { clearInterval(appState.countdownInterval); appState.countdownInterval = null; }
        for (const timerId in appState.timers) { clearInterval(appState.timers[timerId]); }
        appState.timers = {};
    };

    const init = () => {
        cleanup();
        appState.sessionId = elements.container.dataset.sessionId;
        if (!appState.sessionId) return;
        setupEventListeners();
        fetchSessionState();
        appState.apiPollInterval = setInterval(fetchSessionState, 5000);
    };

    const fetchSessionState = async () => {
        try {
            const response = await fetch(`/live-session/api/update/${appState.sessionId}/?_=${new Date().getTime()}`);
            if (!response.ok) throw new Error(`API request failed: ${response.status}`);
            const data = await response.json();
            if (data.status === 'error') throw new Error(data.message);
            appState.lastKnownData = data;
            updateUI(data);
        } catch (error) {
            cleanup();
            elements.container.innerHTML = `<div class="session-error-message"><h1>Error</h1><p>${error.message}</p></div>`;
        }
    };

    const updateUI = (data) => {
        if (elements.container.classList.contains('loading')) {
            elements.container.classList.remove('loading');
        }

        if (data.sessionStatus === 'not_yet_started') {
            displayWaitingScreen(data);
        } else if (data.sessionStatus === 'finished' || !data.currentPhase) {
            displaySessionFinished();
        } else {
            displayLiveSession(data);
        }
    };

    const displayWaitingScreen = (data) => {
        elements.liveHeader.style.display = 'none';
        elements.liveMain.style.display = 'none';
        elements.waitingScreen.style.display = 'flex';

        elements.waitingTitle.textContent = data.sessionTitle;
        updateCoachList(elements.coachesList, data.coaches);
        updateAttendeeList(elements.attendeesList, data.attendees);
        
        if (!appState.countdownInterval) {
            let remaining = data.timeToStart;
            const renderCountdown = () => {
                if (remaining <= 0) {
                    elements.countdownClock.textContent = 'Starting...';
                    clearInterval(appState.countdownInterval);
                    appState.countdownInterval = null;
                    fetchSessionState(); // Re-fetch immediately when time is up
                } else {
                    elements.countdownClock.textContent = formatCountdown(remaining);
                    remaining--;
                }
            };
            renderCountdown();
            appState.countdownInterval = setInterval(renderCountdown, 1000);
        }
    };
    
    const displayLiveSession = (data) => {
        cleanupCountdown();
        elements.waitingScreen.style.display = 'none';
        elements.liveHeader.style.display = 'grid';
        elements.liveMain.style.display = 'block';

        elements.masterTimer.textContent = formatTime(data.totalTimeLeft);
        elements.sessionTitle.textContent = data.sessionTitle;
        elements.phaseName.textContent = data.currentPhase.name;
        updateCircleTimer(elements.phaseTimerContainer, data.currentPhase.timeLeft, data.currentPhase.duration, "phase-timer");

        if (appState.currentView === 'all-courts-view') {
            updateAllCourtsView(data.courts);
        } else {
            if (!appState.selectedCourt && data.courts.length > 0) appState.selectedCourt = data.courts[0].courtName;
            updateSingleCourtSelector(data.courts);
            updateSingleCourtView(data.courts);
        }
    };

    const updateCoachList = (divElement, items) => {
        divElement.innerHTML = '';
        if (items && items.length > 0) {
            divElement.innerHTML = items.map(item => `<span>${item}</span>`).join('');
        } else {
            divElement.innerHTML = '<span class="text-muted">None Assigned</span>';
        }
    };

    const updateAttendeeList = (listElement, items) => {
        listElement.innerHTML = '';
        if (items && items.length > 0) {
            items.forEach(item => {
                const li = document.createElement('li');
                li.textContent = item;
                listElement.appendChild(li);
            });
        } else {
            const li = document.createElement('li');
            li.textContent = 'None yet';
            li.className = 'text-muted';
            listElement.appendChild(li);
        }
    };
    
    const cleanupCountdown = () => {
        if (appState.countdownInterval) {
            clearInterval(appState.countdownInterval);
            appState.countdownInterval = null;
        }
    };

    const updateAllCourtsView = (courts) => {
        elements.allCourtsView.innerHTML = '';
        if (!courts || courts.length === 0) { elements.allCourtsView.innerHTML = '<p class="no-data-message">No activities for this phase.</p>'; return; }
        courts.forEach(court => {
            const card = elements.courtCardTemplate.content.cloneNode(true).querySelector('.court-card');
            card.querySelector('.court-name').textContent = court.courtName;
            card.querySelector('.player-group').textContent = court.playerGroup;
            card.querySelector('.drill-name').textContent = court.currentActivity.name;
            const playerList = card.querySelector('.player-name-list');
            playerList.innerHTML = court.players.map(name => `<li>${name}</li>`).join('');
            const timerWrapper = card.querySelector('.timer-wrapper');
            updateCircleTimer(timerWrapper, court.currentActivity.timeLeft, court.currentActivity.duration, `activity-${court.courtName}`);
            elements.allCourtsView.appendChild(card);
        });
    };

    const updateSingleCourtSelector = (courts) => {
        elements.singleCourtSelector.innerHTML = '';
        courts.forEach(court => {
            const button = document.createElement('button');
            button.textContent = court.courtName;
            if (court.courtName === appState.selectedCourt) button.classList.add('active');
            button.onclick = () => { appState.selectedCourt = court.courtName; if (appState.lastKnownData) updateUI(appState.lastKnownData); };
            elements.singleCourtSelector.appendChild(button);
        });
    };

    const updateSingleCourtView = (courts) => {
        const courtData = courts.find(c => c.courtName === appState.selectedCourt);
        if (!courtData) { elements.singleCourtContent.innerHTML = '<p>Select a court.</p>'; return; }
        const display = elements.singleCourtDisplayTemplate.content.cloneNode(true).querySelector('.single-court-focused');
        display.querySelector('.drill-name').textContent = courtData.currentActivity.name;
        display.querySelector('.player-group').textContent = courtData.playerGroup;
        const playerList = display.querySelector('.player-name-list');
        playerList.innerHTML = courtData.players.map(name => `<li>${name}</li>`).join('');
        display.querySelector('.up-next-name').textContent = courtData.nextActivity ? courtData.nextActivity.name : 'Session End';
        const mainTimerArea = display.querySelector('.main-timer-area');
        updateCircleTimer(mainTimerArea, courtData.currentActivity.timeLeft, courtData.currentActivity.duration, `single-activity-${courtData.courtName}`);
        elements.singleCourtContent.innerHTML = '';
        elements.singleCourtContent.appendChild(display);
    };

    const toggleFullscreen = () => {
        if (!document.fullscreenElement) {
            elements.container.requestFullscreen().catch(err => {
                alert(`Error attempting to enable full-screen mode: ${err.message} (${err.name})`);
            });
        } else {
            document.exitFullscreen();
        }
    };

    const updateFullscreenIcons = () => {
        const isFullscreen = !!document.fullscreenElement;
        [elements.fullscreenToggle, elements.fullscreenToggleWaiting].forEach(btn => {
            if (btn) {
                const enterIcon = btn.querySelector('.bi-fullscreen');
                const exitIcon = btn.querySelector('.bi-fullscreen-exit');
                enterIcon.classList.toggle('d-none', isFullscreen);
                exitIcon.classList.toggle('d-none', !isFullscreen);
            }
        });
    };

    const setupEventListeners = () => {
        elements.viewToggle.addEventListener('click', (e) => {
            const button = e.target.closest('button');
            if (button) {
                const newView = button.dataset.view;
                if (newView === appState.currentView) return;
                elements.viewToggle.querySelector('.active').classList.remove('active');
                button.classList.add('active');
                document.querySelector('.view.active').classList.remove('active');
                document.getElementById(newView).classList.add('active');
                appState.currentView = newView;
                if (appState.lastKnownData) { updateUI(appState.lastKnownData); }
            }
        });

        elements.fullscreenToggle.addEventListener('click', toggleFullscreen);
        elements.fullscreenToggleWaiting.addEventListener('click', toggleFullscreen);
        document.addEventListener('fullscreenchange', updateFullscreenIcons);
    };
    
    const updateCircleTimer = (container, timeLeft, totalDuration, timerId) => {
        if (!container) return;
        let timer = container.querySelector('.circle-timer');
        if (!timer) {
            timer = elements.circleTimerTemplate.content.cloneNode(true);
            container.innerHTML = '';
            container.appendChild(timer);
            timer = container.querySelector('.circle-timer');
        }
        if (!timer) { console.error("Could not create or find .circle-timer element"); return; }
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
            if (remaining < 0) { remaining = 0; clearInterval(appState.timers[timerId]); }
            render();
        }, 1000);
    };

    const formatTime = (seconds) => {
        if (isNaN(seconds) || seconds < 0) return '00:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.round(seconds % 60);
        return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    };
    
    const formatCountdown = (totalSeconds) => {
        if (isNaN(totalSeconds) || totalSeconds < 0) return '00:00:00';
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = Math.floor(totalSeconds % 60);
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    };

    const displaySessionFinished = () => {
        cleanup();
        elements.container.innerHTML = `<div class="session-finished-message"><h1>Session Finished</h1></div>`;
    };
    
    window.addEventListener('beforeunload', cleanup);
    init();
});