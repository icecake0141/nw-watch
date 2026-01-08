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
            ping_window_seconds: 60
        };
        this.runPollTimer = null;
        this.pingPollTimer = null;
        this.pauseBanner = null;
        
        this.init();
    }
    
    async init() {
        // Load configuration
        await this.loadConfig();
        
        // Load initial data
        await this.loadDevices();
        await this.loadCommands();
        
        // Setup UI
        this.setupEventListeners();
        this.renderCommandTabs();
        
        // Start polling
        this.startPolling();
        
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
    
    setupEventListeners() {
        document.getElementById('toggleAutoRefresh').addEventListener('click', () => {
            this.toggleAutoRefresh();
        });
        
        document.getElementById('manualRefresh').addEventListener('click', () => {
            this.manualRefresh();
        });
    }
    
    toggleAutoRefresh() {
        this.autoRefresh = !this.autoRefresh;
        const btn = document.getElementById('toggleAutoRefresh');
        
        if (this.autoRefresh) {
            btn.textContent = '⏸ Pause Auto-Refresh';
            this.startPolling();
            this.showPauseBanner(false);
        } else {
            btn.textContent = '▶ Resume Auto-Refresh';
            this.stopPolling();
            this.showPauseBanner(true);
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
            const response = await fetch(`/api/runs/${encodeURIComponent(command)}`);
            const data = await response.json();
            
            this.renderCommandContent(command, data.runs);
        } catch (error) {
            console.error('Error loading command data:', error);
        }
    }
    
    renderCommandContent(command, runsData) {
        const contentContainer = document.getElementById('commandContent');
        contentContainer.innerHTML = '';
        
        // Render each device's runs
        for (const [device, runs] of Object.entries(runsData)) {
            const deviceSection = document.createElement('div');
            deviceSection.className = 'device-section';
            
            const deviceHeader = document.createElement('h3');
            deviceHeader.textContent = `Device: ${device}`;
            deviceSection.appendChild(deviceHeader);
            
            // Render run history
            const historyDiv = document.createElement('div');
            historyDiv.className = 'run-history';
            
            if (runs.length === 0) {
                historyDiv.innerHTML = '<p class="loading">No data available</p>';
            } else {
                runs.forEach((run, index) => {
                    const runEntry = this.createRunEntry(run, index);
                    historyDiv.appendChild(runEntry);
                });
            }
            
            deviceSection.appendChild(historyDiv);
            
            // Add diff section for this device
            const diffSection = this.createDiffSection(command, device);
            deviceSection.appendChild(diffSection);
            
            contentContainer.appendChild(deviceSection);
        }
    }
    
    createRunEntry(run, index) {
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
        
        return entry;
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
            
            const diffOutput = document.getElementById(`diff-${deviceA}`);
            this.renderDiff(
                diffOutput,
                data.diff,
                data.has_diff ? 'No differences found' : 'Data not available for both devices',
                data.diff_format === 'html'
            );
        } catch (error) {
            console.error('Error loading device diff:', error);
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
                    const value = (attr.value || '').trim().toLowerCase();
                    if (name.startsWith('on')) {
                        node.removeAttribute(attr.name);
                    }
                    if ((name === 'href' || name === 'src') && value.startsWith('javascript:')) {
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
            container.appendChild(tile);
        }
        
        if (Object.keys(pingStatus).length === 0) {
            container.innerHTML = '<p class="loading">No ping data available</p>';
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
