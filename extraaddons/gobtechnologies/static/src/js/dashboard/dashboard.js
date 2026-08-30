/** @odoo-module **/
import {registry} from '@web/core/registry';
import {loadJS} from '@web/core/assets';
import {Component, onWillStart, onMounted, useRef, useState} from '@odoo/owl';
import {useService} from '@web/core/utils/hooks';

export class Dashboard extends Component {
    setup() {
        this.orm = useService('orm');
        this.salesChartRef = useRef('salesChartCanvas');
        this.donutChartRef = useRef('donutChartCanvas');
        this.agentsChartRef = useRef('agentsChartCanvas');
        this.stockChartRef = useRef('stockChartCanvas');

        // Helper function to format numbers with commas
        this.formatNumberWithCommas = (num) => {
            return num.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        };

        // States for dashboard data
        this.state = useState({
            totalRepayment: 0,
            totalDeposit: 0,
            dailyRepayment: 0,
            dailyDeposit: 0,
            salesManagersCount: 0,
            salesAgentsCount: 0,
            dailyCommission: 0,
            monthlyCommission: 0,
            totalStockValue: 0,
            monthlySales: 0,
            overdueAccounts: 0,
            paymentDistribution: {
                paid: 0,
                pending: 0,
                overdue: 0
            },
            customerInstallments: [],
            agentPerformance: [],
            topAgents: [],
            chartData: {
                currentYear: [],
                previousYear: [],
                labels: []
            },
            chartPeriod: 'monthly',
            stockAgingData: {
                '0-30': 0,
                '31-60': 0,
                '61-90': 0,
                '90+': 0
            },
            expandedAgent: null,
            loading: true
        });
        
        onWillStart(async () => {
            try {
                await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js");
                // Fetch data on component start
                await Promise.all([
                    this.fetchTotalRepayment(),
                    this.fetchTotalDeposit(),
                    this.fetchDailyRepayment(),
                    this.fetchDailyDeposit(),
                    this.fetchSalesManagersCount(),
                    this.fetchSalesAgentsCount(),
                    this.fetchDailyCommission(),
                    this.fetchMonthlyCommission(),
                    this.fetchTotalStockValue(),
                    this.fetchMonthlySales(),
                    this.fetchOverdueAccounts(),
                    this.fetchPaymentDistribution(),
                    this.fetchCustomerInstallments(),
                    this.fetchAgentPerformance(),
                    this.fetchTopAgents(),
                    this.fetchChartData()
                ]);
            } catch (error) {
                console.error("Error loading Chart.js:", error);
            }
        });
        
        onMounted(() => {
            this.renderCharts();
        });
    }

    // Fetch Sales Managers Count  
    async fetchSalesManagersCount() {
    try {
            // Fetch sales managers count from res.partner model
            const result = await this.orm.searchCount('res.partner', [
                ['role', '=', 'sales_manager']
            ]);
            
            // Update state with sales managers count
            this.state.salesManagersCount = result;
        } catch (error) {
            console.error('Error fetching sales managers count:', error);
        }
    }

    // Fetch Sales Agents Count
    async fetchSalesAgentsCount() {
        try {
            // Fetch sales agents count from res.partner model
            const result = await this.orm.searchCount('res.partner', [
                ['role', '=', 'sales_agent']
            ]);
            
            // Update state with sales agents count
            this.state.salesAgentsCount = result;
        } catch (error) {
            console.error('Error fetching sales agents count:', error);
        }
    }

    // Fetch Daily Commission
    async fetchDailyCommission() {
        try {
            const total = await this.orm.call('repayment', 'get_daily_commission_by_role', []);
            this.state.dailyCommission = total;
        } catch (error) {
            console.error('Error fetching daily commission:', error);
        }
    }

    // Fetch Monthly Commission
    async fetchMonthlyCommission() {
        try {
            const total = await this.orm.call('repayment', 'get_monthly_commission_by_role', []);
            this.state.monthlyCommission = total;
        } catch (error) {
            console.error('Error fetching monthly commission:', error);
        }
    }

    // Fetch Total Stock Value
    async fetchTotalStockValue() {
        try {
            // Fetch total value from product.product model
            const result = await this.orm.searchRead('product.product', [], ['total_value']);
            
            // Calculate total stock value
            const total = result.reduce((sum, record) => sum + (record.total_value || 0), 0);
            
            // Update state with total stock value
            this.state.totalStockValue = total;
        } catch (error) {
            console.error('Error fetching total stock value:', error);
        }
    }

    // Fetch Monthly Sales
    async fetchMonthlySales() {
        try {
            const total = await this.orm.call('repayment', 'get_monthly_sales_by_role', []);
            this.state.monthlySales = total;
        } catch (error) {
            console.error('Error fetching monthly sales:', error);
        }
    }

