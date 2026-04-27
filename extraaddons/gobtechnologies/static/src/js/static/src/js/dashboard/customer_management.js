/** @odoo-module **/
import {registry} from '@web/core/registry';
import {Component, useState} from '@odoo/owl';

export class CustomerManagement extends Component {
    setup() {
        this.state = useState({
            // Add your state properties here
        });
    }
    
}

CustomerManagement.template = "gobtechnologies.customer_management";
registry.category('actions').add('gobtechnologies.customer_management', CustomerManagement);