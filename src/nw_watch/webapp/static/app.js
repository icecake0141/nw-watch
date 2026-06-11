/*
 * Copyright 2026 icecake0141
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * This file was created or modified with the assistance of an AI (Large Language Model).
 * Review required for correctness, security, and licensing.
 */
// Network Watch Frontend Application

class NetworkWatch {
    constructor() {
        this.autoRefresh = true;
        this.currentCommand = null;
        this.devices = [];
        this.commands = [];
        this.config = {
            run_poll_interval_seconds: 2,
            ping_poll_interval_seconds: 1,
            ping_window_seconds: 60,
            websocket_enabled: false
        };
        this.runPollTimer = null;
        this.pingPollTimer = null;
        this.pauseBanner = null;
        this.isPolling = false;
        this.websocket = null;
        this.websocketReconnectTimer = null;
        this.websocketReconnectAttempts = 0;
        this.expandedPingTiles = new Set();
        this.collectorPollTimer = null;
        this.collectorState = {
            commands_paused: false,
            manual_mode: false,
            manual_run_requested: false,
            shutdown_requested: false,
            command_schedule: {},
            status: 'unknown',
            updated_at: 0
        };
        this.collectorPollIntervalMs = 5000;
        this.scheduleRenderTimer = null;

        // WebSocket reconnection settings
        this.maxWebSocketReconnectAttempts = 5;
        this.baseReconnectDelay = 1000;  // 1 second base delay
        this.maxReconnectDelay = 30000;  // 30 seconds max delay
        this.reconnectBackoffMultiplier = 2;  // Exponential backoff multiplier

        // Diff state preservation
        // Structure: { "command:device": { type: 'history'|'device', content: '...', format: 'html'|'text', otherDevice: '...' } }
        this.diffStates = {};
        this.DIFF_PLACEHOLDER_TEXT = 'Click a button above to view diff';
        this.sideBySideOutputMinHeight = 240;
        this.sideBySideOutputMaxHeight = 2400;
        this.sideBySideOutputHeight = this.loadSideBySideOutputHeight();
        this.sideBySideDiffMode = this.loadSideBySideDiffMode();
        this.sideBySideScrollSyncEnabled = this.loadSideBySideScrollSyncEnabled();
        this.isSyncingSideBySideScroll = false;
        this.sideBySideScrollStates = {};
        this.latestSideBySideData = {};
        this.outputSnapshots = {};
        this.outputViewModes = {};

        this.init();
    }

    async init() {
        // Load configuration
        await this.loadConfig();

        // Load initial data
        await this.loadDevices();
        await this.loadCommands();
        await this.loadCollectorStatus();

        // Setup UI
        this.setupEventListeners();
        this.renderCommandTabs();

        // Start WebSocket or polling based on config
        if (this.config.websocket_enabled) {
            this.connectWebSocket();
        } else {
            this.startPolling();
        }

        this.startCollectorStatusPolling();

        // Initial data load
        await this.updatePingStatus();
        if (this.commands.length > 0) {
            this.switchToCommand(this.commands[0]);
        }
    }

