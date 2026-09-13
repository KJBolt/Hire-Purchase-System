/** @odoo-module **/
import {registry} from "@web/core/registry";
import {Component, useState, onWillStart, useMemo, onMounted, onWillUnmount} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";


export class OppoLock extends Component{
    setup(){
        this.orm = useService('orm');
        this.action = useService('action');
        this.notification = useService('notification');
        this.rpc = useService('rpc');

        // Status cache: keyed by device.id, stores { status, api_status, info }
        this.statusCache = {};
        
        // Countdown timer reference
        this.countdownInterval = null;

        this.state = useState({
            devices: [],
            filteredDevices: [],
            lockedCount: 0,
            unlockedCount: 0,
            completedCount: 0,
            errorCount: 0,
            searchQuery: "",
            confirmDeleteId: null,
            currentPage: 1,
            pageSize: 5,
            loadingStatuses: false,
            completingIds: [],
            countdownTick: 0, // Triggers re-render every second
            decreaseDaysModal: false,
            selectedDevice: null,
            decreaseHours: 0,
            decreaseMinutes: 0,
            decreaseSeconds: 0,
            decreasingDays: false,
        });

        onWillStart(async() => {
            await this.fetchDevices();
        })

        onMounted(() => {
            // Start countdown timer
            this.startCountdownTimer();
        })

        onWillUnmount(() => {
            this.stopCountdownTimer();
        })
    }

    get totalPages() {
        return Math.max(1, Math.ceil(this.state.filteredDevices.length / this.state.pageSize));
    }

    get paginatedDevices() {
        const start = (this.state.currentPage - 1) * this.state.pageSize;
        return this.state.filteredDevices.slice(start, start + this.state.pageSize);
    }

    get pageNumbers() {
        const total = this.totalPages;
        const current = this.state.currentPage;
        const pages = [];
        const maxVisible = 5;
        let start = Math.max(1, current - Math.floor(maxVisible / 2));
        let end = Math.min(total, start + maxVisible - 1);
        if (end - start < maxVisible - 1) {
            start = Math.max(1, end - maxVisible + 1);
        }
        for (let i = start; i <= end; i++) {
            pages.push(i);
        }
        return pages;
    }

    goToPage(page) {
        if (page >= 1 && page <= this.totalPages) {
            this.state.currentPage = page;
            this.fetchStatusesForCurrentPage();
        }
    }

    nextPage() {
        if (this.state.currentPage < this.totalPages) {
            this.state.currentPage++;
            this.fetchStatusesForCurrentPage();
        }
    }

    prevPage() {
        if (this.state.currentPage > 1) {
            this.state.currentPage--;
            this.fetchStatusesForCurrentPage();
        }
    }

    async fetchDevices() {
        const devices = await this.orm.searchRead("oppo.lock", [], [
            "device_name", "customer_name", "repayment_id", "device_uid", "status", "lock_date", "x_sign", "api_response", "repayment_state", "phone_no", "expired_time"
        ]);
        this.state.devices = devices;
        this.state.currentPage = 1;
        this.filterDevices();
        // Non-blocking status fetch for current page
        this.fetchStatusesForCurrentPage();
    }

    async fetchStatusesForCurrentPage() {
        await this.fetchDeviceStatuses(this.paginatedDevices);
    }