    // Fetch Overdue Accounts
    async fetchOverdueAccounts() {
        try {
            const result = await this.orm.call('repayment', 'get_overdue_accounts_by_role', []);
            this.state.overdueAccounts = result;
        } catch (error) {
            console.error('Error fetching overdue accounts:', error);
        }
    }

    // Fetch Total Repayment
    async fetchTotalRepayment() {
        try {
            const total = await this.orm.call('repayment', 'get_total_repayment_by_role', []);
            this.state.totalRepayment = total;
            this.state.loading = false;
        } catch (error) {
            console.error('Error fetching total repayment:', error);
            this.state.loading = false;
        }
    }

    // Fetch Total Deposit
    async fetchTotalDeposit() {
        try {
            const total = await this.orm.call('repayment', 'get_total_deposit_by_role', []);
            this.state.totalDeposit = total;
            this.state.loading = false;
        } catch (error) {
            console.error('Error fetching total deposit:', error);
            this.state.loading = false;
        }
    }

    // Fetch Daily Repayment
    async fetchDailyRepayment() {
        try {
            const total = await this.orm.call('repayment', 'get_daily_repayment_by_role', []);
            this.state.dailyRepayment = total;
            this.state.loading = false;
        } catch (error) {
            console.error('Error fetching daily repayment:', error);
            this.state.loading = false;
        }
    }

    // Fetch Daily Deposit
    async fetchDailyDeposit() {
        try {
            const total = await this.orm.call('repayment', 'get_daily_deposit_by_role', []);
            this.state.dailyDeposit = total;
            this.state.loading = false;
        } catch (error) {
            console.error('Error fetching daily deposit:', error);
            this.state.loading = false;
        }
    }

    // Fetch Payment Distribution
    async fetchPaymentDistribution() {
        try {
            // Call the get_payment_distribution method from the repayment model
            const result = await this.orm.call('repayment', 'get_payment_distribution', []);
            
            // Update state with payment distribution data
            this.state.paymentDistribution = result;
        } catch (error) {
            console.error('Error fetching payment distribution:', error);
        }
    }

    // Fetch Customer Installments
    async fetchCustomerInstallments() {
        try {
            // Call the get_active_customer_installments method from the repayment model
            const result = await this.orm.call('repayment', 'get_active_customer_installments', [10]);
            
            // Update state with customer installments data
            this.state.customerInstallments = result;
        } catch (error) {
            console.error('Error fetching customer installments:', error);
        }
    }

    async fetchAgentPerformance() {
        try {
            const result = await this.orm.call('repayment', 'get_agent_payment_performance', []);
            this.state.agentPerformance = result;
        } catch (error) {
            console.error('Error fetching agent performance:', error);
        }
    }

    // Fetch Top Agents
    async fetchTopAgents() {
        try {
            // Call the get_top_agents_by_performance method from the repayment model
            const result = await this.orm.call('repayment', 'get_top_agents_by_performance', [5]);
            
            // Update state with top agents data
            this.state.topAgents = result;
        } catch (error) {
            console.error('Error fetching top agents:', error);
        }
    }

    // Fetch Chart Data for Monthly Sales Performance
    async fetchChartData(period) {
        try {
            const p = period || this.state.chartPeriod || 'monthly';
            const result = await this.orm.call('repayment', 'get_sales_performance_data', [], { period: p });
            this.state.chartData = {
                labels: result.labels,
                currentYear: result.currentYear,
                previousYear: result.previousYear,
            };
            this._renderSalesChart();
        } catch (error) {
            console.error('Error fetching chart data:', error);
        }
    }

    onPeriodChange(ev) {
        this.state.chartPeriod = ev.target.value;
        this.fetchChartData(this.state.chartPeriod);
    }

    toggleAgent(agentName) {
        this.state.expandedAgent = this.state.expandedAgent === agentName ? null : agentName;
    }

