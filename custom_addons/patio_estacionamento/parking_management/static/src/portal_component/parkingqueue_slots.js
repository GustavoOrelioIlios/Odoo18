import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry"

export class ParkingqueueSlots extends Component {
    static template = "parking_management.ParkingqueueSlots";
    static props = {};
}

registry.category("public_components").add("parking_management.ParkingqueueSlots", ParkingqueueSlots);