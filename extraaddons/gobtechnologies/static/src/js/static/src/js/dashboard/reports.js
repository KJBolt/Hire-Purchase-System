/** @odoo-module **/
import {registry} from '@web/core/registry';
import {loadJS} from '@web/core/assets';
import {Component, onWillStart, onMounted, useRef, useState} from '@odoo/owl';

export class Reports extends Component {
    setup() {
        // Tab state
        this.state = useState({
            activeTab: 'repayment',
        });
        this.state.setActiveTab = (tab) => {
            this.state.activeTab = tab;
            // Re-render charts after tab switch (for Sales Report)
            setTimeout(() => {
                this.renderRepaymentCharts();
                this.renderSalesCharts();
                this.renderCommissionCharts();
                this.renderInventoryCharts();
            }, 0);
        };

        // Chart refs
        this.accountStatusChartRef = useRef('accountStatusChartCanvas');
        this.individualRepaymentChartRef = useRef('individualRepaymentChartCanvas');
        this.monthlySalesChartRef = useRef('monthlySalesChartCanvas');
        this.salesTrendChartRef = useRef('salesTrendChartCanvas');
        this.agentCommissionChartRef = useRef('agentCommissionChartCanvas');
        this.stockValueChartRef = useRef('stockValueChartCanvas');

        onWillStart(async () => {
            try {
                await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js");
            } catch (error) {
                console.error("Error loading Chart.js:", error);
            }
        });

        onMounted(() => {
            this.renderRepaymentCharts();
            this.renderSalesCharts();
            this.renderCommissionCharts();
            this.renderInventoryCharts();
        });
    }

