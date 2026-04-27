/** @odoo-module **/
import {registry} from '@web/core/registry';
import {Component, useState} from '@odoo/owl';

export class StockManagement extends Component {
    setup() {
        this.state = useState({
            // Add your state properties here
        });
    }
    
}

StockManagement.template = "gobtechnologies.stock_management";
registry.category('actions').add('gobtechnologies.stock_management', StockManagement);