    logClientError(code, error, context = {}) {
        console.error(`[NW-WATCH:${code}]`, {
            message: error && error.message ? error.message : String(error),
            name: error && error.name ? error.name : 'Error',
            context: context
        });
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            const data = await response.json();
            this.config = data;
        } catch (error) {
            this.logClientError('CONFIG_LOAD_FAILED', error, { endpoint: '/api/config' });
        }
    }

    async loadDevices() {
        try {
            const response = await fetch('/api/devices');
            const data = await response.json();
            this.devices = data.devices || [];
        } catch (error) {
            this.logClientError('DEVICES_LOAD_FAILED', error, { endpoint: '/api/devices' });
        }
    }

    async loadCommands() {
        try {
            const response = await fetch('/api/commands');
            const data = await response.json();
            this.commands = data.commands || [];
        } catch (error) {
            this.logClientError('COMMANDS_LOAD_FAILED', error, { endpoint: '/api/commands' });
        }
    }

    async loadCollectorStatus() {
        try {
            const response = await fetch('/api/collector/status');
            const data = await response.json();
            this.collectorState = data;
            this.updateCollectorControls();
            this.updateScheduleProgressDisplays();
        } catch (error) {
            this.logClientError('COLLECTOR_STATUS_LOAD_FAILED', error, { endpoint: '/api/collector/status' });
            this.updateCollectorControls(true);
            this.updateScheduleProgressDisplays();
        }
    }

    setupEventListeners() {
        // Theme toggle
        document.getElementById('themeToggle').addEventListener('click', () => {
            this.toggleTheme();
        });

        document.getElementById('toggleAutoRefresh').addEventListener('click', () => {
            this.toggleAutoRefresh();
        });

        document.getElementById('manualRefresh').addEventListener('click', () => {
            this.manualRefresh();
        });

        document.getElementById('toggleCollectorCommands').addEventListener('click', () => {
            this.toggleCollectorCommands();
        });

        document.getElementById('toggleCollectorMode').addEventListener('click', () => {
            this.toggleCollectorMode();
        });

        document.getElementById('runCollectorOnce').addEventListener('click', () => {
            this.runCollectorOnce();
        });

        document.getElementById('stopCollector').addEventListener('click', () => {
            this.stopCollector();
        });

        // Load saved theme preference
        this.loadThemePreference();
    }

    loadSideBySideOutputHeight() {
        const savedHeight = Number(localStorage.getItem('sideBySideOutputHeight'));
        if (Number.isFinite(savedHeight)) {
            return Math.max(this.sideBySideOutputMinHeight, Math.min(savedHeight, this.sideBySideOutputMaxHeight));
        }
        return 600;
    }

    loadSideBySideDiffMode() {
        const savedMode = localStorage.getItem('sideBySideDiffMode');
        if (['char', 'line', 'git'].includes(savedMode)) {
            return savedMode;
        }
        return 'char';
    }

    setSideBySideDiffMode(mode, command) {
        if (!['char', 'line', 'git'].includes(mode)) {
            return;
        }
        this.sideBySideDiffMode = mode;
        localStorage.setItem('sideBySideDiffMode', mode);
        if (command) {
            this.updateCommandData(command);
        }
    }

    loadSideBySideScrollSyncEnabled() {
        const savedValue = localStorage.getItem('sideBySideScrollSyncEnabled');
        return savedValue === null ? true : savedValue === 'true';
    }

    setSideBySideScrollSyncEnabled(enabled) {
        this.sideBySideScrollSyncEnabled = enabled;
        localStorage.setItem('sideBySideScrollSyncEnabled', String(enabled));
        document.querySelectorAll('.scroll-sync-toggle').forEach(button => {
            this.updateScrollSyncToggle(button);
        });
    }

    setSideBySideOutputHeight(height) {
        this.sideBySideOutputHeight = Math.max(
            this.sideBySideOutputMinHeight,
            Math.min(height, this.sideBySideOutputMaxHeight)
        );
        localStorage.setItem('sideBySideOutputHeight', String(this.sideBySideOutputHeight));

        document.querySelectorAll('.side-by-side-section .device-panel-output').forEach(output => {
            output.style.maxHeight = `${this.sideBySideOutputHeight}px`;
            output.style.height = `${this.sideBySideOutputHeight}px`;
        });
    }

    toggleTheme() {
        const body = document.body;
        const isDark = body.classList.toggle('dark-theme');

        // Save preference to localStorage
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
    }

    loadThemePreference() {
        const savedTheme = localStorage.getItem('theme');

        // Check system preference with fallback for older browsers
        let prefersDark = false;
        try {
            prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        } catch (e) {
            // Older browsers may not support matchMedia
            console.log('matchMedia not supported, using light theme');
        }

        // Apply saved theme, or use system preference if no saved theme
        if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
            document.body.classList.add('dark-theme');
        }
    }

    toggleAutoRefresh() {
        this.autoRefresh = !this.autoRefresh;
        const btn = document.getElementById('toggleAutoRefresh');

        if (this.autoRefresh) {
            btn.textContent = '⏸ Pause Auto-Refresh';
            if (this.config.websocket_enabled) {
                // WebSocket handles updates automatically when connected
                if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
                    this.connectWebSocket();
                }
            } else {
                this.startPolling();
            }
            this.showPauseBanner(false);
        } else {
            btn.textContent = '▶ Resume Auto-Refresh';
            this.stopPolling();
            this.showPauseBanner(true);
        }
    }

    startCollectorStatusPolling() {
        if (this.collectorPollTimer) {
            return;
        }

        this.collectorPollTimer = setInterval(() => {
            this.loadCollectorStatus();
        }, this.collectorPollIntervalMs);

        if (!this.scheduleRenderTimer) {
            this.scheduleRenderTimer = setInterval(() => {
                this.updateScheduleProgressDisplays();
            }, 1000);
        }
    }

    async toggleCollectorCommands() {
        try {
            const endpoint = this.collectorState.commands_paused
                ? '/api/collector/resume'
                : '/api/collector/pause';
            const response = await fetch(endpoint, { method: 'POST' });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to toggle collector commands');
            }
            this.collectorState = data;
            this.updateCollectorControls();
            this.updateScheduleProgressDisplays();
        } catch (error) {
            console.error('Error toggling collector commands:', error);
            alert('Failed to update collector state');
        }
    }

    async stopCollector() {
        const confirmed = window.confirm('Stop the collector process? Command execution will end.');
        if (!confirmed) {
            return;
        }

        try {
            const response = await fetch('/api/collector/stop', { method: 'POST' });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to stop collector');
            }
            this.collectorState = data;
            this.updateCollectorControls();
            this.updateScheduleProgressDisplays();
        } catch (error) {
            console.error('Error stopping collector:', error);
            alert('Failed to stop collector');
        }
    }

    async toggleCollectorMode() {
        try {
            const response = await fetch('/api/collector/mode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ manual_mode: !this.collectorState.manual_mode })
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to update collector mode');
            }
            this.collectorState = data;
            this.updateCollectorControls();
            this.updateScheduleProgressDisplays();
        } catch (error) {
            console.error('Error updating collector mode:', error);
            alert('Failed to update collector mode');
        }
    }

    async runCollectorOnce() {
        try {
            const runButton = document.getElementById('runCollectorOnce');
            runButton.disabled = true;
            runButton.textContent = '⏳ Run Requested';

            const response = await fetch('/api/collector/run_once', { method: 'POST' });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to request manual command run');
            }
            this.collectorState = data;
            this.updateCollectorControls();
            this.updateScheduleProgressDisplays();
        } catch (error) {
            console.error('Error requesting manual command run:', error);
            alert('Failed to request manual command run');
            this.updateCollectorControls();
            this.updateScheduleProgressDisplays();
        }
    }

    updateCollectorControls(hasError = false) {
        const statusElement = document.getElementById('collectorStatus');
        const toggleButton = document.getElementById('toggleCollectorCommands');
        const modeButton = document.getElementById('toggleCollectorMode');
        const runButton = document.getElementById('runCollectorOnce');
        const stopButton = document.getElementById('stopCollector');
        statusElement.classList.remove('status-unknown', 'status-paused', 'status-running', 'status-stopped', 'status-manual', 'status-not-running');

        if (hasError) {
            statusElement.textContent = 'Collector: Unknown';
            statusElement.classList.add('status-unknown');
            modeButton.disabled = true;
            runButton.style.display = 'none';
            return;
        }
        const status = this.collectorState.status || 'unknown';

        if (status === 'not_running') {
            statusElement.textContent = 'Collector: Not Running';
            statusElement.classList.add('status-not-running');
            toggleButton.disabled = true;
            modeButton.disabled = true;
            runButton.disabled = true;
            runButton.style.display = 'none';
            stopButton.disabled = true;
            toggleButton.textContent = '⏸ Collector Not Running';
            return;
        }

        if (status === 'stopped') {
            statusElement.textContent = 'Collector: Stopped';
            statusElement.classList.add('status-stopped');
            toggleButton.disabled = true;
            modeButton.disabled = true;
            runButton.disabled = true;
            runButton.style.display = 'none';
            stopButton.disabled = true;
            toggleButton.textContent = '⏹ Collector Stopped';
            return;
        }

        if (this.collectorState.commands_paused || status === 'paused') {
            statusElement.textContent = 'Collector: Paused';
            statusElement.classList.add('status-paused');
            toggleButton.textContent = '▶ Resume Commands';
        } else {
            statusElement.textContent = 'Collector: Running';
            statusElement.classList.add('status-running');
            toggleButton.textContent = '⏸ Pause Commands';
        }

        if (!this.collectorState.commands_paused && this.collectorState.manual_mode) {
            statusElement.textContent = this.collectorState.manual_run_requested
                ? 'Collector: Manual Run Pending'
                : 'Collector: Manual';
            statusElement.classList.remove('status-running', 'status-paused');
            statusElement.classList.add('status-manual');
        }

        modeButton.classList.toggle('mode-on', Boolean(this.collectorState.manual_mode));
        modeButton.classList.toggle('mode-off', !this.collectorState.manual_mode);
        modeButton.setAttribute('aria-pressed', String(Boolean(this.collectorState.manual_mode)));
        modeButton.title = this.collectorState.manual_mode
            ? 'Manual mode is on. Click to return to automatic command collection.'
            : 'Manual mode is off. Click to pause scheduled command collection and run commands manually.';
        modeButton.textContent = this.collectorState.manual_mode
            ? 'Manual Mode ON'
            : 'Manual Mode OFF';
        runButton.style.display = this.collectorState.manual_mode ? 'inline-flex' : 'none';
        runButton.disabled = Boolean(this.collectorState.commands_paused || this.collectorState.manual_run_requested);
        runButton.textContent = this.collectorState.manual_run_requested
            ? '⏳ Run Requested'
            : '▶ Run Commands Now';

        toggleButton.disabled = false;
        modeButton.disabled = false;
        stopButton.disabled = !Boolean(this.collectorState.collector_pid);
    }

    connectWebSocket() {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        try {
            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                console.log('WebSocket connected');
                this.websocketReconnectAttempts = 0;
                // Stop polling when WebSocket is connected
                this.stopPolling();
            };

            this.websocket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleWebSocketMessage(message);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };

            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            this.websocket.onclose = () => {
                console.log('WebSocket disconnected');
                this.websocket = null;

                // Fallback to polling if WebSocket fails
                if (this.autoRefresh && !this.isPolling) {
                    console.log('Falling back to polling');
                    this.startPolling();
                }

                // Attempt to reconnect
                if (this.websocketReconnectAttempts < this.maxWebSocketReconnectAttempts) {
                    this.websocketReconnectAttempts++;
                    const delay = Math.min(
                        this.maxReconnectDelay,
                        this.baseReconnectDelay * Math.pow(this.reconnectBackoffMultiplier, this.websocketReconnectAttempts - 1)
                    );
                    console.log(`Attempting to reconnect WebSocket in ${delay}ms (attempt ${this.websocketReconnectAttempts})`);
                    this.websocketReconnectTimer = setTimeout(() => {
                        if (this.autoRefresh && this.config.websocket_enabled) {
                            this.connectWebSocket();
                        }
                    }, delay);
                }
            };
        } catch (error) {
            console.error('Error creating WebSocket:', error);
            // Fallback to polling
            if (this.autoRefresh) {
                this.startPolling();
            }
        }
    }

    handleWebSocketMessage(message) {
        if (!this.autoRefresh) {
            return;
        }

        switch (message.type) {
            case 'run_update':
                // New command run data available
                if (this.currentCommand) {
                    this.updateCommandData(this.currentCommand);
                }
                break;
            case 'ping_update':
                // New ping data available
                this.updatePingStatus();
                break;
            case 'data_update':
                // General data update
                this.updatePingStatus();
                if (this.currentCommand) {
                    this.updateCommandData(this.currentCommand);
                }
                break;
            default:
                console.log('Unknown WebSocket message type:', message.type);
        }
    }

    disconnectWebSocket() {
        if (this.websocketReconnectTimer) {
            clearTimeout(this.websocketReconnectTimer);
            this.websocketReconnectTimer = null;
        }
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
    }

    showPauseBanner(show) {
        if (!this.pauseBanner) {
            this.pauseBanner = document.createElement('div');
            this.pauseBanner.className = 'pause-banner';
            this.pauseBanner.textContent = 'Auto-refresh paused';
            document.body.appendChild(this.pauseBanner);
        }
        this.pauseBanner.style.display = show ? 'block' : 'none';
    }

    async manualRefresh() {
        await this.updatePingStatus();
        if (this.currentCommand) {
            await this.updateCommandData(this.currentCommand);
        }
    }

    startPolling() {
        if (!this.autoRefresh) return;

        this.isPolling = true;

        // Poll ping status
        this.pingPollTimer = setInterval(() => {
            if (this.autoRefresh) {
                this.updatePingStatus();
            }
        }, this.config.ping_poll_interval_seconds * 1000);

        // Poll run data
        this.runPollTimer = setInterval(() => {
            if (this.autoRefresh && this.currentCommand) {
                this.updateCommandData(this.currentCommand);
            }
        }, this.config.run_poll_interval_seconds * 1000);
    }

    stopPolling() {
        this.isPolling = false;

        if (this.pingPollTimer) {
            clearInterval(this.pingPollTimer);
            this.pingPollTimer = null;
        }
        if (this.runPollTimer) {
            clearInterval(this.runPollTimer);
            this.runPollTimer = null;
        }
    }

    renderCommandTabs() {
        const tabsContainer = document.getElementById('commandTabs');
        tabsContainer.innerHTML = '';

        this.commands.forEach(command => {
            const tab = document.createElement('button');
            tab.className = 'tab';
            tab.textContent = command;
            tab.addEventListener('click', () => this.switchToCommand(command));
            tabsContainer.appendChild(tab);
        });
    }

    async switchToCommand(command) {
        this.currentCommand = command;

        // Update active tab
        document.querySelectorAll('.tab').forEach(tab => {
            if (tab.textContent === command) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        // Load command data
        await this.updateCommandData(command);
        this.updateScheduleProgressDisplays();
    }

    async updateCommandData(command) {
        try {
            // Fetch side-by-side data for character-level diff
            const sideBySideResponse = await fetch(`/api/runs/${encodeURIComponent(command)}/side_by_side`);
            const sideBySideData = await sideBySideResponse.json();
            this.latestSideBySideData[command] = sideBySideData;

            // Also fetch regular run data for history
            const response = await fetch(`/api/runs/${encodeURIComponent(command)}`);
            const data = await response.json();

            this.renderCommandContent(command, data.runs, sideBySideData);
            this.updateScheduleProgressDisplays();
        } catch (error) {
            this.logClientError('COMMAND_DATA_LOAD_FAILED', error, { command });
        }
    }

    getCommandSchedule(command) {
        const schedule = this.collectorState.command_schedule || {};
        return schedule[command] || null;
    }

    getScheduleDisplayState(command) {
        const status = this.collectorState.status || 'unknown';

        if (this.collectorState.commands_paused || status === 'paused') {
            return { label: 'Paused', percent: 0, unavailable: true };
        }
        if (this.collectorState.manual_mode || status === 'manual') {
            return { label: 'Manual', percent: 0, unavailable: true };
        }
        if (status === 'not_running' || status === 'stopped' || status === 'unknown') {
            return { label: 'Schedule unavailable', percent: 0, unavailable: true };
        }

        const schedule = this.getCommandSchedule(command);
        if (!schedule || !schedule.interval_seconds || !schedule.next_run_epoch) {
            return { label: 'Schedule unavailable', percent: 0, unavailable: true };
        }

        const interval = Math.max(1, Number(schedule.interval_seconds));
        const nextRun = Number(schedule.next_run_epoch);
        const remaining = Math.max(0, Math.ceil(nextRun - Date.now() / 1000));
        const percent = Math.max(0, Math.min(100, (remaining / interval) * 100));

        return {
            label: remaining <= 0 ? 'Due now' : `Next run: ${remaining}s`,
            percent,
            unavailable: false
        };
    }

    createScheduleProgress(command) {
        const wrapper = document.createElement('div');
        wrapper.className = 'command-schedule-progress';
        wrapper.dataset.command = command;

        const label = document.createElement('span');
        label.className = 'command-schedule-label';
        wrapper.appendChild(label);

        const track = document.createElement('span');
        track.className = 'command-schedule-track';

        const fill = document.createElement('span');
        fill.className = 'command-schedule-fill';
        track.appendChild(fill);
        wrapper.appendChild(track);

        return wrapper;
    }

    updateScheduleProgressDisplays() {
        document.querySelectorAll('.command-schedule-progress').forEach(progress => {
            const command = progress.dataset.command || this.currentCommand;
            if (!command) {
                return;
            }

            const state = this.getScheduleDisplayState(command);
            const label = progress.querySelector('.command-schedule-label');
            const fill = progress.querySelector('.command-schedule-fill');
            if (label) {
                label.textContent = state.label;
            }
            if (fill) {
                fill.style.width = `${state.percent}%`;
            }
            progress.classList.toggle('schedule-unavailable', state.unavailable);
        });
    }

    renderCommandContent(command, runsData, sideBySideData) {
        const contentContainer = document.getElementById('commandContent');

        // Save current diff states before clearing
        this.saveDiffStates(command);
        this.saveSideBySideScrollStates(command);

        contentContainer.innerHTML = '';

        // Check if we have side-by-side data
        if (sideBySideData && sideBySideData.devices && sideBySideData.devices.length >= 2) {
            // Render side-by-side comparison view
            this.renderSideBySideView(command, this.getDisplayedSideBySideData(command, sideBySideData));

            // Add separator
            const separator = document.createElement('hr');
            separator.style.margin = '30px 0';
            contentContainer.appendChild(separator);
        }

        // Render traditional per-device run history
        for (const [device, runs] of Object.entries(runsData)) {
            const deviceSection = document.createElement('div');
            deviceSection.className = 'device-section';

            const deviceHeader = document.createElement('div');
            deviceHeader.className = 'device-header-section';

            const deviceTitle = document.createElement('h3');
            deviceTitle.textContent = `Device: ${device}`;
            deviceHeader.appendChild(deviceTitle);
            deviceHeader.appendChild(this.createScheduleProgress(command));

            // Add bulk export button
            const bulkExportBtn = document.createElement('button');
            bulkExportBtn.className = 'bulk-export-btn';
            bulkExportBtn.textContent = '📦 Export All Outputs (JSON)';
            bulkExportBtn.addEventListener('click', () => this.exportBulk(command));
            deviceHeader.appendChild(bulkExportBtn);

            deviceSection.appendChild(deviceHeader);

            // Render run history
            const historyDiv = document.createElement('div');
            historyDiv.className = 'run-history';

            if (runs.length === 0) {
                historyDiv.innerHTML = '<p class="loading">No data available</p>';
            } else {
                runs.forEach((run, index) => {
                    // Attach device name to run for export
                    run._device = device;
                    const runEntry = this.createRunEntry(run, command, index);
                    historyDiv.appendChild(runEntry);
                });
            }

            deviceSection.appendChild(historyDiv);

            // Add diff section for this device
            const diffSection = this.createDiffSection(command, device);
            deviceSection.appendChild(diffSection);

            contentContainer.appendChild(deviceSection);
        }

        // Restore diff states after rendering
        this.restoreDiffStates(command);
        this.restoreSideBySideScrollStates(command);
    }

    getSideBySideScrollKey(command, deviceName) {
        return `${command}:${deviceName}`;
    }

    saveSideBySideScrollStates(command) {
        document.querySelectorAll('.device-panel').forEach(panel => {
            const deviceName = panel.dataset.deviceName;
            const output = panel.querySelector('.device-panel-output');

            if (!deviceName || !output) {
                return;
            }

            this.sideBySideScrollStates[this.getSideBySideScrollKey(command, deviceName)] = {
                scrollTop: output.scrollTop,
                scrollLeft: output.scrollLeft
            };
        });
    }

    restoreSideBySideScrollStates(command) {
        try {
            this.isSyncingSideBySideScroll = true;
            document.querySelectorAll('.device-panel').forEach(panel => {
                const deviceName = panel.dataset.deviceName;
                const output = panel.querySelector('.device-panel-output');

                if (!deviceName || !output) {
                    return;
                }

                const state = this.sideBySideScrollStates[this.getSideBySideScrollKey(command, deviceName)];
                if (!state) {
                    return;
                }

                output.scrollTop = Math.max(0, Math.min(state.scrollTop, output.scrollHeight - output.clientHeight));
                output.scrollLeft = Math.max(0, Math.min(state.scrollLeft, output.scrollWidth - output.clientWidth));
            });
        } finally {
            this.isSyncingSideBySideScroll = false;
        }
    }

    syncSideBySideScroll(sourceOutput) {
        if (!this.sideBySideScrollSyncEnabled || this.isSyncingSideBySideScroll) {
            return;
        }

        const sideBySideSection = sourceOutput.closest('.side-by-side-section');
        if (!sideBySideSection) {
            return;
        }

        try {
            this.isSyncingSideBySideScroll = true;
            sideBySideSection.querySelectorAll('.device-panel-output').forEach(output => {
                if (output === sourceOutput) {
                    return;
                }

                output.scrollTop = sourceOutput.scrollTop;
                output.scrollLeft = sourceOutput.scrollLeft;
            });
        } finally {
            this.isSyncingSideBySideScroll = false;
        }
    }

    setupSideBySideScrollSync(outputContainer) {
        outputContainer.addEventListener('scroll', () => {
            this.syncSideBySideScroll(outputContainer);
        });
    }

    setupSideBySideScrollSyncDelegation(sideBySideSection) {
        sideBySideSection.addEventListener('scroll', event => {
            if (!event.target.classList || !event.target.classList.contains('device-panel-output')) {
                return;
            }

            this.syncSideBySideScroll(event.target);
        }, true);
    }

    setupSideBySideScrollSyncWatcher(sideBySideSection) {
        const positions = new WeakMap();

        const rememberPositions = () => {
            sideBySideSection.querySelectorAll('.device-panel-output').forEach(output => {
                positions.set(output, {
                    scrollTop: output.scrollTop,
                    scrollLeft: output.scrollLeft
                });
            });
        };

        const watch = () => {
            if (!sideBySideSection.isConnected) {
                return;
            }

            if (!this.isSyncingSideBySideScroll && this.sideBySideScrollSyncEnabled) {
                const changedOutput = Array.from(
                    sideBySideSection.querySelectorAll('.device-panel-output')
                ).find(output => {
                    const position = positions.get(output);
                    return position && (
                        position.scrollTop !== output.scrollTop ||
                        position.scrollLeft !== output.scrollLeft
                    );
                });

                if (changedOutput) {
                    this.syncSideBySideScroll(changedOutput);
                }
            }

            rememberPositions();
            setTimeout(watch, 100);
        };

        rememberPositions();
        setTimeout(watch, 100);
    }

    updateScrollSyncToggle(button) {
        button.classList.toggle('active', this.sideBySideScrollSyncEnabled);
        button.setAttribute('aria-pressed', String(this.sideBySideScrollSyncEnabled));
        button.textContent = this.sideBySideScrollSyncEnabled ? 'Sync Scroll' : 'Independent Scroll';
        button.title = this.sideBySideScrollSyncEnabled
            ? 'Disable synchronized side-by-side scrolling'
            : 'Enable synchronized side-by-side scrolling';
    }

    createScrollSyncToggle() {
        const button = document.createElement('button');
        button.className = 'scroll-sync-toggle';
        button.type = 'button';
        this.updateScrollSyncToggle(button);
        button.addEventListener('click', () => {
            this.setSideBySideScrollSyncEnabled(!this.sideBySideScrollSyncEnabled);
        });
        return button;
    }

    getDisplayedSideBySideData(command, latestData) {
        const snapshot = this.outputSnapshots[command];
        const mode = this.outputViewModes[command] || 'latest';

        if (mode === 'snapshot' && snapshot) {
            return {
                ...snapshot.data,
                output_view_mode: 'snapshot',
                snapshot_available: true,
                snapshot_captured_at: snapshot.capturedAt
            };
        }

        return {
            ...latestData,
            output_view_mode: 'latest',
            snapshot_available: Boolean(snapshot),
            snapshot_captured_at: snapshot ? snapshot.capturedAt : null
        };
    }

    createOutputSnapshotControls(command, sideBySideData) {
        const toolbar = document.createElement('div');
        toolbar.className = 'output-snapshot-controls';

        const latestBtn = document.createElement('button');
        latestBtn.className = 'snapshot-mode-btn';
        latestBtn.textContent = 'Latest';
        latestBtn.addEventListener('click', () => {
            this.outputViewModes[command] = 'latest';
            this.updateCommandData(command);
        });

        const snapshotBtn = document.createElement('button');
        snapshotBtn.className = 'snapshot-mode-btn';
        snapshotBtn.textContent = 'Snapshot';
        snapshotBtn.disabled = !this.outputSnapshots[command];
        snapshotBtn.addEventListener('click', () => {
            this.outputViewModes[command] = 'snapshot';
            this.updateCommandData(command);
        });

        const captureBtn = document.createElement('button');
        captureBtn.className = 'capture-snapshot-btn';
        captureBtn.textContent = 'Capture Snapshot';
        captureBtn.disabled = !sideBySideData || !sideBySideData.devices || sideBySideData.devices.length === 0;
        captureBtn.addEventListener('click', () => this.captureOutputSnapshot(command));

        const status = document.createElement('span');
        status.className = 'snapshot-status';

        const mode = this.outputViewModes[command] || 'latest';
        latestBtn.classList.toggle('active', mode !== 'snapshot');
        snapshotBtn.classList.toggle('active', mode === 'snapshot');

        const snapshot = this.outputSnapshots[command];
        if (mode === 'snapshot' && snapshot) {
            status.textContent = `Showing snapshot captured ${this.formatTimestampJST(snapshot.capturedAt)}`;
        } else if (snapshot) {
            status.textContent = `Snapshot available from ${this.formatTimestampJST(snapshot.capturedAt)}`;
        } else {
            status.textContent = 'Showing latest command output';
        }

        toolbar.appendChild(latestBtn);
        toolbar.appendChild(snapshotBtn);
        toolbar.appendChild(captureBtn);
        toolbar.appendChild(this.createScrollSyncToggle());
        toolbar.appendChild(status);
        return toolbar;
    }

    createSideBySideDiffModeControls(command) {
        const toolbar = document.createElement('div');
        toolbar.className = 'side-by-side-diff-controls';
        toolbar.setAttribute('role', 'group');
        toolbar.setAttribute('aria-label', 'Side-by-side diff display mode');

        [
            { value: 'char', label: 'Character' },
            { value: 'line', label: 'Line' },
            { value: 'git', label: 'Git' }
        ].forEach(option => {
            const button = document.createElement('button');
            button.className = 'diff-mode-btn';
            button.type = 'button';
            button.textContent = option.label;
            button.setAttribute('aria-pressed', this.sideBySideDiffMode === option.value ? 'true' : 'false');
            button.classList.toggle('active', this.sideBySideDiffMode === option.value);
            button.addEventListener('click', () => this.setSideBySideDiffMode(option.value, command));
            toolbar.appendChild(button);
        });

        return toolbar;
    }

    captureOutputSnapshot(command) {
        const latestData = this.latestSideBySideData[command];
        if (!latestData || !latestData.devices || latestData.devices.length === 0) {
            alert('No command output is available to capture.');
            return;
        }

        this.outputSnapshots[command] = {
            capturedAt: Math.floor(Date.now() / 1000),
            data: JSON.parse(JSON.stringify(latestData))
        };
        this.outputViewModes[command] = 'snapshot';
        this.updateCommandData(command);
    }

    renderSideBySideView(command, sideBySideData) {
        const contentContainer = document.getElementById('commandContent');

        // Create side-by-side section
        const sideBySideSection = document.createElement('div');
        sideBySideSection.className = 'side-by-side-section';
        this.setupSideBySideScrollSyncDelegation(sideBySideSection);
        this.setupSideBySideScrollSyncWatcher(sideBySideSection);

        const sectionHeader = document.createElement('div');
        sectionHeader.className = 'side-by-side-header';

        const title = document.createElement('h2');
        title.textContent = 'Side-by-Side Command Output';
        sectionHeader.appendChild(title);
        const headerControls = document.createElement('div');
        headerControls.className = 'side-by-side-header-controls';
        headerControls.appendChild(this.createSideBySideDiffModeControls(command));
        headerControls.appendChild(this.createOutputSnapshotControls(command, sideBySideData));
        sectionHeader.appendChild(headerControls);
        sideBySideSection.appendChild(sectionHeader);

        // Container for the two device outputs
        const comparisonContainer = document.createElement('div');
        comparisonContainer.className = 'comparison-container';
        const sideBySideDiffRows = this.buildSideBySideDiffRows(sideBySideData.devices);

        // Render each device
        sideBySideData.devices.forEach((deviceData, index) => {
            const devicePanel = document.createElement('div');
            devicePanel.className = 'device-panel';
            devicePanel.dataset.deviceName = deviceData.name;

            // Device header
            const header = document.createElement('div');
            header.className = 'device-panel-header';

            const deviceName = document.createElement('h3');
            deviceName.textContent = deviceData.name;
            header.appendChild(deviceName);
            header.appendChild(this.createScheduleProgress(command));

            // Metadata
            const meta = document.createElement('div');
            meta.className = 'device-panel-meta';
            const timestamp = this.formatTimestampJST(deviceData.run.ts_epoch);
            const duration = deviceData.run.duration_ms ? `${deviceData.run.duration_ms.toFixed(2)}ms` : 'N/A';
            meta.innerHTML = `
                <span>${timestamp}</span> |
                Duration: ${duration}
                ${deviceData.run.original_line_count ? ` | Lines: ${deviceData.run.original_line_count}` : ''}
            `;
            header.appendChild(meta);

            // Badges
            const badges = document.createElement('div');
            badges.className = 'run-badges';

            if (deviceData.run.ok) {
                const badge = document.createElement('span');
                badge.className = 'badge success';
                badge.textContent = 'Success';
                badges.appendChild(badge);
            } else {
                const badge = document.createElement('span');
                badge.className = 'badge error';
                badge.textContent = 'Error';
                badges.appendChild(badge);
            }

            if (deviceData.run.is_filtered) {
                const badge = document.createElement('span');
                badge.className = 'badge filtered';
                badge.textContent = 'Filtered';
                badges.appendChild(badge);
            }

            if (deviceData.run.is_truncated) {
                const badge = document.createElement('span');
                badge.className = 'badge truncated';
                badge.textContent = 'Truncated';
                badges.appendChild(badge);
            }

            header.appendChild(badges);
            devicePanel.appendChild(header);

            // Output with character-level diff highlighting
            const outputContainer = document.createElement('div');
            outputContainer.className = 'device-panel-output';
            outputContainer.style.maxHeight = `${this.sideBySideOutputHeight}px`;
            outputContainer.style.height = `${this.sideBySideOutputHeight}px`;
            this.setupSideBySideScrollSync(outputContainer);

            if (deviceData.run.ok) {
                outputContainer.appendChild(this.renderSideBySideOutput(deviceData, index, sideBySideDiffRows));
            } else {
                const errorMsg = document.createElement('div');
                errorMsg.className = 'error-message';
                errorMsg.textContent = `Error: ${this.formatRunError(deviceData.run)}`;
                outputContainer.appendChild(errorMsg);
            }

            devicePanel.appendChild(outputContainer);
            comparisonContainer.appendChild(devicePanel);
        });

        sideBySideSection.appendChild(comparisonContainer);

        const resizeHandle = document.createElement('div');
        resizeHandle.className = 'comparison-resize-handle';
        resizeHandle.setAttribute('role', 'separator');
        resizeHandle.setAttribute('aria-orientation', 'horizontal');
        resizeHandle.setAttribute('tabindex', '0');
        resizeHandle.title = 'Drag to resize comparison output height';
        resizeHandle.textContent = 'Drag to resize';
        this.setupComparisonResizeHandle(resizeHandle);
        sideBySideSection.appendChild(resizeHandle);

        contentContainer.appendChild(sideBySideSection);
    }

    renderSideBySideOutput(deviceData, deviceIndex, diffRows) {
        if (this.sideBySideDiffMode === 'line' || this.sideBySideDiffMode === 'git') {
            return this.renderLineBasedSideBySideOutput(diffRows, deviceIndex, this.sideBySideDiffMode);
        }

        const outputPre = document.createElement('pre');
        outputPre.className = 'output-text-char-diff';
        outputPre.innerHTML = deviceData.run.output_html || this.escapeHtml(deviceData.run.output_text);
        return outputPre;
    }

    buildSideBySideDiffRows(devices) {
        if (!devices || devices.length < 2) {
            return [];
        }

        const oldLines = (devices[0].run.output_text || '').split('\n');
        const newLines = (devices[1].run.output_text || '').split('\n');
        const table = Array.from({ length: oldLines.length + 1 }, () => (
            Array(newLines.length + 1).fill(0)
        ));

        for (let i = oldLines.length - 1; i >= 0; i -= 1) {
            for (let j = newLines.length - 1; j >= 0; j -= 1) {
                if (oldLines[i] === newLines[j]) {
                    table[i][j] = table[i + 1][j + 1] + 1;
                } else {
                    table[i][j] = Math.max(table[i + 1][j], table[i][j + 1]);
                }
            }
        }

        const rows = [];
        let i = 0;
        let j = 0;
        while (i < oldLines.length && j < newLines.length) {
            if (oldLines[i] === newLines[j]) {
                rows.push({ left: oldLines[i], right: newLines[j], leftType: 'context', rightType: 'context' });
                i += 1;
                j += 1;
            } else if (table[i + 1][j] >= table[i][j + 1]) {
                rows.push({ left: oldLines[i], right: '', leftType: 'remove', rightType: 'empty' });
                i += 1;
            } else {
                rows.push({ left: '', right: newLines[j], leftType: 'empty', rightType: 'add' });
                j += 1;
            }
        }

        while (i < oldLines.length) {
            rows.push({ left: oldLines[i], right: '', leftType: 'remove', rightType: 'empty' });
            i += 1;
        }
        while (j < newLines.length) {
            rows.push({ left: '', right: newLines[j], leftType: 'empty', rightType: 'add' });
            j += 1;
        }

        return rows;
    }

    renderLineBasedSideBySideOutput(diffRows, deviceIndex, mode) {
        const output = document.createElement('div');
        output.className = `output-text-line-diff output-text-line-diff-${mode}`;

        diffRows.forEach(row => {
            const line = document.createElement('div');
            const type = deviceIndex === 0 ? row.leftType : row.rightType;
            const text = deviceIndex === 0 ? row.left : row.right;
            line.className = `side-diff-line side-diff-line-${type}`;

            if (mode === 'git') {
                const prefix = document.createElement('span');
                prefix.className = 'side-diff-prefix';
                if (type === 'remove') {
                    prefix.textContent = '-';
                } else if (type === 'add') {
                    prefix.textContent = '+';
                } else {
                    prefix.textContent = ' ';
                }
                line.appendChild(prefix);
            }

            const content = document.createElement('span');
            content.className = 'side-diff-content';
            content.textContent = text || ' ';
            line.appendChild(content);
            output.appendChild(line);
        });

        return output;
    }

    setupComparisonResizeHandle(handle) {
        let startY = 0;
        let startHeight = this.sideBySideOutputHeight;

        const stopResize = () => {
            document.body.classList.remove('comparison-resizing');
            window.removeEventListener('mousemove', resize);
            window.removeEventListener('mouseup', stopResize);
        };

        const resize = (event) => {
            const deltaY = event.clientY - startY;
            this.setSideBySideOutputHeight(startHeight + deltaY);
        };

        handle.addEventListener('mousedown', (event) => {
            event.preventDefault();
            startY = event.clientY;
            startHeight = this.sideBySideOutputHeight;
            document.body.classList.add('comparison-resizing');
            window.addEventListener('mousemove', resize);
            window.addEventListener('mouseup', stopResize);
        });

        handle.addEventListener('keydown', (event) => {
            if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') {
                return;
            }
            event.preventDefault();
            const step = event.shiftKey ? 80 : 24;
            const direction = event.key === 'ArrowDown' ? 1 : -1;
            this.setSideBySideOutputHeight(this.sideBySideOutputHeight + (step * direction));
        });
    }

    createRunEntry(run, command, index) {
        const entry = document.createElement('div');
        entry.className = 'run-entry';

        // Header
        const header = document.createElement('div');
        header.className = 'run-header';

        const meta = document.createElement('div');
        meta.className = 'run-meta';

        const timestamp = this.formatTimestampJST(run.ts_epoch);
        const duration = run.duration_ms ? `${run.duration_ms.toFixed(2)}ms` : 'N/A';

        meta.innerHTML = `
            <span class="timestamp">${timestamp}</span> |
            Duration: ${duration}
            ${run.original_line_count ? ` | Lines: ${run.original_line_count}` : ''}
        `;

        const badges = document.createElement('div');
        badges.className = 'run-badges';

        if (run.ok) {
            const badge = document.createElement('span');
            badge.className = 'badge success';
            badge.textContent = 'Success';
            badges.appendChild(badge);
        } else {
            const badge = document.createElement('span');
            badge.className = 'badge error';
            badge.textContent = 'Error';
            badges.appendChild(badge);
        }

        if (run.is_filtered) {
            const badge = document.createElement('span');
            badge.className = 'badge filtered';
            badge.textContent = 'Filtered';
            badges.appendChild(badge);
        }

        if (run.is_truncated) {
            const badge = document.createElement('span');
            badge.className = 'badge truncated';
            badge.textContent = 'Truncated';
            badges.appendChild(badge);
        }

        header.appendChild(meta);
        header.appendChild(badges);

        // Output (initially hidden)
        const output = document.createElement('div');
        output.className = 'run-output';

        if (run.ok) {
            const outputText = document.createElement('pre');
            outputText.className = 'output-text';
            outputText.textContent = run.output_text || '(no output)';
            output.appendChild(outputText);
        } else {
            const errorMsg = document.createElement('div');
            errorMsg.className = 'error-message';
            errorMsg.textContent = `Error: ${this.formatRunError(run)}`;
            output.appendChild(errorMsg);
        }

        // Toggle visibility on header click
        header.addEventListener('click', () => {
            output.classList.toggle('visible');
        });

        // Auto-expand first entry
        if (index === 0) {
            output.classList.add('visible');
        }

        entry.appendChild(header);
        entry.appendChild(output);

        // Add export buttons
        if (run.ok) {
            const exportControls = this.createExportControls(run, command, index);
            entry.appendChild(exportControls);
        }

        return entry;
    }

    createExportControls(run, command, index) {
        const controls = document.createElement('div');
        controls.className = 'export-controls';

        // Get device name from the DOM context (will be set by parent)
        const deviceName = run._device || '';

        const exportTextBtn = document.createElement('button');
        exportTextBtn.className = 'export-btn';
        exportTextBtn.textContent = '📄 Export as Text';
        exportTextBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.exportRun(command, deviceName, 'text');
        });

        const exportJsonBtn = document.createElement('button');
        exportJsonBtn.className = 'export-btn';
        exportJsonBtn.textContent = '📋 Export as JSON';
        exportJsonBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.exportRun(command, deviceName, 'json');
        });

        controls.appendChild(exportTextBtn);
        controls.appendChild(exportJsonBtn);

        return controls;
    }

    exportRun(command, device, format) {
        try {
            const url = `/api/export/run?command=${encodeURIComponent(command)}&device=${encodeURIComponent(device)}&format=${format}`;
            window.location.href = url;
        } catch (error) {
            console.error('Error exporting run:', error);
            alert('Failed to export data');
        }
    }

    exportBulk(command) {
        try {
            const url = `/api/export/bulk?command=${encodeURIComponent(command)}&format=json`;
            window.location.href = url;
        } catch (error) {
            console.error('Error exporting bulk data:', error);
            alert('Failed to export bulk data');
        }
    }

    createDiffSection(command, device) {
        const section = document.createElement('div');
        section.className = 'diff-section';

        const header = document.createElement('h3');
        header.textContent = 'Diff Views';
        section.appendChild(header);

        const controls = document.createElement('div');
        controls.className = 'diff-controls';

        // History diff button
        const historyBtn = document.createElement('button');
        historyBtn.textContent = 'Show History Diff';
        historyBtn.addEventListener('click', () => this.showHistoryDiff(command, device));
        controls.appendChild(historyBtn);

        // Device diff controls (if multiple devices)
        if (this.devices.length > 1) {
            const label = document.createElement('label');
            label.textContent = 'Compare with: ';
            controls.appendChild(label);

            const select = document.createElement('select');
            this.devices.forEach(dev => {
                if (dev !== device) {
                    const option = document.createElement('option');
                    option.value = dev;
                    option.textContent = dev;
                    select.appendChild(option);
                }
            });
            controls.appendChild(select);

            const deviceDiffBtn = document.createElement('button');
            deviceDiffBtn.textContent = 'Show Device Diff';
            deviceDiffBtn.addEventListener('click', () => {
                const otherDevice = select.value;
                this.showDeviceDiff(command, device, otherDevice);
            });
            controls.appendChild(deviceDiffBtn);
        }

        section.appendChild(controls);

        // Diff output
        const diffOutput = document.createElement('div');
        diffOutput.className = 'diff-output';
        diffOutput.id = `diff-${device}`;
        diffOutput.textContent = this.DIFF_PLACEHOLDER_TEXT;
        section.appendChild(diffOutput);

        // Diff export controls
        const exportControls = document.createElement('div');
        exportControls.className = 'diff-export-controls';
        exportControls.style.display = 'none';  // Hidden until diff is shown
        exportControls.id = `diff-export-${device}`;

        const exportHtmlBtn = document.createElement('button');
        exportHtmlBtn.className = 'export-btn';
        exportHtmlBtn.textContent = '📄 Export Diff (HTML)';
        exportHtmlBtn.addEventListener('click', () => this.exportDiff(command, device, 'html'));

        const exportTextBtn = document.createElement('button');
        exportTextBtn.className = 'export-btn';
        exportTextBtn.textContent = '📋 Export Diff (Text)';
        exportTextBtn.addEventListener('click', () => this.exportDiff(command, device, 'text'));

        exportControls.appendChild(exportHtmlBtn);
        exportControls.appendChild(exportTextBtn);
        section.appendChild(exportControls);

        return section;
    }

    async showHistoryDiff(command, device) {
        try {
            const response = await fetch(
                `/api/diff/history?command=${encodeURIComponent(command)}&device=${encodeURIComponent(device)}&origin_mode=previous`
            );
            const data = await response.json();

            const diffOutput = document.getElementById(`diff-${device}`);
            this.renderDiff(
                diffOutput,
                data.diff,
                'No differences found',
                data.diff_format === 'html'
            );
            // Show export controls and store diff context
            const exportControls = document.getElementById(`diff-export-${device}`);
            if (exportControls) {
                exportControls.style.display = 'block';
                exportControls.dataset.diffType = 'history';
                exportControls.dataset.command = command;
                exportControls.dataset.device = device;
                exportControls.dataset.originMode = 'previous';
            }

            // Save the diff state immediately
            const stateKey = `${command}:${device}`;
            this.diffStates[stateKey] = {
                type: 'history',
                content: diffOutput.innerHTML,
                isHtml: diffOutput.classList.contains('diff-output-html'),
                command: command,
                device: device
            };
        } catch (error) {
            this.logClientError('HISTORY_DIFF_LOAD_FAILED', error, { command, device });
        }
    }

    async showDeviceDiff(command, deviceA, deviceB) {
        try {
            const response = await fetch(
                `/api/diff/devices?command=${encodeURIComponent(command)}&device_a=${encodeURIComponent(deviceA)}&device_b=${encodeURIComponent(deviceB)}`
            );
            const data = await response.json();

            const diffOutputs = [
                document.getElementById(`diff-${deviceA}`),
                document.getElementById(`diff-${deviceB}`)
            ];
            diffOutputs.forEach(output => {
                if (!output) return;
                this.renderDiff(
                    output,
                    data.diff,
                    'No differences found',
                    data.diff_format === 'html'
                );
            });

            // Show export controls and store diff context
            const exportControlTargets = [
                document.getElementById(`diff-export-${deviceA}`),
                document.getElementById(`diff-export-${deviceB}`)
            ];
            exportControlTargets.forEach(exportControls => {
                if (!exportControls) return;
                exportControls.style.display = 'block';
                exportControls.dataset.diffType = 'device';
                exportControls.dataset.command = command;
                exportControls.dataset.deviceA = deviceA;
                exportControls.dataset.deviceB = deviceB;
            });

            // Save the diff state for both devices
            // Only save if we have valid diff output
            if (diffOutputs && diffOutputs.length > 0 && diffOutputs[0]) {
                const isHtml = diffOutputs[0].classList.contains('diff-output-html');
                const content = diffOutputs[0].innerHTML;

                [deviceA, deviceB].forEach(device => {
                    const stateKey = `${command}:${device}`;
                    this.diffStates[stateKey] = {
                        type: 'device',
                        content: content,
                        isHtml: isHtml,
                        otherDevice: device === deviceA ? deviceB : deviceA,
                        command: command,
                        device: device
                    };
                });
            }
        } catch (error) {
            this.logClientError('DEVICE_DIFF_LOAD_FAILED', error, { command, deviceA, deviceB });
        }
    }

    exportDiff(command, device, format) {
        const exportControls = document.getElementById(`diff-export-${device}`);
        if (!exportControls) return;

        const diffType = exportControls.dataset.diffType;
        let url;

        if (diffType === 'history') {
            const originMode = exportControls.dataset.originMode || 'previous';
            url = `/api/export/diff?command=${encodeURIComponent(command)}&device=${encodeURIComponent(device)}&format=${format}&origin_mode=${originMode}`;
        } else if (diffType === 'device') {
            const deviceA = exportControls.dataset.deviceA;
            const deviceB = exportControls.dataset.deviceB;
            url = `/api/export/diff?command=${encodeURIComponent(command)}&device_a=${encodeURIComponent(deviceA)}&device_b=${encodeURIComponent(deviceB)}&format=${format}`;
        } else {
            console.error('Unknown diff type');
            return;
        }

        try {
            window.location.href = url;
        } catch (error) {
            console.error('Error exporting diff:', error);
            alert('Failed to export diff');
        }
    }

    escapeHtml(text) {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    renderDiff(element, diffText, fallbackMessage, isHtml = false) {
        element.classList.remove('diff-output-html');

        if (!diffText || diffText.length === 0) {
            element.textContent = fallbackMessage;
            return;
        }

        if (isHtml) {
            const parsed = new DOMParser().parseFromString(diffText, 'text/html');
            parsed.querySelectorAll('script').forEach(node => node.remove());
            parsed.querySelectorAll('*').forEach(node => {
                Array.from(node.attributes).forEach(attr => {
                    const name = attr.name.toLowerCase();
                    const value = (attr.value || '').trim();
                    const lowerValue = value.toLowerCase();
                    const unsafeProtocols = ['javascript:', 'vbscript:', 'data:text/html'];
                    if (name.startsWith('on')) {
                        node.removeAttribute(attr.name);
                    }
                    if ((name === 'href' || name === 'src') && unsafeProtocols.some(proto => lowerValue.startsWith(proto))) {
                        node.removeAttribute(attr.name);
                    }
                    if (name === 'style' && /expression|javascript:/i.test(value)) {
                        node.removeAttribute(attr.name);
                    }
                });
            });
            element.innerHTML = '';
            element.append(...Array.from(parsed.body.childNodes));
            element.classList.add('diff-output-html');
            return;
        }

        const lines = diffText.split('\n');
        if (lines.length === 0 || lines.every(l => l.trim() === '')) {
            element.textContent = fallbackMessage;
            return;
        }

        const html = lines.map(line => {
            let cls = '';
            if (line.startsWith('+')) {
                cls = 'diff-add';
            } else if (line.startsWith('-')) {
                cls = 'diff-remove';
            } else if (line.startsWith('@@')) {
                cls = 'diff-hunk';
            }
            return `<div class="${cls}">${this.escapeHtml(line)}</div>`;
        }).join('');

        element.innerHTML = html;
    }

    saveDiffStates(command) {
        // Save the state of all visible diffs for the current command
        this.devices.forEach(device => {
            const diffOutputElement = document.getElementById(`diff-${device}`);
            const exportControlsElement = document.getElementById(`diff-export-${device}`);

            if (!diffOutputElement || !exportControlsElement) {
                return;
            }

            // Check if there's actual diff content (not just the placeholder text)
            const hasContent = diffOutputElement.textContent !== this.DIFF_PLACEHOLDER_TEXT &&
                               diffOutputElement.innerHTML.trim().length > 0;

            // Check if export controls are visible (more robust check)
            const isVisible = exportControlsElement.style.display === 'block' ||
                            (exportControlsElement.style.display !== 'none' &&
                             exportControlsElement.offsetParent !== null);

            if (hasContent && isVisible) {
                const stateKey = `${command}:${device}`;
                const diffType = exportControlsElement.dataset.diffType;
                const otherDevice = exportControlsElement.dataset.deviceB;

                // Store the diff state
                this.diffStates[stateKey] = {
                    type: diffType,
                    content: diffOutputElement.innerHTML,
                    isHtml: diffOutputElement.classList.contains('diff-output-html'),
                    otherDevice: otherDevice,
                    command: command,
                    device: device
                };
            } else {
                // Remove state if diff is not visible
                const stateKey = `${command}:${device}`;
                delete this.diffStates[stateKey];
            }
        });
    }

    restoreDiffStates(command) {
        // Restore previously visible diffs for the current command
        this.devices.forEach(device => {
            const stateKey = `${command}:${device}`;
            const state = this.diffStates[stateKey];

            if (!state) {
                return;
            }

            const diffOutputElement = document.getElementById(`diff-${device}`);
            const exportControlsElement = document.getElementById(`diff-export-${device}`);

            if (!diffOutputElement || !exportControlsElement) {
                return;
            }

            // Restore the diff content
            diffOutputElement.innerHTML = state.content;
            if (state.isHtml) {
                diffOutputElement.classList.add('diff-output-html');
            }

            // Restore export controls visibility and metadata
            exportControlsElement.style.display = 'block';
            exportControlsElement.dataset.diffType = state.type;
            exportControlsElement.dataset.command = state.command;
            exportControlsElement.dataset.device = state.device;
            if (state.otherDevice) {
                exportControlsElement.dataset.deviceB = state.otherDevice;
            }
        });
    }

    async updatePingStatus() {
        try {
            const response = await fetch(
                `/api/ping?window_seconds=${this.config.ping_window_seconds}`
            );
            const data = await response.json();

            this.renderPingStatus(data.ping_status);
        } catch (error) {
            console.error('Error loading ping status:', error);
        }
    }

    renderPingStatus(pingStatus) {
        const monitorContainer = document.getElementById('monitorPingTiles');
        const deviceContainer = document.getElementById('devicePingTiles');
        monitorContainer.innerHTML = '';
        deviceContainer.innerHTML = '';

        const deviceNames = new Set(this.devices);
        let monitorCount = 0;
        let deviceCount = 0;

        for (const [device, status] of Object.entries(pingStatus)) {
            const tile = this.createPingTile(device, status);
            if (deviceNames.has(device)) {
                deviceContainer.appendChild(tile);
                deviceCount += 1;
            } else {
                tile.classList.add('monitor-ping-tile');
                monitorContainer.appendChild(tile);
                monitorCount += 1;
            }
        }

        if (Object.keys(pingStatus).length === 0) {
            monitorContainer.innerHTML = '<p class="loading">No ping data available</p>';
        } else if (monitorCount === 0) {
            monitorContainer.innerHTML = '<p class="loading">No standalone monitor data available</p>';
        }

        if (deviceCount === 0 && Object.keys(pingStatus).length > 0) {
            deviceContainer.innerHTML = '<p class="loading">No device ping data available</p>';
        }
    }

    createPingTile(device, status) {
        const tile = document.createElement('div');
        tile.className = `ping-tile ${status.status}`;
        const isExpanded = this.expandedPingTiles.has(device);
        if (isExpanded) {
            tile.classList.add('expanded');
        }
        tile.setAttribute('aria-expanded', String(isExpanded));

        const statusText = this.formatPingStatus(status);
        const successRate = `${status.success_rate.toFixed(1)}%`;
        const tooltipText = this.formatPingTooltip(status, statusText);
        tile.title = tooltipText;

        const summary = document.createElement('div');
        summary.className = 'ping-summary';

        const indicator = document.createElement('span');
        indicator.className = 'ping-indicator';
        indicator.setAttribute('aria-hidden', 'true');
        summary.appendChild(indicator);

        const name = document.createElement('h3');
        name.textContent = device;
        summary.appendChild(name);

        const compactStats = document.createElement('div');
        compactStats.className = 'ping-compact-stats';

        const state = document.createElement('span');
        state.className = 'ping-state';
        state.textContent = statusText;
        compactStats.appendChild(state);

        const rate = document.createElement('span');
        rate.className = 'ping-rate';
        rate.textContent = successRate;
        compactStats.appendChild(rate);

        const compactDetail = this.formatCompactPingDetail(status);
        if (compactDetail) {
            const detail = document.createElement('span');
            detail.className = 'ping-compact-detail';
            detail.textContent = compactDetail;
            compactStats.appendChild(detail);
        }
        summary.appendChild(compactStats);

        const expandButton = document.createElement('button');
        expandButton.type = 'button';
        expandButton.className = 'ping-expand-toggle';
        expandButton.textContent = isExpanded ? 'Collapse' : 'Expand';
        expandButton.setAttribute('aria-expanded', String(isExpanded));
        expandButton.setAttribute('aria-label', `${isExpanded ? 'Collapse' : 'Expand'} ping details for ${device}`);
        expandButton.addEventListener('click', event => {
            event.stopPropagation();
            if (this.expandedPingTiles.has(device)) {
                this.expandedPingTiles.delete(device);
            } else {
                this.expandedPingTiles.add(device);
            }
            this.updatePingStatus();
        });
        summary.appendChild(expandButton);
        tile.appendChild(summary);

        const details = document.createElement('div');
        details.className = 'ping-details';

        const stats = document.createElement('div');
        stats.className = 'stats';
        stats.innerHTML = `
            <div><strong>Status:</strong> ${this.escapeHtml(statusText)}</div>
            <div><strong>Success Rate:</strong> ${successRate}</div>
            <div><strong>Samples:</strong> ${status.successful_samples}/${status.total_samples}</div>
            ${status.avg_rtt_ms !== null && status.avg_rtt_ms !== undefined ? `<div><strong>Avg RTT:</strong> ${status.avg_rtt_ms.toFixed(2)}ms</div>` : ''}
            ${status.last_check_ts ? `<div><strong>Last Check:</strong> ${this.formatTimestampJST(status.last_check_ts)}</div>` : ''}
            ${status.last_error_message ? `<div><strong>Last Error:</strong> ${this.escapeHtml(status.last_error_message)}</div>` : ''}
        `;
        details.appendChild(stats);

        // Timeline tiles (oldest -> newest)
        const timelineWrapper = document.createElement('div');
        timelineWrapper.className = 'ping-timeline';

        (status.timeline || []).forEach(result => {
            const cell = document.createElement('div');
            cell.className = 'ping-cell';
            if (result === true) {
                cell.classList.add('ok');
            } else if (result === false) {
                cell.classList.add('fail');
            } else {
                cell.classList.add('unknown');
            }
            timelineWrapper.appendChild(cell);
        });

        details.appendChild(timelineWrapper);

        // Add ping export buttons
        const pingExportControls = document.createElement('div');
        pingExportControls.className = 'ping-export-controls';

        const exportCsvBtn = document.createElement('button');
        exportCsvBtn.className = 'export-btn-small';
        exportCsvBtn.textContent = '📊 Export CSV';
        exportCsvBtn.addEventListener('click', event => {
            event.stopPropagation();
            this.exportPing(device, 'csv');
        });

        const exportJsonBtn = document.createElement('button');
        exportJsonBtn.className = 'export-btn-small';
        exportJsonBtn.textContent = '📋 Export JSON';
        exportJsonBtn.addEventListener('click', event => {
            event.stopPropagation();
            this.exportPing(device, 'json');
        });

        pingExportControls.appendChild(exportCsvBtn);
        pingExportControls.appendChild(exportJsonBtn);
        details.appendChild(pingExportControls);
        tile.appendChild(details);

        return tile;
    }

    formatPingTooltip(status, statusText) {
        const lines = [
            `Status: ${statusText}`,
            `Success Rate: ${status.success_rate.toFixed(1)}%`,
            `Samples: ${status.successful_samples}/${status.total_samples}`
        ];
        if (status.avg_rtt_ms !== null && status.avg_rtt_ms !== undefined) {
            lines.push(`Avg RTT: ${status.avg_rtt_ms.toFixed(2)}ms`);
        }
        if (status.last_check_ts) {
            lines.push(`Last Check: ${this.formatTimestampJST(status.last_check_ts)}`);
        }
        if (status.last_error_message) {
            lines.push(`Last Error: ${status.last_error_message}`);
        }
        return lines.join('\n');
    }

    formatCompactPingDetail(status) {
        if (status.status === 'down' && status.last_error_message) {
            const message = status.last_error_message;
            return message.length > 40 ? `${message.slice(0, 37)}...` : message;
        }
        if (status.avg_rtt_ms !== null && status.avg_rtt_ms !== undefined) {
            return `${status.avg_rtt_ms.toFixed(1)}ms`;
        }
        if (status.total_samples > 0) {
            return `${status.successful_samples}/${status.total_samples}`;
        }
        return '';
    }

    formatPingStatus(status) {
        if (status.status === 'down') {
            return status.last_error_message || 'Not Responding';
        }
        if (status.status === 'unknown') {
            return 'No Data';
        }
        return status.status.charAt(0).toUpperCase() + status.status.slice(1);
    }

    formatRunError(run) {
        return run.error_message || 'Disconnected';
    }

    exportPing(device, format) {
        try {
            const url = `/api/export/ping?device=${encodeURIComponent(device)}&format=${format}&window_seconds=3600`;
            window.location.href = url;
        } catch (error) {
            console.error('Error exporting ping data:', error);
            alert('Failed to export ping data');
        }
    }

    formatTimestampJST(epoch) {
        // Convert UTC epoch to JST
        const date = new Date(epoch * 1000);

        // JST is UTC+9
        const jstOffset = 9 * 60; // minutes
        const jstDate = new Date(date.getTime() + jstOffset * 60 * 1000);

        const year = jstDate.getUTCFullYear();
        const month = String(jstDate.getUTCMonth() + 1).padStart(2, '0');
        const day = String(jstDate.getUTCDate()).padStart(2, '0');
        const hours = String(jstDate.getUTCHours()).padStart(2, '0');
        const minutes = String(jstDate.getUTCMinutes()).padStart(2, '0');
        const seconds = String(jstDate.getUTCSeconds()).padStart(2, '0');

        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds} JST`;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new NetworkWatch();
});
