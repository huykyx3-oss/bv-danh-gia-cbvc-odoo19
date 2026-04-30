/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";

export class EvaluationFormView extends Component {
    static template = "bv_danh_gia.EvaluationFormView";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");

        const actionProps = this.props.action || {};
        const ctx = actionProps.context || {};
        this.evalId = ctx.active_id || ctx.eval_id || false;

        this.state = useState({
            loading: true,
            saving: false,
            record: null,
            criteria_groups: [],
            task_fields: [],
            scores: {},
            deptScores: {},
            totalGeneral: 0,
            totalDeptGeneral: 0,
            totalTask: 0,
            totalScore: 0,
            generalMax: 30,
            taskMax: 70,
            classification: '',
            filledCount: 0,
            totalCriteria: 0,
            isDeptManager: false,
            canEditDept: false,
        });

        onWillStart(async () => {
            this.state.isDeptManager = await this.orm.call(
                'res.users', 'has_group',
                [[session.uid], 'bv_danh_gia.group_evaluation_dept_manager'],
            );
            if (this.evalId) {
                await this.loadRecord();
            } else {
                this.state.loading = false;
            }
        });
    }

    async loadRecord() {
        this.state.loading = true;
        const [record] = await this.orm.read('bv.monthly.evaluation', [this.evalId], [
            'employee_id', 'department_id', 'job_id', 'month', 'year',
            'is_manager', 'state', 'general_score', 'task_score', 'total_score',
            'general_score_max', 'task_score_max',
            'classification', 'strengths', 'weaknesses', 'authority_comment',
            'pct_quantity', 'pct_quality', 'pct_progress',
            'pct_field_result', 'pct_organization', 'pct_team_cohesion',
            'criteria_line_ids', 'display_name',
        ]);
        this.state.record = record;
        this.state.generalMax = record.general_score_max || 30;
        this.state.taskMax = record.task_score_max || 70;
        // Manager can score only when state is 'submitted' (waiting for dept approval)
        this.state.canEditDept = this.state.isDeptManager && record.state === 'submitted';

        const lineIds = record.criteria_line_ids;
        if (lineIds && lineIds.length > 0) {
            const lines = await this.orm.read('bv.evaluation.criteria.line', lineIds, [
                'criteria_id', 'parent_criteria_id', 'max_score',
                'self_score', 'dept_score', 'final_score', 'sequence',
            ]);
            lines.sort((a, b) => a.sequence - b.sequence);

            const groups = {};
            for (const line of lines) {
                const parentName = line.parent_criteria_id ? line.parent_criteria_id[1] : 'Khác';
                const parentId = line.parent_criteria_id ? line.parent_criteria_id[0] : 0;
                if (!groups[parentId]) {
                    groups[parentId] = {
                        id: parentId,
                        name: parentName,
                        criteria: [],
                        maxScore: 0,
                        currentScore: 0,
                    };
                }
                const g = groups[parentId];
                const options = this._buildOptions(line.max_score);
                g.criteria.push({
                    lineId: line.id,
                    name: line.criteria_id[1],
                    maxScore: line.max_score,
                    selfScore: line.self_score,
                    deptScore: line.dept_score,
                    finalScore: line.final_score,
                    options: options,
                    selectedScore: line.self_score,
                });
                g.maxScore += line.max_score;
                g.currentScore += line.final_score;
                this.state.scores[line.id] = line.self_score;
                this.state.deptScores[line.id] = line.dept_score;
            }
            this.state.criteria_groups = Object.values(groups);
        }

        this._buildTaskFields();
        this._recalculate();
        this.state.loading = false;
    }

    _buildOptions(maxScore) {
        if (maxScore === 5) {
            return [
                { score: 5, label: 'Gương mẫu, được tập thể ghi nhận', desc: 'Không vi phạm, gương mẫu, hoàn thành xuất sắc' },
                { score: 4, label: 'Có góp ý nhưng chưa đến mức nhắc nhở', desc: 'Chấp hành nghiêm quy định, phẩm chất tốt' },
                { score: 3, label: 'Có nhắc nhở bằng văn bản', desc: 'Chấp hành đầy đủ, đáp ứng yêu cầu' },
                { score: 2, label: 'Bị kiểm điểm / kỷ luật', desc: 'Chấp hành chưa nghiêm, ý thức hạn chế' },
                { score: 1, label: 'Vi phạm nghiêm trọng', desc: 'Không chấp hành, có biểu hiện vi phạm' },
            ];
        }
        if (maxScore === 2.5) {
            return [
                { score: 2.5, label: 'Xuất sắc, nổi bật', desc: 'Hoàn thành vượt mức yêu cầu, tích cực đóng góp' },
                { score: 2, label: 'Tốt', desc: 'Hoàn thành tốt nhiệm vụ, không sai sót' },
                { score: 1.5, label: 'Đạt yêu cầu', desc: 'Hoàn thành nhiệm vụ ở mức đáp ứng' },
                { score: 1, label: 'Còn hạn chế', desc: 'Có sai sót, cần cải thiện' },
                { score: 0.5, label: 'Yếu', desc: 'Chưa đáp ứng yêu cầu' },
                { score: 0, label: 'Không đạt', desc: 'Không hoàn thành nhiệm vụ' },
            ];
        }
        const steps = 5;
        const step = maxScore / steps;
        const options = [];
        for (let i = steps; i >= 0; i--) {
            const s = Math.round(step * i * 10) / 10;
            options.push({ score: s, label: `${s} điểm`, desc: '' });
        }
        return options;
    }

    _buildTaskFields() {
        const r = this.state.record;
        if (!r) return;
        // All 6 fields defined; managerOnly=true fields visible only when is_manager toggled
        this.state.task_fields = [
            { key: 'pct_quantity',    label: 'a) Số lượng thực hiện chỉ tiêu, nhiệm vụ chuyên môn', value: r.pct_quantity || 0,    managerOnly: false },
            { key: 'pct_quality',     label: 'b) Chất lượng kết quả thực hiện nhiệm vụ được giao',  value: r.pct_quality || 0,     managerOnly: false },
            { key: 'pct_progress',    label: 'c) Tiến độ thực hiện',                                  value: r.pct_progress || 0,    managerOnly: false },
            { key: 'pct_field_result',label: 'd) Kết quả hoạt động lĩnh vực phụ trách',              value: r.pct_field_result || 0,managerOnly: true  },
            { key: 'pct_organization',label: 'đ) Khả năng tổ chức triển khai thực hiện',             value: r.pct_organization || 0,managerOnly: true  },
            { key: 'pct_team_cohesion',label: 'e) Năng lực tập hợp đoàn kết',                        value: r.pct_team_cohesion || 0,managerOnly: true },
        ];
    }

    selectCriteriaScore(lineId, score) {
        if (this.state.record && this.state.record.state !== 'draft') return;
        this.state.scores[lineId] = score;
        for (const g of this.state.criteria_groups) {
            for (const c of g.criteria) {
                if (c.lineId === lineId) {
                    c.selectedScore = score;
                    c.selfScore = score;
                }
            }
        }
        this._recalculate();
    }

    /** Dept manager scores a criteria line (max bounded by line.maxScore) */
    updateDeptScore(lineId, rawValue, maxScore) {
        if (!this.state.canEditDept) return;
        const v = Math.min(maxScore, Math.max(0, parseFloat(rawValue) || 0));
        this.state.deptScores[lineId] = v;
        for (const g of this.state.criteria_groups) {
            for (const c of g.criteria) {
                if (c.lineId === lineId) c.deptScore = v;
            }
        }
        this._recalculate();
    }

    /** Replace radio-button selection: user types a percentage 0–100 */
    updateTaskPct(key, rawValue) {
        if (this.state.record && this.state.record.state !== 'draft') return;
        const numVal = Math.min(100, Math.max(0, parseFloat(rawValue) || 0));
        for (const f of this.state.task_fields) {
            if (f.key === key) f.value = numVal;
        }
        this._recalculate();
    }

    /** Toggle "đánh giá với tư cách lãnh đạo / quản lý" */
    toggleManager() {
        if (this.state.record && this.state.record.state !== 'draft') return;
        this.state.record.is_manager = !this.state.record.is_manager;
        this._recalculate();
    }

    _recalculate() {
        // --- Phần I: tiêu chí chung ---
        let generalScore = 0;
        let deptGeneral = 0;
        let filled = 0;
        let total = 0;
        for (const g of this.state.criteria_groups) {
            g.currentScore = 0;
            for (const c of g.criteria) {
                g.currentScore += c.selectedScore || 0;
                generalScore += c.selectedScore || 0;
                deptGeneral += c.deptScore || 0;
                total++;
                if (c.selectedScore > 0) filled++;
            }
        }
        this.state.totalGeneral = Math.round(generalScore * 10) / 10;
        this.state.totalDeptGeneral = Math.round(deptGeneral * 10) / 10;

        // --- Phần II: KQTHNV ---
        // Công thức: điểm KQTHNV = trung bình(pct_*) / 100 × taskMax
        // Non-manager: 3 trường; Manager: 6 trường
        const isManager = this.state.record && this.state.record.is_manager;
        const activeFields = this.state.task_fields.filter(f => !f.managerOnly || isManager);
        const pctSum = activeFields.reduce((sum, f) => sum + (parseFloat(f.value) || 0), 0);
        const pctAvg = activeFields.length > 0 ? pctSum / activeFields.length : 0;
        const taskScore = Math.round((pctAvg / 100 * (this.state.taskMax || 70)) * 10) / 10;

        this.state.totalTask = taskScore;
        // Total score uses dept score if any criteria has dept score (review phase),
        // otherwise self score.
        const useDept = deptGeneral > 0 && this.state.record && this.state.record.state !== 'draft';
        const finalGeneral = useDept ? deptGeneral : generalScore;
        this.state.totalScore = Math.round((finalGeneral + taskScore) * 10) / 10;

        total += activeFields.length;
        filled += activeFields.filter(f => f.value > 0).length;
        this.state.filledCount = filled;
        this.state.totalCriteria = total;

        const s = this.state.totalScore;
        if (s >= 90)      this.state.classification = 'excellent';
        else if (s >= 75) this.state.classification = 'good';
        else if (s >= 50) this.state.classification = 'fair';
        else              this.state.classification = 'poor';
    }

    get classificationDisplay() {
        const map = {
            excellent: { label: 'Hoàn thành xuất sắc', css: 'bv-rank-excellent' },
            good: { label: 'Hoàn thành tốt', css: 'bv-rank-good' },
            fair: { label: 'Hoàn thành nhiệm vụ', css: 'bv-rank-fair' },
            poor: { label: 'Không hoàn thành', css: 'bv-rank-poor' },
        };
        return map[this.state.classification] || { label: 'Chưa chấm', css: 'bv-rank-none' };
    }

    get progressPct() {
        if (!this.state.totalCriteria) return 0;
        return Math.round(this.state.filledCount / this.state.totalCriteria * 100);
    }

    get generalPct() {
        const max = this.state.generalMax || 30;
        return Math.min(100, Math.round(this.state.totalGeneral / max * 100));
    }

    get taskPct() {
        const max = this.state.taskMax || 70;
        return Math.min(100, Math.round(this.state.totalTask / max * 100));
    }

    get scoreDeg() {
        return Math.round(this.state.totalScore / 100 * 360);
    }

    get isReadonly() {
        if (!this.state.record) return true;
        // Employee can edit when draft. Dept manager can edit when state is submitted.
        return this.state.record.state !== 'draft' && !this.state.canEditDept;
    }

    get monthLabel() {
        const months = {
            '1': 'Tháng 1', '2': 'Tháng 2', '3': 'Tháng 3',
            '4': 'Tháng 4', '5': 'Tháng 5', '6': 'Tháng 6',
            '7': 'Tháng 7', '8': 'Tháng 8', '9': 'Tháng 9',
            '10': 'Tháng 10', '11': 'Tháng 11', '12': 'Tháng 12',
        };
        return this.state.record ? months[this.state.record.month] || '' : '';
    }

    async saveDraft() {
        if (!this.state.record || this.state.saving) return;
        this.state.saving = true;
        try {
            const lineWrites = [];
            for (const g of this.state.criteria_groups) {
                for (const c of g.criteria) {
                    const lineVals = {};
                    if (this.state.record.state === 'draft') {
                        lineVals.self_score = c.selectedScore || 0;
                    }
                    if (this.state.canEditDept) {
                        lineVals.dept_score = c.deptScore || 0;
                    }
                    if (Object.keys(lineVals).length > 0) {
                        lineWrites.push([1, c.lineId, lineVals]);
                    }
                }
            }
            const vals = {};
            if (lineWrites.length > 0) {
                vals.criteria_line_ids = lineWrites;
            }
            if (this.state.record.state === 'draft') {
                vals.is_manager = this.state.record.is_manager || false;
                for (const f of this.state.task_fields) {
                    vals[f.key] = parseFloat(f.value) || 0;
                }
            }
            if (Object.keys(vals).length === 0) {
                this.state.saving = false;
                return;
            }
            await this.orm.write('bv.monthly.evaluation', [this.evalId], vals);
            this.notification.add("Đã lưu thành công!", { type: "success", sticky: false });
        } catch (e) {
            this.notification.add("Lỗi khi lưu: " + (e.message || ''), { type: "danger" });
        }
        this.state.saving = false;
    }

    async deptApprove() {
        await this.saveDraft();
        try {
            await this.orm.call('bv.monthly.evaluation', 'action_dept_approve', [this.evalId]);
            this.notification.add("Đã duyệt và chuyển lên TCCB.", { type: "success" });
            await this.loadRecord();
        } catch (e) {
            this.notification.add("Lỗi: " + (e.message || ''), { type: "danger" });
        }
    }

    async submitForm() {
        await this.saveDraft();
        try {
            await this.orm.call('bv.monthly.evaluation', 'action_submit', [this.evalId]);
            this.notification.add("Phiếu đánh giá đã được gửi thành công!", { type: "success" });
            await this.loadRecord();
        } catch (e) {
            this.notification.add("Lỗi: " + (e.message || e.data?.message || ''), { type: "danger" });
        }
    }

    goBack() {
        this.action.doAction('bv_danh_gia.action_monthly_evaluation');
    }

    openStandardForm() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'bv.monthly.evaluation',
            res_id: this.evalId,
            view_mode: 'form',
            views: [[false, 'form']],
        });
    }
}

registry.category("actions").add("bv_danh_gia.evaluation_form_custom", EvaluationFormView);
