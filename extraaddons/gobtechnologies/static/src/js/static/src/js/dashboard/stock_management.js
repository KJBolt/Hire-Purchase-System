/** @odoo-module **/
import {registry} from '@web/core/registry';
import {Component, useState} from '@odoo/owl';

export class StockManagement extends Component {
    setup() {
        this.state = useState({
            activeTab: 'stockList',
        });
        this.state.setActiveTab = (tab) => {
            this.state.activeTab = tab;
        };
    }

}

StockManagement.template = "gobtechnologies.stock_management";
registry.category('actions').add('gobtechnologies.stock_management', StockManagement);