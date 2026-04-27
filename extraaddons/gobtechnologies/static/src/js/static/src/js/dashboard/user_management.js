/** @odoo-module **/
import {registry} from '@web/core/registry';
import {Component, useState} from '@odoo/owl';

export class UserManagement extends Component {
    setup() {
        this.state = useState({
            // Add your state properties here
        });
    }
    
}

UserManagement.template = "gobtechnologies.user_management";
registry.category('actions').add('gobtechnologies.user_management', UserManagement);