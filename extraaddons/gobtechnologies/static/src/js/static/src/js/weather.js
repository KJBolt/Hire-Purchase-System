/** @odoo-module **/
import {registry} from "@web/core/registry";
import {Component, useState, onWillStart} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

// Load Axios from static files
const axiosScript = document.createElement('script');
axiosScript.src = '/gobtechnologies/static/lib/axios.min.js';
document.head.appendChild(axiosScript);

export class Weather extends Component{
    setup(){
        this.orm = useService('orm');
        this.action = useService('action');
        this.notification = useService('notification');
        this.busService = this.env.services.bus_service;
        this.rpc = useService('rpc');

        this.state = useState({
            weatherData: null,
            isLoading: false,
        });

        onWillStart(async() => {
            await this.fetchWeather();
        })
    }

    async fetchWeather(){
        this.state.isLoading = true;
        if (!window.axios) {
            console.error("Axios is not loaded.");
            return;
        }

        const url = `https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=60&lon=10`;

        try {
            const response = await axios.get(url);
            this.state.weatherData = response.data['geometry']['coordinates'];
            this.notification.add('Data fetched successfully', {type: 'success'});
            this.state.isLoading = false;
        } catch (error) {
            console.error("Error fetching weather:", error);
            this.state.isLoading = false;
        }
    }
}

Weather.template = "gobtechnologies.weather";

registry.category('actions').add('gobtechnologies.weather', Weather);

