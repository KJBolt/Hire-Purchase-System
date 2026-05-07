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
            topAgents: [],
            chartData: {
                currentYear: [0, 0, 0, 0, 0, 0],
                previousYear: [0, 0, 0, 0, 0, 0],
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
            },
            loading: true
        });
        
        onWillStart(async () => {
            try {
                await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js");
                // Fetch data on component start
                await Promise.all([
                    this.fetchTotalRepayment(),
                    this.fetchSalesManagersCount(),
                    this.fetchSalesAgentsCount(),
                    this.fetchDailyCommission(),
                    this.fetchMonthlyCommission(),
                    this.fetchTotalStockValue(),
                    this.fetchMonthlySales(),
                    this.fetchOverdueAccounts(),
                    this.fetchPaymentDistribution(),
                    this.fetchCustomerInstallments(),
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
            // Get today's date
            const today = new Date().toISOString().split('T')[0];
            
            // Fetch sales commissions from repayment contracts created today
            const result = await this.orm.searchRead('repayment', [
                ['create_date', '>=', today + ' 00:00:00'],
                ['create_date', '<=', today + ' 23:59:59']
            ], ['sales_commission']);
            
            // Calculate total daily commission
            const total = result.reduce((sum, record) => sum + (record.sales_commission || 0), 0);
            
            // Update state with daily commission
            this.state.dailyCommission = total;
        } catch (error) {
            console.error('Error fetching daily commission:', error);
        }
    }

    // Fetch Monthly Commission
    async fetchMonthlyCommission() {
        try {
            // Get current month's first and last day
            const now = new Date();
            const firstDay = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
            const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];
            
            // Fetch sales commissions from repayment contracts created this month
            const result = await this.orm.searchRead('repayment', [
                ['create_date', '>=', firstDay + ' 00:00:00'],
                ['create_date', '<', lastDay + ' 00:00:00']
            ], ['sales_commission']);
            
            // Calculate total monthly commission
            const total = result.reduce((sum, record) => sum + (record.sales_commission || 0), 0);
            
            // Update state with monthly commission
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
            // Get current month's first and last day
            const now = new Date();
            const firstDay = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
            const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];
            
            // Fetch selling prices from fully paid repayment contracts created this month
            const result = await this.orm.searchRead('repayment', [
                ['create_date', '>=', firstDay + ' 00:00:00'],
                ['create_date', '<', lastDay + ' 00:00:00'],
                ['state', '=', 'paid']
            ], ['selling_price']);
            
            // Calculate total monthly sales from fully paid contracts only
            const total = result.reduce((sum, record) => sum + (record.selling_price || 0), 0);
            
            // Update state with monthly sales
            this.state.monthlySales = total;
        } catch (error) {
            console.error('Error fetching monthly sales:', error);
        }
    }

    // Fetch Overdue Accounts
    async fetchOverdueAccounts() {
        try {
            // Fetch count of overdue accounts using overdue_status field
            const result = await this.orm.searchCount('repayment', [
                ['overdue_status', '=', true]
            ]);
            
            // Update state with overdue accounts count
            this.state.overdueAccounts = result;
            
            console.log('Overdue accounts:', result);
        } catch (error) {
            console.error('Error fetching overdue accounts:', error);
        }
    }

    // Fetch Total Repayment
    async fetchTotalRepayment() {
        try {
            // Fetch total repayment amount from Repayment model
            const result = await this.orm.searchRead('repayment', [], ['repayment']);
            
            // Calculate total repayment amount
            const total = result.reduce((sum, record) => sum + (record.repayment || 0), 0);
            
            // Update state with formatted total
            this.state.totalRepayment = total;
            this.state.loading = false;
            
            console.log('Total repayment amount:', total);
        } catch (error) {
            console.error('Error fetching total repayment:', error);
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
    async fetchChartData() {
        try {
            const now = new Date();
            const currentYear = now.getFullYear();
            const previousYear = currentYear - 1;
            
            // Initialize arrays for 6 months (Jan-Jun)
            const currentYearData = [0, 0, 0, 0, 0, 0];
            const previousYearData = [0, 0, 0, 0, 0, 0];
            
            // Fetch current year data (Jan-Jun)
            for (let month = 0; month < 6; month++) {
                const firstDay = new Date(currentYear, month, 1).toISOString().split('T')[0];
                const lastDay = new Date(currentYear, month + 1, 0).toISOString().split('T')[0];
                
                const result = await this.orm.searchRead('repayment', [
                    ['create_date', '>=', firstDay + ' 00:00:00'],
                    ['create_date', '<', lastDay + ' 00:00:00'],
                    ['state', '=', 'paid']
                ], ['selling_price']);
                
                currentYearData[month] = result.reduce((sum, record) => sum + (record.selling_price || 0), 0);
            }
            
            // Fetch previous year data (Jan-Jun)
            for (let month = 0; month < 6; month++) {
                const firstDay = new Date(previousYear, month, 1).toISOString().split('T')[0];
                const lastDay = new Date(previousYear, month + 1, 0).toISOString().split('T')[0];
                
                const result = await this.orm.searchRead('repayment', [
                    ['create_date', '>=', firstDay + ' 00:00:00'],
                    ['create_date', '<', lastDay + ' 00:00:00'],
                    ['state', '=', 'paid']
                ], ['selling_price']);
                
                previousYearData[month] = result.reduce((sum, record) => sum + (record.selling_price || 0), 0);
            }
            
            // Update state with chart data
            this.state.chartData = {
                currentYear: currentYearData,
                previousYear: previousYearData,
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
            };
            
            console.log('Chart data fetched:', { currentYear: currentYearData, previousYear: previousYearData });
        } catch (error) {
            console.error('Error fetching chart data:', error);
        }
    }
    
    renderCharts() {
        if (!window.Chart) {
            console.error("Chart.js not loaded yet!");
            return;
        }
        
        // Sales Bar Chart
        if (this.salesChartRef.el) {
            new Chart(this.salesChartRef.el.getContext("2d"), {
                type: "bar",
                data: {
                    labels: this.state.chartData.labels,
                    datasets: [{
                        label: "Current Year",
                        data: this.state.chartData.currentYear,
                        backgroundColor: "#3b82f6",
                        borderRadius: 6,
                    }, {
                        label: "Previous Year",
                        data: this.state.chartData.previousYear,
                        backgroundColor: "#10b981",
                        borderRadius: 6,
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
            new Chart(this.stockChartRef.el.getContext("2d"), {
                type: "line",
                data: {
                    labels: ["Week 1", "Week 2", "Week 3", "Week 4"],
                    datasets: [
                        {
                            label: "0-30 days",
                            data: [150, 180, 200, 220],
                            borderColor: "#3b82f6",
                            backgroundColor: "rgba(59, 130, 246, 0.1)",
                            fill: true,
                            tension: 0.4
                        },
                        {
                            label: "31-60 days",
                            data: [80, 90, 85, 95],
                            borderColor: "#10b981",
                            backgroundColor: "rgba(16, 185, 129, 0.1)",
                            fill: true,
                            tension: 0.4
                        },
                        {
                            label: "61-90 days",
                            data: [40, 45, 50, 48],
                            borderColor: "#f59e0b",
                            backgroundColor: "rgba(245, 158, 11, 0.1)",
                            fill: true,
                            tension: 0.4
                        },
                        {
                            label: "90+ days",
                            data: [20, 25, 30, 28],
                            borderColor: "#ef4444",
                            backgroundColor: "rgba(239, 68, 68, 0.1)",
                            fill: true,
                            tension: 0.4
                        }
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