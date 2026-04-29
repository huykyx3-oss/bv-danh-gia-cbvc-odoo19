/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

export class EvaluationDashboard extends Component {
    static template = "bv_danh_gia.Dashboard";
    static props = ["*"];

    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.state = useState({
            data: null,
            loading: true,
        });
        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        this.state.data = await this.rpc("/bv_danh_gia/dashboard_data", {});
        this.state.loading = false;
    }

    get roleLabel() {
        const d = this.state.data;
        if (!d) return '';
        if (d.role === 'hospital') return 'Toàn viện';
        if (d.role === 'department') return `Khoa/Phòng: ${d.department_name}`;
        return 'Cá nhân';
    }

    get classificationLabel() {
        return {
            excellent: 'Hoàn thành xuất sắc',
            good: 'Hoàn thành tốt',
            fair: 'Hoàn thành nhiệm vụ',
            poor: 'Không hoàn thành',
        };
    }

    get stateLabel() {
        return {
            draft: 'Nháp',
            submitted: 'Đã gửi',
            dept_approved: 'TK duyệt',
            hr_reviewed: 'TCCB duyệt',
            approved: 'Đã duyệt',
            rejected: 'Trả lại',
        };
    }

    get ratioExceeded() {
        const d = this.state.data;
        if (!d) return false;
        return d.ratio_excellent_actual > d.ratio_excellent;
    }

    openEvaluations(domain) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Phiếu đánh giá',
            res_model: 'bv.monthly.evaluation',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: domain || [],
        });
    }

    openMyEvaluations() {
        this.openEvaluations([['employee_id.user_id', '=', this.state.data ? 0 : 0]]);
        this.action.doAction('bv_danh_gia.action_monthly_evaluation');
    }

    openPendingDept() {
        this.action.doAction('bv_danh_gia.action_monthly_evaluation_dept');
    }

    openPendingHR() {
        this.action.doAction('bv_danh_gia.action_monthly_evaluation_hr');
    }

    openEvaluation(evalId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'bv.monthly.evaluation',
            res_id: evalId,
            view_mode: 'form',
            views: [[false, 'form']],
        });
    }
}

registry.category("actions").add("bv_danh_gia.dashboard", EvaluationDashboard);
