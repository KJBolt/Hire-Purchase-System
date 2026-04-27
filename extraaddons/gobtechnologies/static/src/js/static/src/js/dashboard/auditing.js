/** @odoo-module **/
import {registry} from '@web/core/registry';
import {Component, useState} from '@odoo/owl';

export class Auditing extends Component {
    setup() {
        this.state = useState({
            activeTab: 'activity',
        });

        this.state.setActiveTab = (tab) => {
            this.state.activeTab = tab;
        };
    }
    
}

Auditing.template = "gobtechnologies.auditing";
registry.category('actions').add('gobtechnologies.auditing', Auditing);