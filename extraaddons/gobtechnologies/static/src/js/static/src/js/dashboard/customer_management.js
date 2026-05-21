/** @odoo-module **/
import {registry} from '@web/core/registry';
import {Component, useState, onWillStart} from '@odoo/owl';
import {useService} from '@web/core/utils/hooks';

export class CustomerManagement extends Component {
    setup() {
        this.orm = useService('orm');
        this.state = useState({
            totalCustomers: 0,
            active: 0,
            completed: 0,
            overdue: 0,
            customers: [],
            searchQuery: '',
            filterStatus: 'all',
        });
        
        onWillStart(this.onWillStart.bind(this));
    }
    
    async onWillStart() {
        await this.fetchKPIData();
        await this.fetchCustomers();
    }
    
    async fetchKPIData() {
        // Fetch total customers
        const totalCustomers = await this.orm.searchCount('repayment', []);
        
        // Fetch active customers (draft and progress states)
        const active = await this.orm.searchCount('repayment', [
            ['state', '=', 'progress']
        ]);
        
        // Fetch completed customers (paid state)
        const completed = await this.orm.searchCount('repayment', [
            ['state', '=', 'paid']
        ]);
        
        // Fetch overdue customers (overdue_status field)
        const overdue = await this.orm.searchCount('repayment', [
            ['overdue_status', '=', true]
        ]);
        
        this.state.totalCustomers = totalCustomers;
        this.state.active = active;
        this.state.completed = completed;
        this.state.overdue = overdue;
    }
    
    async fetchCustomers() {
        const customers = await this.orm.searchRead('repayment', [], [
            'customer_name',
            'phone_no',
            'created_by',
            'product_lines',
            'selling_price',
            'total_paid',
            'percentage_paid',
            'state',
            'overdue_status',
            'unique_id',
        ]);
        
        // Fetch customer_name related fields (sales_agent, sales_manager, sales_administrator)
        for (let customer of customers) {
            if (customer.customer_name) {
                const partnerData = await this.orm.read('res.partner', [customer.customer_name[0]], [
                    'email',
                    'sales_agent',
                    'sales_manager',
                    'sales_administrator',
                ]);
                if (partnerData.length > 0) {
                    customer.customer_email = partnerData[0].email;
                    customer.sales_agent = customer.created_by ? customer.created_by[1] : '';
                    customer.sales_manager = partnerData[0].sales_manager;
                    customer.sales_administrator = partnerData[0].sales_administrator;
                }
            }
            
            // Fetch product names from product_lines
            if (customer.product_lines && customer.product_lines.length > 0) {
                const productData = await this.orm.read('repayment.item.line', customer.product_lines, [
                    'product_id',
                ]);
                customer.product_names = productData.map(line => line.product_id[1]).join(', ');
            }
        }
        
        this.state.customers = customers;
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value.toLowerCase();
    }

    onFilterChange(ev) {
        this.state.filterStatus = ev.target.value;
    }

    get filteredCustomers() {
        let customers = this.state.customers;

        // Filter by search query
        if (this.state.searchQuery) {
            customers = customers.filter(customer =>
                (customer.customer_name[1] && customer.customer_name[1].toLowerCase().includes(this.state.searchQuery)) ||
                (customer.phone_no && customer.phone_no.toLowerCase().includes(this.state.searchQuery)) ||
                (customer.customer_email && customer.customer_email.toLowerCase().includes(this.state.searchQuery))
            );
        }

        // Filter by status
        if (this.state.filterStatus !== 'all') {
            if (this.state.filterStatus === 'active') {
                customers = customers.filter(customer => customer.state === 'progress');
            } else if (this.state.filterStatus === 'completed') {
                customers = customers.filter(customer => customer.state === 'paid');
            } else if (this.state.filterStatus === 'overdue') {
                customers = customers.filter(customer => customer.overdue_status === true);
            }
        }

        return customers;
    }

}

CustomerManagement.template = "gobtechnologies.customer_management";
registry.category('actions').add('gobtechnologies.customer_management', CustomerManagement);