/** @odoo-module **/
import {registry} from '@web/core/registry';
import {Component, useState, onWillStart} from '@odoo/owl';
import {useService} from '@web/core/utils/hooks';

export class UserManagement extends Component {
    setup() {
        this.orm = useService('orm');
        this.action = useService('action');
        this.state = useState({
            totalUsers: 0,
            activeUsers: 0,
            salesAgentsCount: 0,
            managersCount: 0,
            loading: false,

            users: [],
            searchQuery: '',
            filterRole: 'all',
        });

        onWillStart(async () => {
            this.state.loading = true;
            await Promise.all([
                this.fetchUsers(),
                this.fetchTotalUsers(),
                this.fetchActiveUsers(),
                this.fetchSalesAgentsCount(),
                this.fetchManagersCount(),
            ]);
            this.state.loading = false;
        });
    }

    // Redirect to contacts form
    async onCreateUser() {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Create User',
            res_model: 'res.users',
            views: [[false, 'form']],
            target: 'current',
        });
    }

    async fetchUsers() {
        try {
            const users = await this.orm.searchRead('res.users', [], ['name', 'email', 'role', 'active', 'general_manager', 'supervisor', 'create_date', 'active']);
            this.state.users = users;
            console.log("Users =>", this.state.users);
        } catch (error) {
            console.error('Error fetching users:', error);
            this.state.users = [];
        }
    }

    // Fetch total users
    async fetchTotalUsers() {
        try {
            const count = await this.orm.searchCount('res.users', []);
            this.state.totalUsers = count;
        } catch (error) {
            console.error('Error fetching total users:', error);
            this.state.totalUsers = 0;
        }
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value.toLowerCase();
    }

    onFilterChange(ev) {
        this.state.filterRole = ev.target.value;
    }

    get filteredUsers() {
        let users = this.state.users;
        
        // Filter by search query
        if (this.state.searchQuery) {
            users = users.filter(user => 
                user.name?.toLowerCase().includes(this.state.searchQuery) ||
                user.email?.toLowerCase().includes(this.state.searchQuery)
            );
        }
        
        // Filter by role
        if (this.state.filterRole !== 'all') {
            users = users.filter(user => user.role === this.state.filterRole);
        }
        
        return users;
    }
    

    async fetchActiveUsers() {
        try {
            const count = await this.orm.searchCount('res.users', [
                ['active', '=', true]
            ]);
            this.state.activeUsers = count;
        } catch (error) {
            console.error('Error fetching active users:', error);
            this.state.activeUsers = 0;
        }
    }

    async fetchSalesAgentsCount() {
        try {
            const count = await this.orm.searchCount('res.users', [
                ['role', '=', 'sales_agent']
            ]);
            this.state.salesAgentsCount = count;
        } catch (error) {
            console.error('Error fetching sales agents count:', error);
            this.state.salesAgentsCount = 0;
        }
    }

    async fetchManagersCount() {
        try {
            const count = await this.orm.searchCount('res.users', [
                ['role', '=', 'general_manager']
            ]);
            this.state.managersCount = count;
        } catch (error) {
            console.error('Error fetching managers count:', error);
            this.state.managersCount = 0;
        }
    }
}

UserManagement.template = "gobtechnologies.user_management";
registry.category('actions').add('gobtechnologies.user_management', UserManagement);