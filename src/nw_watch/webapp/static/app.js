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
        this.collectorPollTimer = null;
        this.collectorState = {
            commands_paused: false,
            shutdown_requested: false,
            status: 'unknown',
            updated_at: 0
        };
        this.collectorPollIntervalMs = 5000;
        
        // WebSocket reconnection settings
        this.maxWebSocketReconnectAttempts = 5;
        this.baseReconnectDelay = 1000;  // 1 second base delay
        this.maxReconnectDelay = 30000;  // 30 seconds max delay
        this.reconnectBackoffMultiplier = 2;  // Exponential backoff multiplier
        
        // Diff state preservation
        // Structure: { "command:device": { type: 'history'|'device', content: '...', format: 'html'|'text', otherDevice: '...' } }
        this.diffStates = {};
        
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
    
    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            const data = await response.json();
            this.config = data;
        } catch (error) {
            console.error('Error loading config:', error);
        }
    }
    
    async loadDevices() {
        try {
            const response = await fetch('/api/devices');
            const data = await response.json();
            this.devices = data.devices || [];
        } catch (error) {
            console.error('Error loading devices:', error);
        }
    }
    
    async loadCommands() {
        try {
            const response = await fetch('/api/commands');
            const data = await response.json();
            this.commands = data.commands || [];
        } catch (error) {
            console.error('Error loading commands:', error);
        }
    }

    async loadCollectorStatus() {
        try {
            const response = await fetch('/api/collector/status');
            const data = await response.json();
            this.collectorState = data;
            this.updateCollectorControls();
        } catch (error) {
            console.error('Error loading collector status:', error);
            this.updateCollectorControls(true);
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

        document.getElementById('stopCollector').addEventListener('click', () => {
            this.stopCollector();
        });
        
        // Load saved theme preference
        this.loadThemePreference();
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
        } catch (error) {
            console.error('Error stopping collector:', error);
            alert('Failed to stop collector');
        }
    }

    updateCollectorControls(hasError = false) {
        const statusElement = document.getElementById('collectorStatus');
        const toggleButton = document.getElementById('toggleCollectorCommands');
        const stopButton = document.getElementById('stopCollector');
        statusElement.classList.remove('status-unknown', 'status-paused', 'status-running', 'status-stopped');

        if (hasError) {
            statusElement.textContent = 'Collector: Unknown';
            statusElement.classList.add('status-unknown');
            return;
        }
        const status = this.collectorState.status || 'unknown';

        if (status === 'stopped' || this.collectorState.shutdown_requested) {
            statusElement.textContent = 'Collector: Stopped';
            statusElement.classList.add('status-stopped');
            toggleButton.disabled = true;
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

        toggleButton.disabled = false;
        stopButton.disabled = false;
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
    }
    
    async updateCommandData(command) {
        try {
            // Fetch side-by-side data for character-level diff
            const sideBySideResponse = await fetch(`/api/runs/${encodeURIComponent(command)}/side_by_side`);
            const sideBySideData = await sideBySideResponse.json();
            
            // Also fetch regular run data for history
            const response = await fetch(`/api/runs/${encodeURIComponent(command)}`);
            const data = await response.json();
            
            this.renderCommandContent(command, data.runs, sideBySideData);
        } catch (error) {
            console.error('Error loading command data:', error);
        }
    }
    
    renderCommandContent(command, runsData, sideBySideData) {
        const contentContainer = document.getElementById('commandContent');
        
        // Save current diff states before clearing
        this.saveDiffStates(command);
        
        contentContainer.innerHTML = '';
        
        // Check if we have side-by-side data
        if (sideBySideData && sideBySideData.devices && sideBySideData.devices.length >= 2) {
            // Render side-by-side comparison view
            this.renderSideBySideView(command, sideBySideData);
            
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
            deviceHeader.innerHTML = `<h3>Device: ${device}</h3>`;
            
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
    }
    
    renderSideBySideView(command, sideBySideData) {
        const contentContainer = document.getElementById('commandContent');
        
        // Create side-by-side section
        const sideBySideSection = document.createElement('div');
        sideBySideSection.className = 'side-by-side-section';
        
        // Title
        const title = document.createElement('h2');
        title.textContent = 'Side-by-Side Comparison (Character-level Diff)';
        title.style.marginBottom = '15px';
        sideBySideSection.appendChild(title);
        
        // Container for the two device outputs
        const comparisonContainer = document.createElement('div');
        comparisonContainer.className = 'comparison-container';
        
        // Render each device
        sideBySideData.devices.forEach(deviceData => {
            const devicePanel = document.createElement('div');
            devicePanel.className = 'device-panel';
            
            // Device header
            const header = document.createElement('div');
            header.className = 'device-panel-header';
            
            const deviceName = document.createElement('h3');
            deviceName.textContent = deviceData.name;
            header.appendChild(deviceName);
            
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
            
            if (deviceData.run.ok) {
                const outputPre = document.createElement('pre');
                outputPre.className = 'output-text-char-diff';
                outputPre.innerHTML = deviceData.run.output_html || this.escapeHtml(deviceData.run.output_text);
                outputContainer.appendChild(outputPre);
            } else {
                const errorMsg = document.createElement('div');
                errorMsg.className = 'error-message';
                errorMsg.textContent = `Error: ${deviceData.run.error_message || 'Unknown error'}`;
                outputContainer.appendChild(errorMsg);
            }
            
            devicePanel.appendChild(outputContainer);
            comparisonContainer.appendChild(devicePanel);
        });
        
        sideBySideSection.appendChild(comparisonContainer);
        contentContainer.appendChild(sideBySideSection);
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
            errorMsg.textContent = `Error: ${run.error_message || 'Unknown error'}`;
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
        historyBtn.textContent = 'Show Previous vs Latest';
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
        diffOutput.textContent = 'Click a button above to view diff';
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
                `/api/diff/history?command=${encodeURIComponent(command)}&device=${encodeURIComponent(device)}`
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
            console.error('Error loading history diff:', error);
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
            const isHtml = diffOutputs[0] && diffOutputs[0].classList.contains('diff-output-html');
            const content = diffOutputs[0] ? diffOutputs[0].innerHTML : '';
            
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
        } catch (error) {
            console.error('Error loading device diff:', error);
        }
    }
    
    exportDiff(command, device, format) {
        const exportControls = document.getElementById(`diff-export-${device}`);
        if (!exportControls) return;
        
        const diffType = exportControls.dataset.diffType;
        let url;
        
        if (diffType === 'history') {
            url = `/api/export/diff?command=${encodeURIComponent(command)}&device=${encodeURIComponent(device)}&format=${format}`;
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
            const hasContent = diffOutputElement.textContent !== 'Click a button above to view diff' &&
                               diffOutputElement.innerHTML.trim().length > 0;
            
            if (hasContent && exportControlsElement.style.display !== 'none') {
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
        const container = document.getElementById('pingTiles');
        container.innerHTML = '';
        
        for (const [device, status] of Object.entries(pingStatus)) {
            const tile = document.createElement('div');
            tile.className = `ping-tile ${status.status}`;
            
            const header = document.createElement('h3');
            header.textContent = device;
            tile.appendChild(header);
            
            const stats = document.createElement('div');
            stats.className = 'stats';
            
            const statusText = status.status.charAt(0).toUpperCase() + status.status.slice(1);
            stats.innerHTML = `
                <div><strong>Status:</strong> ${statusText}</div>
                <div><strong>Success Rate:</strong> ${status.success_rate.toFixed(1)}%</div>
                <div><strong>Samples:</strong> ${status.successful_samples}/${status.total_samples}</div>
                ${status.avg_rtt_ms ? `<div><strong>Avg RTT:</strong> ${status.avg_rtt_ms.toFixed(2)}ms</div>` : ''}
                ${status.last_check_ts ? `<div><strong>Last Check:</strong> ${this.formatTimestampJST(status.last_check_ts)}</div>` : ''}
            `;
            
            tile.appendChild(stats);

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

            tile.appendChild(timelineWrapper);
            
            // Add ping export buttons
            const pingExportControls = document.createElement('div');
            pingExportControls.className = 'ping-export-controls';
            
            const exportCsvBtn = document.createElement('button');
            exportCsvBtn.className = 'export-btn-small';
            exportCsvBtn.textContent = '📊 Export CSV';
            exportCsvBtn.addEventListener('click', () => this.exportPing(device, 'csv'));
            
            const exportJsonBtn = document.createElement('button');
            exportJsonBtn.className = 'export-btn-small';
            exportJsonBtn.textContent = '📋 Export JSON';
            exportJsonBtn.addEventListener('click', () => this.exportPing(device, 'json'));
            
            pingExportControls.appendChild(exportCsvBtn);
            pingExportControls.appendChild(exportJsonBtn);
            tile.appendChild(pingExportControls);
            
            container.appendChild(tile);
        }
        
        if (Object.keys(pingStatus).length === 0) {
            container.innerHTML = '<p class="loading">No ping data available</p>';
        }
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
