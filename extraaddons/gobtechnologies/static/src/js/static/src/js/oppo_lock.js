/** @odoo-module **/
import {registry} from "@web/core/registry";
import {Component, useState, onWillStart} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";


export class OppoLock extends Component{
    setup(){
        this.orm = useService('orm');
        this.action = useService('action');
        this.notification = useService('notification');
        this.rpc = useService('rpc');

        this.state = useState({
            devices: [],
            filteredDevices: [],
            lockedCount: 0,
            unlockedCount: 0,
            pendingCount: 0,
            errorCount: 0,
            searchQuery: "",
            confirmDeleteId: null,
        });

        onWillStart(async() => {
            await this.fetchDevices();
        })
    }

    async fetchDevices() {
        const devices = await this.orm.searchRead("oppo.lock", [], [
            "device_name", "customer_name", "repayment_id", "device_uid", "status", "lock_date", "x_sign", "api_response"
        ]);
        this.state.devices = devices;
        await this.fetchDeviceStatuses();
        this.filterDevices();
        this.updateCounts();
    }

    async fetchDeviceStatuses() {
        // Status code to description mapping
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
        // Fetch status from Oppo API for each device
        for (const device of this.state.devices) {
            try {
                const result = await this.orm.call("oppo.lock", "action_get_device_status", [[device.id]]);
                // Update the device status in the state
                const deviceIndex = this.state.devices.findIndex(d => d.id === device.id);
                if (deviceIndex !== -1) {
                    this.state.devices[deviceIndex].status = statusMap[result.status] || result.status;
                    this.state.devices[deviceIndex].api_status = result.api_status;
                    this.state.devices[deviceIndex].info = result.info;
                }
            } catch (error) {
                console.error(`Failed to fetch status for device ${device.id}:`, error);
                // Keep existing status if API call fails
            }
        }

        // Update counts after fetching all statuses
        this.updateCounts();
    }

    // Update device counts based on status
    updateCounts() {
        // Count based on new status descriptions
        this.state.lockedCount = this.state.devices.filter(d => d.status === 'Locked').length;
        this.state.unlockedCount = this.state.devices.filter(d => 
            ['Normal', 'Completed', 'Released PhoneLOCK', 'Released SIMLOCK', 'Deleted', 'CK Unlock'].includes(d.status)
        ).length;
        this.state.pendingCount = this.state.devices.filter(d => 
            ['Locking', 'Completing', 'Unlocking', 'Activating', 'Releasing PhoneLOCK', 'Releasing SIMLOCK', 'Deleting'].includes(d.status)
        ).length;
        this.state.errorCount = this.state.devices.filter(d => d.status === 'Error').length;
    }

    filterDevices() {
        if (!this.state.searchQuery) {
            this.state.filteredDevices = this.state.devices;
        } else {
            const query = this.state.searchQuery.toLowerCase();
            this.state.filteredDevices = this.state.devices.filter(d =>
                (d.device_name && d.device_name.toLowerCase().includes(query)) ||
                (d.customer_name && d.customer_name.toLowerCase().includes(query)) ||
                (d.device_uid && d.device_uid.toLowerCase().includes(query)) ||
                (d.repayment_id && d.repayment_id[1].toLowerCase().includes(query))
            );
        }
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
        this.filterDevices();
    }

    async lockDevice(device) {
        try {
            await this.orm.call("oppo.lock", "action_lock_device", [[device.id]]);
            this.notification.add(`Device locked successfully`, { type: 'success' });
            await this.fetchDevices();
        } catch (error) {
            this.notification.add(`Failed to lock device`, { type: 'danger' });
            this.notification.add(`Error: ${error.message}`, { type: 'danger' });
        }
    }

    async unlockDevice(device) {
        try {
            await this.orm.call("oppo.lock", "action_unlock_device", [[device.id]]);
            this.notification.add(`Device unlocked successfully`, { type: 'success' });
            await this.fetchDevices();
        } catch (error) {
            this.notification.add(`Failed to unlock device`, { type: 'danger' });
            this.notification.add(`Error: ${error.message}`, { type: 'danger' });
        }
    }

    async refreshDeviceStatus(device) {
        // Status code to description mapping
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
            this.filterDevices();
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
}

OppoLock.template = "gobtechnologies.oppo_lock";

registry.category('actions').add('gobtechnologies.oppo_lock', OppoLock);
