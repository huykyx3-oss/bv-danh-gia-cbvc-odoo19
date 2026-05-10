/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart } from "@odoo/owl";

const CURRENT_YEAR = new Date().getFullYear();

export class EvaluationDashboard extends Component {
    static template = "bv_danh_gia.Dashboard";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            data: null,
            loading: true,
            chartYear: CURRENT_YEAR,
            chartMode: "avg_all",
            chartEmployeeId: false,
            chartDeptForAvg: false,
            chartDeptFilterForEmployee: false,
            chartNvScores: [],
            chartTpScores: [],
            chartMeta: null,
            chartLoading: false,
            chartEmployees: [],
            chartDepartments: [],
        });
        onWillStart(async () => {
            await this.loadData();
            this.initChartDefaults();
            await Promise.all([this.loadChartFilters(), this.loadChartData()]);
        });
    }

    initChartDefaults() {
        const d = this.state.data;
        if (!d) {
            return;
        }
        if (d.role === "employee") {
            this.state.chartMode = "employee";
            this.state.chartEmployeeId = d.my_employee_id || false;
        } else {
            this.state.chartMode = "avg_all";
            this.state.chartEmployeeId = false;
            this.state.chartDeptForAvg = false;
            this.state.chartDeptFilterForEmployee = false;
        }
    }

    get yearOptions() {
        const years = [];
        for (let y = CURRENT_YEAR; y >= CURRENT_YEAR - 6; y--) {
            years.push(y);
        }
        return years;
    }

    async loadChartFilters() {
        const d = this.state.data;
        if (!d) {
            return;
        }
        if (d.role === "hospital") {
            this.state.chartDepartments = await this.orm.searchRead(
                "hr.department",
                [],
                ["id", "name"],
                { order: "name" },
            );
        } else {
            this.state.chartDepartments = [];
        }
        await this.loadChartEmployeesForFilter();
    }

    async loadChartEmployeesForFilter() {
        const d = this.state.data;
        if (!d || d.role === "employee") {
            return;
        }
        let domain = [];
        if (d.role === "department" && d.my_department_id) {
            domain = [["department_id", "=", d.my_department_id]];
        } else if (
            d.role === "hospital" &&
            this.state.chartMode === "employee" &&
            this.state.chartDeptFilterForEmployee
        ) {
            domain = [["department_id", "=", this.state.chartDeptFilterForEmployee]];
        }
        this.state.chartEmployees = await this.orm.searchRead(
            "hr.employee",
            domain,
            ["id", "name"],
            { order: "name", limit: 800 },
        );
    }

    async loadData() {
        this.state.loading = true;
        this.state.data = await rpc("/bv_danh_gia/dashboard_data", {});
        this.state.loading = false;
    }

    async loadChartData() {
        if (!this.state.data) {
            return;
        }
        this.state.chartLoading = true;
        try {
            const payload = {
                year: this.state.chartYear,
                mode: this.state.chartMode,
                employee_id: this.state.chartEmployeeId || false,
                department_id:
                    this.state.chartMode === "department"
                        ? this.state.chartDeptForAvg || false
                        : false,
            };
            const res = await rpc("/bv_danh_gia/dashboard_chart_data", payload);
            this.state.chartNvScores = res?.nv_scores || [];
            this.state.chartTpScores = res?.tp_scores || [];
            this.state.chartMeta = res?.meta || null;
        } catch (e) {
            console.error(e);
            this.notification.add(
                "Không tải được dữ liệu biểu đồ. " + (e?.message || String(e)),
                { type: "danger", sticky: false },
            );
            this.state.chartNvScores = [];
            this.state.chartTpScores = [];
            this.state.chartMeta = null;
        } finally {
            this.state.chartLoading = false;
        }
    }

    async onChartYearChange(ev) {
        this.state.chartYear = parseInt(ev.target.value, 10) || CURRENT_YEAR;
        await this.loadChartData();
    }

    async onChartModeChange(ev) {
        const mode = ev.target.value;
        this.state.chartMode = mode;
        this.state.chartEmployeeId = false;
        if (mode === "avg_all") {
            this.state.chartDeptForAvg = false;
            this.state.chartDeptFilterForEmployee = false;
        } else if (mode === "department") {
            this.state.chartDeptFilterForEmployee = false;
        } else if (mode === "employee") {
            this.state.chartDeptForAvg = false;
        }
        await this.loadChartEmployeesForFilter();
        await this.loadChartData();
    }

    async onChartDeptForAvgChange(ev) {
        const raw = ev.target.value;
        this.state.chartDeptForAvg = raw ? parseInt(raw, 10) : false;
        await this.loadChartData();
    }

    async onChartEmployeeDeptFilterChange(ev) {
        const raw = ev.target.value;
        this.state.chartDeptFilterForEmployee = raw ? parseInt(raw, 10) : false;
        this.state.chartEmployeeId = false;
        await this.loadChartEmployeesForFilter();
        await this.loadChartData();
    }

    async onChartEmployeeChange(ev) {
        const raw = ev.target.value;
        this.state.chartEmployeeId = raw ? parseInt(raw, 10) : false;
        await this.loadChartData();
    }

    get chartGeometry() {
        const W = 560;
        const H = 260;
        const padL = 44;
        const padR = 16;
        const padT = 16;
        const padB = 40;
        const innerW = W - padL - padR;
        const innerH = H - padT - padB;
        const nv = this.state.chartNvScores || [];
        const tp = this.state.chartTpScores || [];
        const nums = [...nv, ...tp].filter(
            (x) => x !== null && x !== undefined && !Number.isNaN(Number(x)),
        );
        let yMax = 100;
        if (nums.length) {
            const mx = Math.max(...nums.map(Number));
            yMax = Math.max(100, Math.ceil(mx / 5) * 5);
        }
        const xAt = (monthIdx0) => padL + (monthIdx0 / 11) * innerW;
        const yAt = (score) => padT + innerH * (1 - Number(score) / yMax);
        return { W, H, padL, padR, padT, padB, innerW, innerH, yMax, xAt, yAt };
    }

    buildSeriesPoints(scores) {
        const { xAt, yAt } = this.chartGeometry;
        const pts = [];
        for (let i = 0; i < 12; i++) {
            const s = scores[i];
            if (s !== null && s !== undefined && !Number.isNaN(Number(s))) {
                pts.push({
                    x: xAt(i),
                    y: yAt(s),
                    month: i + 1,
                    score: Number(s),
                });
            }
        }
        return pts;
    }

    polylinePointsFromScores(scores) {
        const pts = this.buildSeriesPoints(scores);
        if (pts.length < 2) {
            return "";
        }
        return pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
    }

    get chartNvPolylinePoints() {
        return this.polylinePointsFromScores(this.state.chartNvScores || []);
    }

    get chartTpPolylinePoints() {
        return this.polylinePointsFromScores(this.state.chartTpScores || []);
    }

    get chartNvDots() {
        return this.buildSeriesPoints(this.state.chartNvScores || []);
    }

    get chartTpDots() {
        return this.buildSeriesPoints(this.state.chartTpScores || []);
    }

    get chartYTicks() {
        const { yMax, padT, innerH } = this.chartGeometry;
        return [
            { label: String(yMax), y: padT },
            { label: String(Math.round(yMax / 2)), y: padT + innerH / 2 },
            { label: "0", y: padT + innerH },
        ];
    }

    get chartMonthLabelPositions() {
        const g = this.chartGeometry;
        const labels =
            (this.state.chartMeta && this.state.chartMeta.labels) || [];
        const out = [];
        for (let m = 1; m <= 12; m++) {
            out.push({
                m,
                x: g.xAt(m - 1),
                label: labels[m - 1] || `T${m}`,
            });
        }
        return out;
    }

    get chartHasAnyPoint() {
        const nv = this.state.chartNvScores || [];
        const tp = this.state.chartTpScores || [];
        const has = (arr) =>
            arr.some(
                (x) => x !== null && x !== undefined && !Number.isNaN(Number(x)),
            );
        return has(nv) || has(tp);
    }

    get roleLabel() {
        const d = this.state.data;
        if (!d) {
            return "";
        }
        if (d.role === "hospital") {
            return "Toàn viện";
        }
        if (d.role === "department") {
            return `Khoa/Phòng: ${d.department_name}`;
        }
        return "Cá nhân";
    }

    get classificationLabel() {
        return {
            excellent: "Hoàn thành xuất sắc",
            good: "Hoàn thành tốt",
            fair: "Hoàn thành nhiệm vụ",
            poor: "Không hoàn thành",
        };
    }

    get stateLabel() {
        return {
            draft: "Nháp",
            submitted: "Đã gửi",
            dept_approved: "TK duyệt",
            hr_reviewed: "TCCB duyệt",
            approved: "Đã duyệt",
            rejected: "Trả lại",
        };
    }

    get ratioExceeded() {
        const d = this.state.data;
        if (!d) {
            return false;
        }
        return d.ratio_excellent_actual > d.ratio_excellent;
    }

    openEvaluations(domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Phiếu đánh giá",
            res_model: "bv.monthly.evaluation",
            view_mode: "list,form",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: domain || [],
        });
    }

    openMyEvaluations() {
        const uid = this.state.data?.my_user_id;
        if (!uid) {
            this.action.doAction("bv_danh_gia.action_monthly_evaluation");
            return;
        }
        this.openEvaluations([["employee_id.user_id", "=", uid]]);
    }

    openPendingDept() {
        this.action.doAction("bv_danh_gia.action_monthly_evaluation_dept");
    }

    openPendingHR() {
        this.action.doAction("bv_danh_gia.action_monthly_evaluation_hr");
    }

    openEvaluation(evalId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bv.monthly.evaluation",
            res_id: evalId,
            view_mode: "form",
            views: [[false, "form"]],
        });
    }
}

registry.category("actions").add("bv_danh_gia.dashboard", EvaluationDashboard);
