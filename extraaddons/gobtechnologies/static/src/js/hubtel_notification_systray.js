/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class HubtelNotificationSystray extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.busService = this.env.services.bus_service;
        this.state = useState({ count: 0 });

        // Create a string channel using the user's ID
        this.channel = `hubtel_notification_${this.env.services.user.partnerId}`;
        
        // Subscribe to the channel
        this.busService.addChannel(this.channel);

        // Use the standard addEventListener method with the correct event name
        this.busService.addEventListener('notification', this._onBusNotification.bind(this));


        // Initial fetch
        onWillStart(async () => {
            // await this._initialFetchNotificationCount();
        });
    }

    _onBusNotification(event) {
        const notifications = event.detail;
        for (const { type, payload } of notifications) {
            if (type === 'count_notification') {
                this.state.count = payload.count;
            }

            if (type === 'notify_user'){
                this.notification.add(payload.msg, { type: "success", sticky: false });
            }

            if (type === 'invoice'){
                this.notification.add(payload.msg, { type: "success", sticky: false });
            }

            if (type === 'sms_error'){
                this.notification.add(payload.msg, { type: "danger", sticky: false });
            }
        }
    }

    // async _initialFetchNotificationCount() {
    //     try {
    //         const count = await this.orm.call("payment.notifications", "search_count", [[["is_read", "=", false]]]);
    //         this.state.count = count;
    //     } catch (error) {
    //         console.error("Error fetching notification count:", error);
    //         this.notification.add(
    //             "Failed to fetch notifications",
    //             {
    //                 type: "danger",
    //             }
    //         );
    //     }
    // }

    // When the bell icon is clicked clear notifications
    // async clearNotifications() {
    //     try {
    //         await this.orm.call("hubtel.webhook", "mark_as_read", [[]], {});
    //         this.state.count = 0;
    //         if (this.action) {
    //             this.action.doAction({
    //                 type: "ir.actions.act_window",
    //                 name: "Notifications from Hubtel",
    //                 res_model: "hubtel.webhook",
    //                 view_mode: "tree,form",
    //                 views: [[false, "list"], [false, "form"]],  // Ensure views are defined
    //                 target: "current",
    //                 context: {}, 
    //             });
    //         } else {
    //             console.error("Action service is not available.");
    //         }
    //     } catch (error) {
    //         console.error("Error clearing notifications:", error);
    //         this.notification.add(
    //             "Failed to clear notifications",
    //             {
    //                 type: "danger",
    //             }
    //         );
    //     }
    // }
}

HubtelNotificationSystray.template = "gobtechnologies.HubtelNotificationSystray";

export const systrayItem = {
    Component: HubtelNotificationSystray,
    isDisplayed: (env) => true,
};

registry.category("systray").add("hubtel_notification", systrayItem, { sequence: 100 });
