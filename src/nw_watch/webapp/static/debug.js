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

class DebugPage {
    constructor() {
        this.maxLines = 600;
        this.streams = [];
        this.bindControls();
        this.startLogStream('app', 'appLogStream', 'appStreamStatus');
        this.loadConfig();
    }

    bindControls() {
        document.getElementById('clearDebugLogs').addEventListener('click', () => {
            document.querySelectorAll('.ssh-device-log-stream').forEach(output => {
                output.textContent = '';
            });
            document.getElementById('appLogStream').textContent = '';
        });
        document.getElementById('refreshDebugConfig').addEventListener('click', () => {
            this.loadConfig();
        });
    }

    startLogStream(name, outputId, statusId, params = {}) {
        const output = document.getElementById(outputId);
        const status = document.getElementById(statusId);
        const query = new URLSearchParams(params).toString();
        const source = new EventSource(
            `/api/debug/logs/${name}${query ? `?${query}` : ''}`
        );
        this.streams.push(source);

        source.addEventListener('status', event => {
            status.textContent = event.data;
            status.className = 'debug-stream-status connected';
        });

        source.addEventListener('log', event => {
            const line = JSON.parse(event.data);
            this.appendLine(output, line);
        });

        source.onerror = () => {
            status.textContent = 'Reconnecting';
            status.className = 'debug-stream-status reconnecting';
        };
    }

    appendLine(output, line) {
        const lines = output.textContent ? output.textContent.split('\n') : [];
        if (lines.length === 1 && lines[0].startsWith('Waiting for')) {
            lines.length = 0;
        }
        lines.push(line);
        while (lines.length > this.maxLines) {
            lines.shift();
        }
        output.textContent = lines.join('\n');
        output.scrollTop = output.scrollHeight;
    }

    async loadConfig() {
        const output = document.getElementById('debugConfig');
        try {
            const response = await fetch('/api/debug/config');
            const data = await response.json();
            const config = data.config || data;
            output.textContent = JSON.stringify(config, null, 2);
            this.renderSshDevicePanels(config.devices || []);
        } catch (error) {
            output.textContent = `Failed to load configuration: ${error}`;
        }
    }

    renderSshDevicePanels(devices) {
        const container = document.getElementById('sshDevicePanels');
        const existingDeviceNames = new Set(
            [...container.querySelectorAll('.debug-panel')].map(
                panel => panel.dataset.deviceName
            )
        );
        const nextDeviceNames = new Set(devices.map(device => device.name));

        if (
            existingDeviceNames.size === nextDeviceNames.size &&
            [...nextDeviceNames].every(name => existingDeviceNames.has(name))
        ) {
            return;
        }

        this.streams = this.streams.filter(source => {
            if (source.datasetType === 'ssh') {
                source.close();
                return false;
            }
            return true;
        });
        container.innerHTML = '';

        if (devices.length === 0) {
            container.innerHTML = '<p class="loading">No devices configured</p>';
            return;
        }

        devices.forEach(device => {
            const ids = this.deviceElementIds(device.name);
            const panel = document.createElement('div');
            panel.className = 'debug-panel';
            panel.dataset.deviceName = device.name;
            panel.innerHTML = `
                <div class="debug-panel-header">
                    <h2>SSH Session Console - ${this.escapeHtml(device.name)}</h2>
                    <span id="${ids.statusId}" class="debug-stream-status">Connecting</span>
                </div>
                <pre id="${ids.outputId}" class="debug-log-stream ssh-device-log-stream">Waiting for ${this.escapeHtml(device.name)} SSH session logs...</pre>
            `;
            container.appendChild(panel);
            this.startLogStream('ssh', ids.outputId, ids.statusId, { device: device.name });
            this.streams[this.streams.length - 1].datasetType = 'ssh';
        });
    }

    deviceElementIds(deviceName) {
        const suffix = deviceName.replace(/[^a-zA-Z0-9_-]/g, '_');
        return {
            outputId: `sshLogStream_${suffix}`,
            statusId: `sshStreamStatus_${suffix}`
        };
    }

    escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = value;
        return div.innerHTML;
    }
}

window.addEventListener('beforeunload', () => {
    if (window.debugPage) {
        window.debugPage.streams.forEach(source => source.close());
    }
});

document.addEventListener('DOMContentLoaded', () => {
    window.debugPage = new DebugPage();
});