    renderRepaymentCharts() {
        if (!window.Chart || this.state.activeTab !== 'repayment') {
            return;
        }

        // Account Status Pie Chart
        if (this.accountStatusChartRef.el) {
            new Chart(this.accountStatusChartRef.el.getContext("2d"), {
                type: "pie",
                data: {
                    labels: ["Active", "Completed", "Defaulted"],
                    datasets: [{
                        data: [6, 1, 1],
                        backgroundColor: ["#3b82f6", "#22c55e", "#f97316"],
                        borderWidth: 2,
                        borderColor: "#ffffff"
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                usePointStyle: true,
                                padding: 20,
                                font: { size: 13 }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((context.raw / total) * 100).toFixed(1);
                                    return `${context.label}: ${context.raw} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }

        // Individual Repayment Horizontal Bar Chart
        if (this.individualRepaymentChartRef.el) {
            new Chart(this.individualRepaymentChartRef.el.getContext("2d"), {
                type: "bar",
                data: {
                    labels: ["Emmanuel Tetteh", "Gifty Amoah", "Bright Osei", "Patience Acheampong", "Isaac Mensah", "Cecilia Boateng"],
                    datasets: [{
                        label: "Repayment %",
                        data: [75.0, 75.0, 50.0, 33.3, 90.0, 100.0],
                        backgroundColor: [
                            "#22c55e",
                            "#22c55e",
                            "#f97316",
                            "#ef4444",
                            "#22c55e",
                            "#22c55e"
                        ],
                        borderRadius: 5,
                        barThickness: 12
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            max: 100,
                            grid: { color: '#f1f5f9' },
                            ticks: {
                                callback: function(value) {
                                    return value + '%';
                                }
                            }
                        },
                        y: {
                            grid: { display: false },
                            ticks: {
                                font: { size: 13 }
                            }
                        }
                    }
                }
            });
        }
    }

    renderSalesCharts() {
        if (!window.Chart || this.state.activeTab !== 'sales') {
            return;
        }

        // Monthly Sales — HP vs Repayments Bar Chart
        if (this.monthlySalesChartRef.el) {
            new Chart(this.monthlySalesChartRef.el.getContext("2d"), {
                type: "bar",
                data: {
                    labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                    datasets: [
                        {
                            label: "Repayments",
                            data: [12, 15, 18, 17, 20, 19, 22, 25, 24, 26, 25, 30],
                            backgroundColor: "#22c55e",
                            borderRadius: 4,
                            barPercentage: 0.6
                        },
                        {
                            label: "HP Sales",
                            data: [16, 19, 22, 23, 25, 24, 27, 29, 28, 30, 29, 35],
                            backgroundColor: "#3b82f6",
                            borderRadius: 4,
                            barPercentage: 0.6
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                usePointStyle: true,
                                padding: 20,
                                font: { size: 12 }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: '#f1f5f9', borderDash: [5, 5] },
                            ticks: {
                                callback: function(value) {
                                    return '₵' + value + 'k';
                                }
                            }
                        },
                        x: {
                            grid: { display: false }
                        }
                    }
                }
            });
        }

        // Sales Trend Line Chart
        if (this.salesTrendChartRef.el) {
            new Chart(this.salesTrendChartRef.el.getContext("2d"), {
                type: "line",
                data: {
                    labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                    datasets: [
                        {
                            label: "Sales Trend",
                            data: [18, 19, 22, 21, 23, 22, 24, 26, 25, 28, 27, 32],
                            borderColor: "#3b82f6",
                            backgroundColor: "rgba(59, 130, 246, 0.1)",
                            tension: 0.4,
                            pointRadius: 0,
                            borderWidth: 2,
                            fill: false
                        },
                        {
                            label: "Repayment Trend",
                            data: [14, 15, 17, 16, 18, 17, 19, 21, 20, 22, 21, 26],
                            borderColor: "#22c55e",
                            backgroundColor: "rgba(34, 197, 94, 0.1)",
                            tension: 0.4,
                            pointRadius: 0,
                            borderWidth: 2,
                            fill: false
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
                        y: {
                            beginAtZero: true,
                            grid: { color: '#f1f5f9', borderDash: [5, 5] },
                            ticks: {
                                callback: function(value) {
                                    return '₵' + value + 'k';
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    renderCommissionCharts() {
        if (!window.Chart || this.state.activeTab !== 'commission') {
            return;
        }

        // Agent Commission Bar Chart
        if (this.agentCommissionChartRef.el) {
            new Chart(this.agentCommissionChartRef.el.getContext("2d"), {
                type: "bar",
                data: {
                    labels: ["Akosua", "Kweku", "Efua"],
                    datasets: [{
                        label: "Commission (€)",
                        data: [900, 420, 745],
                        backgroundColor: "#f97316",
                        borderRadius: 4,
                        barThickness: 60
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 1000,
                            grid: { color: '#f1f5f9', borderDash: [5, 5] },
                            ticks: {
                                callback: function(value) {
                                    return '€' + value;
                                }
                            }
                        },
                        x: {
                            grid: { display: false },
                            ticks: {
                                font: { size: 13 }
                            }
                        }
                    }
                }
            });
        }
    }

    renderInventoryCharts() {
        if (!window.Chart || this.state.activeTab !== 'inventory') {
            return;
        }

        // Stock Value by Location Bar Chart
        if (this.stockValueChartRef.el) {
            new Chart(this.stockValueChartRef.el.getContext("2d"), {
                type: "bar",
                data: {
                    labels: ["Main Warehouse", "Branch A", "Branch B", "Branch C"],
                    datasets: [{
                        label: "Stock Value",
                        data: [200, 75, 50, 25],
                        backgroundColor: "#a855f7",
                        borderRadius: 4,
                        barThickness: 60
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 250,
                            grid: { color: '#f1f5f9', borderDash: [5, 5] },
                            ticks: {
                                callback: function(value) {
                                    return '€' + value + 'k';
                                }
                            }
                        },
                        x: {
                            grid: { display: false },
                            ticks: {
                                font: { size: 12 }
                            }
                        }
                    }
                }
            });
        }
    }
}

Reports.template = "gobtechnologies.reports";
registry.category('actions').add('gobtechnologies.reports', Reports);