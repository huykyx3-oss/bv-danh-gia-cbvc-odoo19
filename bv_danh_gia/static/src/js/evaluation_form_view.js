/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
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
            totalGeneral: 0,
            totalTask: 0,
            totalScore: 0,
            classification: '',
            filledCount: 0,
            totalCriteria: 0,
        });

        onWillStart(async () => {
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
            'classification', 'strengths', 'weaknesses', 'authority_comment',
            'pct_quantity', 'pct_quality', 'pct_progress',
            'pct_field_result', 'pct_organization', 'pct_team_cohesion',
            'criteria_line_ids', 'display_name',
        ]);
        this.state.record = record;

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
        const fields = [
            { key: 'pct_quantity', label: 'a) Số lượng thực hiện chỉ tiêu, nhiệm vụ chuyên môn', maxPts: 15, value: r.pct_quantity },
            { key: 'pct_quality', label: 'b) Chất lượng kết quả thực hiện nhiệm vụ được giao', maxPts: 15, value: r.pct_quality },
            { key: 'pct_progress', label: 'c) Tiến độ thực hiện', maxPts: 10, value: r.pct_progress },
        ];
        if (r.is_manager) {
            fields.push(
                { key: 'pct_field_result', label: 'd) Kết quả hoạt động lĩnh vực phụ trách', maxPts: 10, value: r.pct_field_result },
                { key: 'pct_organization', label: 'đ) Khả năng tổ chức triển khai thực hiện', maxPts: 10, value: r.pct_organization },
                { key: 'pct_team_cohesion', label: 'e) Năng lực tập hợp đoàn kết', maxPts: 10, value: r.pct_team_cohesion },
            );
        }
        this.state.task_fields = fields;
    }

    get taskFieldOptions() {
        const taskOpts = {};
        for (const f of this.state.task_fields) {
            const opts = [];
            const maxPts = f.maxPts;
            if (maxPts === 15) {
                opts.push({ score: 15, label: 'Đạt ≥ 100% — Vượt yêu cầu' });
                opts.push({ score: 12, label: 'Đạt 90% – < 100%' });
                opts.push({ score: 10, label: 'Đạt 80% – < 90%' });
                opts.push({ score: 5, label: 'Đạt 70% – < 80%' });
                opts.push({ score: 0, label: 'Đạt < 70%' });
            } else if (maxPts === 10) {
                opts.push({ score: 10, label: 'Xuất sắc, 100% đúng/vượt tiến độ' });
                opts.push({ score: 8, label: 'Tốt, 90%+ đúng tiến độ' });
                opts.push({ score: 5, label: 'Đạt, có công việc chậm tiến độ' });
                opts.push({ score: 3, label: 'Hạn chế, chậm tiến độ kéo dài' });
                opts.push({ score: 0, label: 'Không hoàn thành' });
            }
            taskOpts[f.key] = opts;
        }
        return taskOpts;
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

    selectTaskScore(key, score) {
        if (this.state.record && this.state.record.state !== 'draft') return;
        for (const f of this.state.task_fields) {
            if (f.key === key) {
                f.value = score;
            }
        }
        this._recalculate();
    }

    _recalculate() {
        let generalScore = 0;
        let filled = 0;
        let total = 0;
        for (const g of this.state.criteria_groups) {
            g.currentScore = 0;
            for (const c of g.criteria) {
                g.currentScore += c.selectedScore || 0;
                generalScore += c.selectedScore || 0;
                total++;
                if (c.selectedScore > 0) filled++;
            }
        }
        this.state.totalGeneral = Math.round(generalScore * 10) / 10;

        let taskTotal = 0;
        let taskCount = 0;
        for (const f of this.state.task_fields) {
            taskTotal += f.value || 0;
            taskCount++;
            total++;
            if (f.value > 0) filled++;
        }
        this.state.totalTask = Math.round(taskTotal * 10) / 10;
        this.state.totalScore = Math.round((generalScore + taskTotal) * 10) / 10;
        this.state.filledCount = filled;
        this.state.totalCriteria = total;

        const s = this.state.totalScore;
        if (s >= 90) this.state.classification = 'excellent';
        else if (s >= 75) this.state.classification = 'good';
        else if (s >= 50) this.state.classification = 'fair';
        else this.state.classification = 'poor';
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
        return Math.round(this.state.totalGeneral / 30 * 100);
    }

    get taskPct() {
        return Math.round(this.state.totalTask / 70 * 100);
    }

    get scoreDeg() {
        return Math.round(this.state.totalScore / 100 * 360);
    }

    get isReadonly() {
        return !this.state.record || this.state.record.state !== 'draft';
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
                    lineWrites.push([1, c.lineId, { self_score: c.selectedScore || 0 }]);
                }
            }
            const vals = { criteria_line_ids: lineWrites };
            for (const f of this.state.task_fields) {
                vals[f.key] = f.value || 0;
            }
            await this.orm.write('bv.monthly.evaluation', [this.evalId], vals);
            this.notification.add("Đã lưu nháp thành công!", { type: "success", sticky: false });
        } catch (e) {
            this.notification.add("Lỗi khi lưu: " + (e.message || ''), { type: "danger" });
        }
        this.state.saving = false;
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
