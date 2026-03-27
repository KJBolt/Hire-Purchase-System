/** @odoo-module **/
import {registry} from '@web/core/registry';
import {loadJS} from '@web/core/assets';
import {Component, onWillStart, onMounted, useRef} from '@odoo/owl';

export class ChartDashboard extends Component{
    setup(){
        this.chartRef = useRef('chartCanvas');
        onWillStart(async () => {
            try{
                await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js")
            } catch (error) {
                console.error("Error loading Chart.js:", error);
            }
                
        });
        onMounted(() => {
            this.renderChart();
        })
    }
    
    renderChart() {
        if (!window.Chart) {
            console.error("Chart.js not loaded yet!");
            return;
        }

        const canvas = this.chartRef.el; // Get the canvas element safely
        if (!canvas) {
            console.error("Canvas element not found!");
            return;
        }

        const ctx = canvas.getContext("2d");

        new Chart(ctx, {
            type: "bar",
            data: {
                labels: ["Jan", "Feb", "Mar", "Apr", "May"],
                datasets: [{
                    label: "Sales",
                    data: [100, 200, 150, 300, 250],
                    backgroundColor: ["red", "blue", "green", "purple", "orange"],
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }


}

ChartDashboard.template = "gobtechnologies.chartDashboard";

registry.category('actions').add('gobtechnologies.chartDashboard', ChartDashboard);