    async fetchDeviceStatuses(devicesToFetch) {
        if (!devicesToFetch || devicesToFetch.length === 0) {
            return;
        }

        const statusMap = {
            '-1': 'Error',
            '0': 'Normal',
            '1': 'Locked',
            '2': 'Locking',
            '3': 'Completed',
            '4': 'Completing',
            '5': 'Unlocking',
            '7': 'Activating',
            '8': 'Releasing PhoneLOCK',
            '9': 'Released PhoneLOCK',
            '10': 'Releasing SIMLOCK',
            '11': 'Released SIMLOCK',
            '12': 'Deleting',
            '13': 'Deleted',
            '14': 'CK Unlock',
        };

        // Filter out devices that are already in cache
        const devicesNeedingFetch = devicesToFetch.filter(device => {
            return !this.statusCache[device.id];
        });

        if (devicesNeedingFetch.length === 0) {
            // All devices are cached — apply cache data to state
            devicesToFetch.forEach(device => {
                const cached = this.statusCache[device.id];
                if (cached) {
                    const deviceIndex = this.state.devices.findIndex(d => d.id === device.id);
                    if (deviceIndex !== -1) {
                        this.state.devices[deviceIndex].status = cached.status;
                        this.state.devices[deviceIndex].api_status = cached.api_status;
                        this.state.devices[deviceIndex].info = cached.info;
                    }
                    const filteredIndex = this.state.filteredDevices.findIndex(d => d.id === device.id);
                    if (filteredIndex !== -1) {
                        this.state.filteredDevices[filteredIndex].status = cached.status;
                        this.state.filteredDevices[filteredIndex].api_status = cached.api_status;
                        this.state.filteredDevices[filteredIndex].info = cached.info;
                    }
                }
            });
            this.updateCounts();
            return;
        }

        this.state.loadingStatuses = true;

        const fetchPromises = devicesNeedingFetch.map(async (device) => {
            try {
                const result = await this.orm.call("oppo.lock", "action_get_device_status", [[device.id]]);
                const status = statusMap[result.status] || result.status;

                // Store in cache
                this.statusCache[device.id] = {
                    status: status,
                    api_status: result.api_status,
                    info: result.info,
                };

                // Update device in state.devices
                const deviceIndex = this.state.devices.findIndex(d => d.id === device.id);
                if (deviceIndex !== -1) {
                    this.state.devices[deviceIndex].status = status;
                    this.state.devices[deviceIndex].api_status = result.api_status;
                    this.state.devices[deviceIndex].info = result.info;
                }

                // Update device in state.filteredDevices
                const filteredIndex = this.state.filteredDevices.findIndex(d => d.id === device.id);
                if (filteredIndex !== -1) {
                    this.state.filteredDevices[filteredIndex].status = status;
                    this.state.filteredDevices[filteredIndex].api_status = result.api_status;
                    this.state.filteredDevices[filteredIndex].info = result.info;
                }
            } catch (error) {
                console.error(`Failed to fetch status for device ${device.id}:`, error);
            }
        });

        await Promise.all(fetchPromises);
        this.state.loadingStatuses = false;
        this.updateCounts();
    }

    updateCounts() {
        this.state.lockedCount = this.state.devices.filter(d => d.status === 'Locked').length;
        this.state.unlockedCount = this.state.devices.filter(d =>
            ['Normal', 'Released PhoneLOCK', 'Released SIMLOCK', 'Deleted', 'CK Unlock'].includes(d.status)
        ).length;
        this.state.completedCount = this.state.devices.filter(d => d.status === 'Completed').length;
        this.state.errorCount = this.state.devices.filter(d => d.status === 'Error').length;
    }

    filterDevices() {
        if (!this.state.searchQuery) {
            this.state.filteredDevices = [...this.state.devices];
        } else {
            const query = this.state.searchQuery.toLowerCase();
            this.state.filteredDevices = this.state.devices.filter(d =>
                (d.device_name && d.device_name.toLowerCase().includes(query)) ||
                (d.customer_name && d.customer_name.toLowerCase().includes(query)) ||
                (d.device_uid && d.device_uid.toLowerCase().includes(query)) ||
                (d.repayment_id && d.repayment_id[1].toLowerCase().includes(query)) ||
                (d.phone_no && d.phone_no.toLowerCase().includes(query))
            );
        }
        this.state.currentPage = 1;
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
        this.filterDevices();
        this.fetchStatusesForCurrentPage();
    }


    async refreshDeviceStatus(device) {
        const statusMap = {
            '-1': 'Error',
            '0': 'Normal',
            '1': 'Locked',
            '2': 'Locking',
            '3': 'Completed',
            '4': 'Completing',
            '5': 'Unlocking',
            '7': 'Activating',
            '8': 'Releasing PhoneLOCK',
            '9': 'Released PhoneLOCK',
            '10': 'Releasing SIMLOCK',
            '11': 'Released SIMLOCK',
            '12': 'Deleting',
            '13': 'Deleted',
            '14': 'CK Unlock',
        };

        try {
            const result = await this.orm.call("oppo.lock", "action_get_device_status", [[device.id]]);
            const deviceIndex = this.state.devices.findIndex(d => d.id === device.id);
            if (deviceIndex !== -1) {
                this.state.devices[deviceIndex].status = statusMap[result.status] || result.status;
                this.state.devices[deviceIndex].api_status = result.api_status;
                this.state.devices[deviceIndex].info = result.info;
            }
            const filteredIndex = this.state.filteredDevices.findIndex(d => d.id === device.id);
            if (filteredIndex !== -1) {
                this.state.filteredDevices[filteredIndex].status = statusMap[result.status] || result.status;
                this.state.filteredDevices[filteredIndex].api_status = result.api_status;
                this.state.filteredDevices[filteredIndex].info = result.info;
            }
            this.updateCounts();
            this.notification.add(`Device status refreshed`, { type: 'success' });
        } catch (error) {
            this.notification.add(`Failed to refresh device status`, { type: 'danger' });
            this.notification.add(`Error: ${error.message}`, { type: 'danger' });
        }
    }

