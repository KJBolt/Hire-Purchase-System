/** @odoo-module **/
import {registry} from "@web/core/registry";
import {Component, useState, onWillStart} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";


export class NuovoPay extends Component{
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
            searchQuery: "",
            confirmUnregisterId: null,
        });

        onWillStart(async() => {
            await this.fetchDevices();
        })
    }

    async fetchDevices() {
        const devices = await this.orm.searchRead("nuovopay.lock", [], [
            "name", "repayment_id", "device_id", "status", "lock_date", "unlock_date"
        ]);
        this.state.devices = devices;
        this.filterDevices();
        this.updateCounts();
    }

    updateCounts() {
        this.state.lockedCount = this.state.devices.filter(d => d.status === 'locked').length;
        this.state.unlockedCount = this.state.devices.filter(d => d.status === 'unlocked').length;
    }

    filterDevices() {
        if (!this.state.searchQuery) {
            this.state.filteredDevices = this.state.devices;
        } else {
            const query = this.state.searchQuery.toLowerCase();
            this.state.filteredDevices = this.state.devices.filter(d =>
                d.name.toLowerCase().includes(query) ||
                (d.device_id && d.device_id.toLowerCase().includes(query)) ||
                (d.repayment_id && d.repayment_id[1].toLowerCase().includes(query))
            );
        }
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
        this.filterDevices();
    }

    async toggleLock(device, actionType) {
        const endpoint = actionType === 'lock' ? '/nuovopay/devices/lock' : '/nuovopay/devices/unlock';
        try {
            const result = await this.rpc(endpoint, { device_id: device.device_id });
            if (result && result.success) {
                this.notification.add(`Device ${actionType}ed successfully`, { type: 'success' });
                await this.fetchDevices();
            } else {
                const errMsg = result && result.error ? result.error : `Failed to ${actionType} device`;
                this.notification.add(`Error: ${errMsg}`, { type: 'danger' });
                this.notification.add(errMsg, { type: 'danger' });
            }
        } catch (error) {
            this.notification.add(`Failed to ${actionType} device`, { type: 'danger' });
            this.notification.add(`Error: ${error}`, { type: 'danger' });
        }
    }

    confirmUnregister(deviceId) {
        this.state.confirmUnregisterId = deviceId;
    }

    cancelUnregister() {
        this.state.confirmUnregisterId = null;
    }

    async unregisterDevice(device) {
        try {
            const result = await this.rpc('/nuovopay/devices/unregister', {
                device_id: device.device_id,
                odoo_record_id: device.id,
            });
            if (result && result.success) {
                this.notification.add('Device unregistered successfully', { type: 'success' });
                this.state.confirmUnregisterId = null;
                await this.fetchDevices();
            } else {
                const errMsg = result && result.error ? result.error : 'Failed to unregister device';
                this.notification.add(errMsg, { type: 'danger' });
            }
        } catch (error) {
            this.notification.add('Failed to unregister device', { type: 'danger' });
            console.error(error);
        }
    }

    openDevice(deviceId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'nuovopay.lock',
            res_id: deviceId,
            views: [[false, 'form']],
            target: 'current',
        });
    }
}

NuovoPay.template = "gobtechnologies.nuovo_pay";

registry.category('actions').add('gobtechnologies.nuovo_pay', NuovoPay);