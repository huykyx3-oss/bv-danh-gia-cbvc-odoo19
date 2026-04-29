/** @odoo-module **/
import { registry } from "@web/core/registry";

const evaluationNotificationService = {
    dependencies: ["bus_service", "notification"],

    start(env, { bus_service, notification }) {
        bus_service.subscribe("bv_danh_gia/notification", (payload) => {
            const typeMap = {
                info: "info",
                success: "success",
                warning: "warning",
                danger: "danger",
            };
            notification.add(payload.message, {
                title: payload.title,
                type: typeMap[payload.type] || "info",
                sticky: payload.type === "danger" || payload.type === "warning",
            });
        });
    },
};

registry
    .category("services")
    .add("bv_danh_gia_notification", evaluationNotificationService);