    openRecord(model, id) {
        this.env.services['action'].doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
        });
    }

    _renderSalesChart() {
        if (this._salesChart) {
            this._salesChart.destroy();
        }
        if (!this.salesChartRef.el || !window.Chart) return;
        this._salesChart = new Chart(this.salesChartRef.el.getContext("2d"), {
            type: "line",
            data: {
                labels: this.state.chartData.labels,
                datasets: [{
                    label: "Current Period",
                    data: this.state.chartData.currentYear,
                    borderColor: "#3b82f6",
                    backgroundColor: "rgba(59, 130, 246, 0.1)",
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: "#3b82f6",
                    pointRadius: 4,
                }, {
                    label: "Previous Period",
                    data: this.state.chartData.previousYear,
                    borderColor: "#10b981",
                    backgroundColor: "rgba(16, 185, 129, 0.1)",
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: "#10b981",
                    pointRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { usePointStyle: true, padding: 20 }
                    }
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: '#f3f4f6' } },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    // Add this method to fetch stock aging data
    async fetchStockAgingData() {
        try {
            // Get stock quantities with aging information
            const stockData = await this.orm.call('stock.quant', 'read_group', [
                // Domain: only positive stock
                [['quantity', '>', 0]],
                // Fields to group by
                ['product_id', 'location_id', 'quantity', 'in_date'],
                // Group by
                ['product_id', 'location_id'],
                // Lazy loading
                false,
            ]);
            
            // Calculate aging based on in_date (when stock was received)
            const today = new Date();
            const agingCategories = {
                '0-30': 0,
                '31-60': 0, 
                '61-90': 0,
                '90+': 0
            };
            
            stockData.forEach(record => {
                if (record.in_date) {
                    const inDate = new Date(record.in_date);
                    const daysOld = Math.floor((today - inDate) / (1000 * 60 * 60 * 24));
                    
                    if (daysOld <= 30) agingCategories['0-30'] += record.quantity;
                    else if (daysOld <= 60) agingCategories['31-60'] += record.quantity;
                    else if (daysOld <= 90) agingCategories['61-90'] += record.quantity;
                    else agingCategories['90+'] += record.quantity;
                }
            });
            
            // Update state with aging data
            this.state.stockAgingData = agingCategories;
            
        } catch (error) {
            console.error('Error fetching stock aging data:', error);
            // Set default values on error
            this.state.stockAgingData = {
                '0-30': 0,
                '31-60': 0,
                '61-90': 0,
                '90+': 0
            };
        }
    }
    
    renderCharts() {
        if (!window.Chart) {
            console.error("Chart.js not loaded yet!");
            return;
        }
        
        // Sales Bar Chart
        this._renderSalesChart();
        
        // Payment Distribution Donut
        if (this.donutChartRef.el) {
            new Chart(this.donutChartRef.el.getContext("2d"), {
                type: "doughnut",
                data: {
                    labels: ["Paid", "Pending", "Overdue"],
                    datasets: [{
                        data: [
                            this.state.paymentDistribution.paid,
                            this.state.paymentDistribution.pending,
                            this.state.paymentDistribution.overdue
                        ],
                        backgroundColor: ["#3b82f6", "#ef4444", "#10b981"],
                        borderWidth: 0,
                        cutout: "75%"
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }
        
        // Agents Horizontal Bar
        if (this.agentsChartRef.el) {
            // Extract agent names and percentages from state
            const agentNames = this.state.topAgents.map(agent => agent.agent_name);
            const agentPercentages = this.state.topAgents.map(agent => agent.repayment_percentage);
            
            // Generate colors for bars
            const colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];
            const backgroundColors = agentNames.map((_, index) => colors[index % colors.length]);
            
            new Chart(this.agentsChartRef.el.getContext("2d"), {
                type: "bar",
                data: {
                    labels: agentNames.length > 0 ? agentNames : ["No Data"],
                    datasets: [{
                        label: "Repayment %",
                        data: agentPercentages.length > 0 ? agentPercentages : [0],
                        backgroundColor: backgroundColors,
                        borderRadius: 4,
                        barThickness: 20
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { 
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const agentIndex = context.dataIndex;
                                    const agent = this.state.topAgents[agentIndex];
                                    if (agent) {
                                        return [
                                            `Repayment: ${agent.repayment_percentage}%`,
                                            `Total Sales: ₵${agent.total_value.toLocaleString()}`,
                                            `Paid Sales: ₵${agent.paid_value.toLocaleString()}`,
                                            `Contracts: ${agent.paid_repayments}/${agent.total_repayments}`
                                        ];
                                    }
                                    return `Repayment: ${context.parsed.x}%`;
                                }.bind(this)
                            }
                        }
                    },
                    scales: {
                        x: { beginAtZero: true, max: 100, grid: { color: '#f3f4f6' } },
                        y: { grid: { display: false } }
                    }
                }
            });
        }
        
        // Stock Aging Line Chart
        if (this.stockChartRef.el) {
            const agingData = this.state.stockAgingData || {
                '0-30': 0,
                '31-60': 0, 
                '61-90': 0,
                '90+': 0
            };
            new Chart(this.stockChartRef.el.getContext("2d"), {
                type: "line",
                data: {
                    labels: ["Week 1", "Week 2", "Week 3", "Week 4"],
                    datasets: [
                        {
                            label: "0-30 days",
                            data: [agingData['0-30'] * 0.9, agingData['0-30'], agingData['0-30'] * 1.1, agingData['0-30'] * 1.2],
                            borderColor: "#3b82f6",
                            backgroundColor: "rgba(59, 130, 246, 0.1)",
                            fill: true,
                            tension: 0.4
                        },
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: { beginAtZero: true, grid: { color: '#f3f4f6' } },
                        x: { grid: { display: false } }
                    }
                }
            });
        }
    }
}

Dashboard.template = "gobtechnologies.dashboard";
registry.category('actions').add('gobtechnologies.dashboard', Dashboard);