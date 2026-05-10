/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/* ─────────────────────────────────────────────────────────
   BvBinaryField — custom upload widget for grid containers
   Replaces widget="binary" which fails inside custom divs.
   Usage in view: widget="bv_binary" options="{'fn':'field_name_of_filename'}"
   ───────────────────────────────────────────────────────── */
class BvBinaryField extends Component {
    static template = xml`
<div class="bv-bf-wrap">
    <t t-if="uploadVisible">
        <label class="bv-ev-btn">
            <i class="fa fa-upload"/> <span>Tải lên</span>
            <input type="file" accept=".pdf" t-on-change="onUpload" style="display:none"/>
        </label>
    </t>
    <t t-if="hasValue">
        <a t-att-href="downloadUrl" target="_blank" class="bv-ev-dl"
           t-att-title="filename">
            <i class="fa fa-download"/> <t t-esc="shortName"/>
        </a>
    </t>
    <t t-if="!hasValue and props.readonly">
        <span style="color:#bbb;font-style:italic;font-size:11px;">—</span>
    </t>
</div>`;

    static props = ["*"];

    setup() {
        this.notif = useService("notification");
    }

    get uploadVisible() {
        const ro = this.props.readonly;
        return !ro;
    }

    get filenameFieldName() {
        return (this.props.options && this.props.options.fn) || null;
    }

    get hasValue() {
        return !!this.props.record.data[this.props.name];
    }

    get filename() {
        const ff = this.filenameFieldName;
        return ff ? (this.props.record.data[ff] || "") : "";
    }

    get shortName() {
        const n = this.filename || "pdf";
        return n.length > 22 ? n.substring(0, 22) + "…" : n;
    }

    get downloadUrl() {
        const id = this.props.record.resId;
        const model = this.props.record.resModel;
        const field = this.props.name;
        const ff = this.filenameFieldName;
        const fnPart = ff ? `&filename_field=${ff}` : "";
        return `/web/content?model=${model}&id=${id}&field=${field}${fnPart}&download=true`;
    }

    async onUpload(ev) {
        const file = ev.target.files[0];
        if (!file) return;
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            this.notif.add("Chỉ chấp nhận file PDF", { type: "danger" });
            ev.target.value = "";
            return;
        }
        const reader = new FileReader();
        reader.onload = async (e) => {
            const b64 = e.target.result.split(",")[1];
            const upd = { [this.props.name]: b64 };
            const ff = this.filenameFieldName;
            if (ff) upd[ff] = file.name;
            await this.props.record.update(upd);
        };
        reader.readAsDataURL(file);
    }
}

registry.category("fields").add("bv_binary", { component: BvBinaryField, supportedTypes: ["binary"] });
/* ───────────────────────────────────────────────────────── */

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
