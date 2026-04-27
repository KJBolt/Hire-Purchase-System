/** @odoo-module **/
import {registry} from '@web/core/registry';
import {loadJS} from '@web/core/assets';
import {Component, onWillStart, onMounted, useRef} from '@odoo/owl';

export class Dashboard extends Component {
    setup() {
        this.salesChartRef = useRef('salesChartCanvas');
        this.donutChartRef = useRef('donutChartCanvas');
        this.agentsChartRef = useRef('agentsChartCanvas');
        this.stockChartRef = useRef('stockChartCanvas');
        
        onWillStart(async () => {
            try {
                await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js");
            } catch (error) {
                console.error("Error loading Chart.js:", error);
            }
        });
        
        onMounted(() => {
            this.renderCharts();
        });
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
                    labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                    datasets: [{
                        label: "Current Year",
                        data: [120, 190, 150, 250, 220, 300],
                        backgroundColor: "#3b82f6",
                        borderRadius: 6,
                    }, {
                        label: "Previous Year",
                        data: [100, 150, 140, 200, 180, 250],
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
                        data: [68.3, 20.5, 11.2],
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
            new Chart(this.agentsChartRef.el.getContext("2d"), {
                type: "bar",
                data: {
                    labels: ["Agent A", "Agent B", "Agent C", "Agent D"],
                    datasets: [{
                        label: "Repayment %",
                        data: [85, 72, 65, 58],
                        backgroundColor: ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"],
                        borderRadius: 4,
                        barThickness: 20
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
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