    editDevice(deviceId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'oppo.lock',
            res_id: deviceId,
            views: [[false, 'form']],
            target: 'current',
            flags: { mode: 'edit' },
        });
    }

    async lockDevice(deviceId) {
        try {
            const result = await this.orm.call("oppo.lock", "action_edit_prepaid", [[deviceId], 0, 0]);
            if (result && result.success) {
                // Update status to Locked
                const deviceIndex = this.state.devices.findIndex(d => d.id === deviceId);
                if (deviceIndex !== -1) {
                    this.state.devices[deviceIndex].status = 'Locked';
                }
                const filteredIndex = this.state.filteredDevices.findIndex(d => d.id === deviceId);
                if (filteredIndex !== -1) {
                    this.state.filteredDevices[filteredIndex].status = 'Locked';
                }
                this.statusCache[deviceId] = {
                    status: 'Locked',
                    api_status: 1,
                    info: '',
                };
                this.updateCounts();
                this.notification.add('Device locked successfully', { type: 'success' });
            } else {
                this.notification.add(`Lock failed: ${result?.error || 'Unknown error'}`, { type: 'danger' });
            }
        } catch (error) {
            console.error(`Failed to lock device ${deviceId}:`, error);
            const msg = error.data?.message || error.message || 'Unknown error';
            this.notification.add(`Lock failed: ${msg}`, { type: 'danger' });
        }
    }

    async completeDevice(deviceId) {
        if (this.state.completingIds.includes(deviceId)) {
            return;
        }
        this.state.completingIds.push(deviceId);
        try {
            const result = await this.orm.call("oppo.lock", "action_complete_device", [[deviceId]]);

            if (result.success) {
                // Update device status in state.devices
                const deviceIndex = this.state.devices.findIndex(d => d.id === deviceId);
                if (deviceIndex !== -1) {
                    this.state.devices[deviceIndex].status = 'Completed';
                }

                // Update device status in state.filteredDevices
                const filteredIndex = this.state.filteredDevices.findIndex(d => d.id === deviceId);
                if (filteredIndex !== -1) {
                    this.state.filteredDevices[filteredIndex].status = 'Completed';
                }

                // Update cache
                this.statusCache[deviceId] = {
                    status: 'Completed',
                    api_status: 3,
                    info: result.info || '',
                };

                this.updateCounts();
                this.notification.add('Device completed successfully', { type: 'success' });
            } else {
                this.notification.add(`Complete failed: ${result.error || 'Unknown error'}`, { type: 'danger' });
            }
        } catch (error) {
            console.error(`Failed to complete device ${deviceId}:`, error);
            const msg = error.data?.message || error.message || 'Unknown error';
            this.notification.add(`Complete failed: ${msg}`, { type: 'danger' });
        } finally {
            this.state.completingIds = this.state.completingIds.filter(id => id !== deviceId);
        }
    }

    confirmDelete(deviceId) {
        this.state.confirmDeleteId = deviceId;
    }

    cancelDelete() {
        this.state.confirmDeleteId = null;
    }

    async deleteDevice(device) {
        try {
            await this.orm.unlink("oppo.lock", [device.id]);
            this.notification.add('Device deleted successfully', { type: 'success' });
            this.state.confirmDeleteId = null;
            await this.fetchDevices();
        } catch (error) {
            this.notification.add('Failed to delete device', { type: 'danger' });
            console.error(error);
        }
    }

    getCountdown(expiredTime) {
        if (!expiredTime) return { text: '—', isExpired: false, isUrgent: false, isWarning: false };
        
        const expiryTimestamp = parseInt(expiredTime);
        if (isNaN(expiryTimestamp)) return { text: '—', isExpired: false, isUrgent: false, isWarning: false };
        
        const deadline = new Date(expiryTimestamp);
        const diff = deadline.getTime() - Date.now();
        
        if (diff <= 0) {
            return { text: 'Expired', isExpired: true, isUrgent: false, isWarning: false };
        }
        
        const totalSeconds = Math.floor(diff / 1000);
        const d = Math.floor(totalSeconds / 86400);
        const h = Math.floor((totalSeconds % 86400) / 3600);
        const m = Math.floor((totalSeconds % 3600) / 60);
        const s = totalSeconds % 60;
        
        const text = `${String(d).padStart(2, '0')}d ${String(h).padStart(2, '0')}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
        
        // Add urgency classes like home.xml
        let isUrgent = false;
        let isWarning = false;
        
        if (d < 1) {
            isUrgent = true;
        } else if (d < 3) {
            isWarning = true;
        }
        
        return { text, isExpired: false, isUrgent, isWarning };
    }

    startCountdownTimer() {
        // Update countdown every second
        this.countdownInterval = setInterval(() => {
            this.state.countdownTick = this.state.countdownTick + 1;
        }, 1000);
    }

    stopCountdownTimer() {
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
            this.countdownInterval = null;
        }
    }

    openDecreaseDaysModal(device) {
        this.state.selectedDevice = device;
        this.state.decreaseHours = 0;
        this.state.decreaseMinutes = 0;
        this.state.decreaseSeconds = 0;
        this.state.decreaseDaysModal = true;
    }

    closeDecreaseDaysModal() {
        this.state.decreaseDaysModal = false;
        this.state.selectedDevice = null;
        this.state.decreaseHours = 0;
        this.state.decreaseMinutes = 0;
        this.state.decreaseSeconds = 0;
    }

    getDecreaseDurationText() {
        const parts = [];
        const h = parseInt(this.state.decreaseHours) || 0;
        const m = parseInt(this.state.decreaseMinutes) || 0;
        const s = parseInt(this.state.decreaseSeconds) || 0;
        if (h > 0) parts.push(`${h} hour${h !== 1 ? 's' : ''}`);
        if (m > 0) parts.push(`${m} min${m !== 1 ? 's' : ''}`);
        if (s > 0) parts.push(`${s} sec${s !== 1 ? 's' : ''}`);
        return parts.length > 0 ? parts.join(', ') : '0';
    }

    async confirmDecreaseDays() {
        const h = parseInt(this.state.decreaseHours) || 0;
        const m = parseInt(this.state.decreaseMinutes) || 0;
        const s = parseInt(this.state.decreaseSeconds) || 0;

        if (!this.state.selectedDevice) {
            this.notification.add('No device selected', { type: 'danger' });
            return;
        }
        if (h <= 0 && m <= 0 && s <= 0) {
            this.notification.add('Please enter a value greater than zero for at least one field', { type: 'danger' });
            return;
        }

        // Frontend validation: check if decrease would push expiry into the past
        const device = this.state.selectedDevice;
        if (device.expired_time) {
            const expiryMs = parseInt(device.expired_time);
            if (!isNaN(expiryMs)) {
                const totalMs = ((h * 3600) + (m * 60) + s) * 1000;
                const newExpiryMs = expiryMs - totalMs;
                if (newExpiryMs <= Date.now()) {
                    const remainingMs = expiryMs - Date.now();
                    const remH = Math.floor(remainingMs / (1000 * 60 * 60));
                    const remM = Math.floor((remainingMs % (1000 * 60 * 60)) / (1000 * 60));
                    this.notification.add(
                        `Cannot decrease by ${this.getDecreaseDurationText()}: only ${remH}h ${remM}m remaining. The expiry would fall in the past.`,
                        { type: 'danger' }
                    );
                    return;
                }
            }
        }

        this.state.decreasingDays = true;

        try {
            const result = await this.orm.call("oppo.lock", "action_decrease_days", [
                [this.state.selectedDevice.id],
                h, m, s
            ]);

            if (result.success) {
                this.notification.add(`Expiry time decreased by ${this.getDecreaseDurationText()}`, { type: 'success' });
                this.closeDecreaseDaysModal();
                await this.fetchDevices();
            } else {
                const errorMsg = result.error || 'Failed to decrease expiry time';
                this.notification.add(errorMsg, { type: 'danger' });
            }
        } catch (error) {
            // Extract the actual error message from the Odoo error
            let errorMessage = 'Failed to decrease expiry time';
            if (error.message) {
                errorMessage = error.message;
            } else if (error.data && error.data.message) {
                errorMessage = error.data.message;
            } else if (error.data && error.data.debug) {
                // Parse the debug message to get the actual error
                const debugLines = error.data.debug.split('\n');
                const errorLine = debugLines.find(line => line.includes('Error:') || line.includes('UserError'));
                if (errorLine) {
                    errorMessage = errorLine.split(':').slice(1).join(':').trim();
                }
            }
            this.notification.add(errorMessage, { type: 'danger' });
            console.error('Decrease days error:', error);
        } finally {
            this.state.decreasingDays = false;
        }
    }
}

OppoLock.template = "gobtechnologies.oppo_lock";

registry.category('actions').add('gobtechnologies.oppo_lock', OppoLock);
