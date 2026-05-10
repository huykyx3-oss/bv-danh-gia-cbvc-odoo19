from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import base64
import datetime
import logging
_logger = logging.getLogger(__name__)

MONTHS = [
    ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'),
    ('4', 'Tháng 4'), ('5', 'Tháng 5'), ('6', 'Tháng 6'),
    ('7', 'Tháng 7'), ('8', 'Tháng 8'), ('9', 'Tháng 9'),
    ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12'),
]

CLASSIFICATION = [
    ('excellent', 'Hoàn thành xuất sắc nhiệm vụ'),
    ('good', 'Hoàn thành tốt nhiệm vụ'),
    ('fair', 'Hoàn thành nhiệm vụ'),
    ('poor', 'Không hoàn thành nhiệm vụ'),
]

CONTRACT_TYPE = [
    ('labor', 'Hợp đồng lao động'),
    ('public_employee', 'Viên chức'),
    ('civil_servant', 'Công chức'),
]


class MonthlyEvaluation(models.Model):
    _name = 'bv.monthly.evaluation'
    _description = 'Phiếu theo dõi, đánh giá CBVC hằng tháng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc, month desc, employee_id'
    _rec_name = 'display_name'

    employee_id = fields.Many2one(
        'hr.employee', string='Họ và tên', required=True,
        tracking=True, default=lambda self: self.env.user.employee_id)
    department_id = fields.Many2one(
        'hr.department', string='Đơn vị công tác',
        related='employee_id.department_id', store=True, readonly=True)
    job_id = fields.Many2one(
        'hr.job', string='Chức vụ, chức danh',
        related='employee_id.job_id', store=True, readonly=True)
    month = fields.Selection(MONTHS, string='Tháng', required=True,
                             default=lambda self: str(datetime.date.today().month),
                             tracking=True)
    year = fields.Integer(string='Năm', required=True,
                          default=lambda self: datetime.date.today().year,
                          tracking=True)
    quarter = fields.Integer(string='Quý', compute='_compute_quarter', store=True)

    contract_type = fields.Selection(
        CONTRACT_TYPE,
        string='Loại hợp đồng',
        tracking=True,
        help='Phân loại theo hình thức làm việc (lưu để báo cáo, thống kê sau này)',
    )

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Đã gửi'),
        ('dept_approved', 'Trưởng khoa duyệt'),
        ('hr_reviewed', 'TCCB xét duyệt'),
        ('approved', 'BGĐ phê duyệt'),
        ('rejected', 'Trả lại'),
    ], string='Trạng thái', default='draft', tracking=True, required=True)

    is_manager = fields.Boolean(
        string='Giữ chức vụ lãnh đạo, quản lý',
        help='Viên chức giữ chức vụ lãnh đạo, quản lý sẽ áp dụng công thức tính điểm khác')
    can_edit_dept_score = fields.Boolean(
        string='Có thể chấm điểm trưởng khoa',
        compute='_compute_can_edit_dept_score',
        help='Đúng khi user hiện tại là trưởng khoa/phòng và phiếu đang chờ duyệt cấp khoa')
    template_id = fields.Many2one(
        'bv.evaluation.template', string='Biểu mẫu đánh giá',
        domain="[('active', '=', True), ('template_type', '=', 'monthly')]",
        help='Biểu mẫu đánh giá do TCCB tạo')

    # --- Nhãn tiêu chí KQTHNV (lấy từ biểu mẫu, TCCB chỉnh) ---
    label_pct_a = fields.Char(related='template_id.label_pct_a', readonly=True)
    label_pct_b = fields.Char(related='template_id.label_pct_b', readonly=True)
    label_pct_c = fields.Char(related='template_id.label_pct_c', readonly=True)
    label_pct_d = fields.Char(related='template_id.label_pct_d', readonly=True)
    label_pct_dd = fields.Char(related='template_id.label_pct_dd', readonly=True)
    label_pct_e = fields.Char(related='template_id.label_pct_e', readonly=True)

    # --- Tiêu chí chung (30 điểm) ---
    criteria_line_ids = fields.One2many(
        'bv.evaluation.criteria.line', 'evaluation_id',
        string='Tiêu chí chung')
    general_score = fields.Float(
        string='Điểm tiêu chí chung', compute='_compute_general_score',
        store=True, tracking=True)

    # --- Tiêu chí kết quả nhiệm vụ (70 điểm) — NV tự chấm ---
    task_line_ids = fields.One2many(
        'bv.evaluation.task.line', 'evaluation_id',
        string='Nhiệm vụ được giao')
    pct_quantity = fields.Float(string='a - % Số lượng KQTHNV', tracking=True)
    pct_quality = fields.Float(string='b - % Chất lượng KQTHNV', tracking=True)
    pct_progress = fields.Float(string='c - % Tiến độ KQTHNV', tracking=True)
    pct_field_result = fields.Float(
        string='d - % Kết quả lĩnh vực được giao',
        help='Chỉ áp dụng cho viên chức giữ chức vụ lãnh đạo, quản lý')
    pct_organization = fields.Float(
        string='đ - % Khả năng tổ chức triển khai',
        help='Chỉ áp dụng cho viên chức giữ chức vụ lãnh đạo, quản lý')
    pct_team_cohesion = fields.Float(
        string='e - % Năng lực tập hợp, đoàn kết',
        help='Chỉ áp dụng cho viên chức giữ chức vụ lãnh đạo, quản lý')

    # --- Điểm trưởng khoa/phòng chấm KQTHNV ---
    dept_pct_quantity = fields.Float(string='a - % Số lượng (TP chấm)', tracking=True)
    dept_pct_quality = fields.Float(string='b - % Chất lượng (TP chấm)', tracking=True)
    dept_pct_progress = fields.Float(string='c - % Tiến độ (TP chấm)', tracking=True)
    dept_pct_field_result = fields.Float(
        string='d - % Kết quả lĩnh vực (TP chấm)',
        help='Chỉ áp dụng cho viên chức giữ chức vụ lãnh đạo, quản lý')
    dept_pct_organization = fields.Float(
        string='đ - % Tổ chức triển khai (TP chấm)',
        help='Chỉ áp dụng cho viên chức giữ chức vụ lãnh đạo, quản lý')
    dept_pct_team_cohesion = fields.Float(
        string='e - % Đoàn kết (TP chấm)',
        help='Chỉ áp dụng cho viên chức giữ chức vụ lãnh đạo, quản lý')

    # --- Tài liệu minh chứng KQTHNV (PDF) ---
    evidence_quantity = fields.Binary(
        string='Minh chứng % Số lượng', attachment=True)
    evidence_quantity_name = fields.Char(string='Tên file minh chứng số lượng')
    evidence_quality = fields.Binary(
        string='Minh chứng % Chất lượng', attachment=True)
    evidence_quality_name = fields.Char(string='Tên file minh chứng chất lượng')
    evidence_progress = fields.Binary(
        string='Minh chứng % Tiến độ', attachment=True)
    evidence_progress_name = fields.Char(string='Tên file minh chứng tiến độ')
    evidence_field_result = fields.Binary(
        string='Minh chứng kết quả lĩnh vực', attachment=True)
    evidence_field_result_name = fields.Char(string='Tên file minh chứng kết quả lĩnh vực')
    evidence_organization = fields.Binary(
        string='Minh chứng tổ chức triển khai', attachment=True)
    evidence_organization_name = fields.Char(string='Tên file minh chứng tổ chức')
    evidence_team_cohesion = fields.Binary(
        string='Minh chứng đoàn kết', attachment=True)
    evidence_team_cohesion_name = fields.Char(string='Tên file minh chứng đoàn kết')

    task_score = fields.Float(
        string='Điểm tiêu chí KQTHNV', compute='_compute_task_score',
        store=True, tracking=True)

    # --- Trọng số điểm (lấy từ biểu mẫu, mặc định 30/70) ---
    general_score_max = fields.Float(
        string='Điểm tối đa tiêu chí chung',
        compute='_compute_score_maxes', store=True,
        help='Lấy từ biểu mẫu đánh giá; mặc định 30 nếu không có biểu mẫu')
    task_score_max = fields.Float(
        string='Điểm tối đa KQTHNV',
        compute='_compute_score_maxes', store=True,
        help='Lấy từ biểu mẫu đánh giá; mặc định 70 nếu không có biểu mẫu')

    # --- Tổng điểm (workflow) ---
    total_score = fields.Float(
        string='Tổng điểm', compute='_compute_total_score',
        store=True, tracking=True)
    classification = fields.Selection(
        CLASSIFICATION, string='Mức xếp loại',
        compute='_compute_classification', store=True, tracking=True)

    # --- Điểm TK/TP chấm (độc lập với NV) ---
    general_score_nv = fields.Float(
        string='Điểm Phần I (NV tự chấm)',
        compute='_compute_nv_tp_scores', store=True)
    general_score_tp = fields.Float(
        string='Điểm Phần I (TK/TP chấm)',
        compute='_compute_nv_tp_scores', store=True)
    task_score_nv = fields.Float(
        string='Điểm KQTHNV (NV tự chấm)',
        compute='_compute_nv_tp_scores', store=True)
    task_score_tp = fields.Float(
        string='Điểm KQTHNV (TK/TP chấm)',
        compute='_compute_nv_tp_scores', store=True)
    total_score_nv = fields.Float(
        string='Tổng điểm (NV tự chấm)',
        compute='_compute_nv_tp_scores', store=True)
    total_score_tp = fields.Float(
        string='Tổng điểm (TK/TP chấm)',
        compute='_compute_nv_tp_scores', store=True)
    classification_tp = fields.Selection(
        CLASSIFICATION, string='Xếp loại (TK/TP chấm)',
        compute='_compute_nv_tp_scores', store=True)

    # --- Nhận xét ---
    strengths = fields.Text(string='Ưu điểm')
    weaknesses = fields.Text(string='Hạn chế, khuyết điểm')
    authority_comment = fields.Text(string='Ý kiến nhận xét của cấp có thẩm quyền')

    display_name = fields.Char(compute='_compute_display_name', store=True)

    _unique_employee_month_year = models.Constraint(
        'UNIQUE(employee_id, month, year)',
        'Mỗi nhân viên chỉ có một phiếu đánh giá trong một tháng!'
    )

    @api.depends('employee_id', 'month', 'year')
    def _compute_display_name(self):
        for rec in self:
            month_label = dict(MONTHS).get(rec.month, '')
            emp_name = rec.employee_id.name or ''
            rec.display_name = f'{emp_name} - {month_label}/{rec.year}'

    @api.depends('month')
    def _compute_quarter(self):
        for rec in self:
            m = int(rec.month) if rec.month else 1
            rec.quarter = (m - 1) // 3 + 1

    @api.depends('state')
    def _compute_can_edit_dept_score(self):
        is_dept_mgr = self.env.user.has_group('bv_danh_gia.group_evaluation_dept_manager')
        for rec in self:
            result = rec.state == 'submitted' and is_dept_mgr
            # region agent log H-B
            _logger.info('BV_DEBUG[H-B] rec=%s state=%s is_dept_mgr=%s can_edit=%s uid=%s',
                         rec.id, rec.state, is_dept_mgr, result, self.env.uid)
            # endregion
            rec.can_edit_dept_score = result

    @api.depends('criteria_line_ids.final_score')
    def _compute_general_score(self):
        for rec in self:
            rec.general_score = sum(rec.criteria_line_ids.mapped('final_score'))

    @api.depends(
        'is_manager', 'state',
        'pct_quantity', 'pct_quality', 'pct_progress',
        'pct_field_result', 'pct_organization', 'pct_team_cohesion',
        'dept_pct_quantity', 'dept_pct_quality', 'dept_pct_progress',
        'dept_pct_field_result', 'dept_pct_organization', 'dept_pct_team_cohesion',
        'task_score_max')
    def _compute_task_score(self):
        for rec in self:
            max_pts = rec.task_score_max or 70.0
            # Sau khi trưởng phòng duyệt, ưu tiên dùng điểm TP nếu đã nhập
            use_dept = (
                rec.state in ('dept_approved', 'hr_reviewed', 'approved')
                and (
                    rec.dept_pct_quantity or rec.dept_pct_quality or rec.dept_pct_progress
                    or rec.dept_pct_field_result or rec.dept_pct_organization
                    or rec.dept_pct_team_cohesion
                )
            )
            if use_dept:
                if rec.is_manager:
                    total_pct = (
                        rec.dept_pct_quantity + rec.dept_pct_quality + rec.dept_pct_progress
                        + rec.dept_pct_field_result + rec.dept_pct_organization
                        + rec.dept_pct_team_cohesion
                    )
                    rec.task_score = (total_pct / 6.0) * max_pts / 100.0
                else:
                    total_pct = (
                        rec.dept_pct_quantity + rec.dept_pct_quality + rec.dept_pct_progress
                    )
                    rec.task_score = (total_pct / 3.0) * max_pts / 100.0
            else:
                if rec.is_manager:
                    total_pct = (
                        rec.pct_quantity + rec.pct_quality + rec.pct_progress
                        + rec.pct_field_result + rec.pct_organization + rec.pct_team_cohesion
                    )
                    rec.task_score = (total_pct / 6.0) * max_pts / 100.0
                else:
                    total_pct = rec.pct_quantity + rec.pct_quality + rec.pct_progress
                    rec.task_score = (total_pct / 3.0) * max_pts / 100.0

    @api.depends('template_id', 'template_id.task_score_weight',
                 'template_id.total_general_score')
    def _compute_score_maxes(self):
        for rec in self:
            if rec.template_id:
                rec.task_score_max = rec.template_id.task_score_weight or 70.0
                # Prefer the template's explicit general total, else 100 - task
                rec.general_score_max = (
                    rec.template_id.total_general_score
                    or (100.0 - rec.task_score_max)
                )
            else:
                rec.general_score_max = 30.0
                rec.task_score_max = 70.0

    @api.depends('general_score', 'task_score')
    def _compute_total_score(self):
        for rec in self:
            rec.total_score = rec.general_score + rec.task_score

    @api.depends('total_score')
    def _compute_classification(self):
        for rec in self:
            score = rec.total_score
            if score >= 90:
                rec.classification = 'excellent'
            elif score >= 70:
                rec.classification = 'good'
            elif score >= 50:
                rec.classification = 'fair'
            else:
                rec.classification = 'poor'

    @api.depends(
        'criteria_line_ids.self_score', 'criteria_line_ids.dept_score',
        'is_manager', 'task_score_max',
        'pct_quantity', 'pct_quality', 'pct_progress',
        'pct_field_result', 'pct_organization', 'pct_team_cohesion',
        'dept_pct_quantity', 'dept_pct_quality', 'dept_pct_progress',
        'dept_pct_field_result', 'dept_pct_organization', 'dept_pct_team_cohesion',
    )
    def _compute_nv_tp_scores(self):
        for rec in self:
            max_pts = rec.task_score_max or 70.0

            # Phần I
            rec.general_score_nv = sum(rec.criteria_line_ids.mapped('self_score'))
            rec.general_score_tp = sum(rec.criteria_line_ids.mapped('dept_score'))

            # Phần II — NV
            if rec.is_manager:
                nv_pct = (rec.pct_quantity + rec.pct_quality + rec.pct_progress
                          + rec.pct_field_result + rec.pct_organization + rec.pct_team_cohesion)
                rec.task_score_nv = (nv_pct / 6.0) * max_pts / 100.0
            else:
                nv_pct = rec.pct_quantity + rec.pct_quality + rec.pct_progress
                rec.task_score_nv = (nv_pct / 3.0) * max_pts / 100.0

            # Phần II — TK/TP (luôn từ dept_pct_*, không phụ thuộc NV)
            if rec.is_manager:
                tp_pct = (rec.dept_pct_quantity + rec.dept_pct_quality + rec.dept_pct_progress
                          + rec.dept_pct_field_result + rec.dept_pct_organization
                          + rec.dept_pct_team_cohesion)
                rec.task_score_tp = (tp_pct / 6.0) * max_pts / 100.0
            else:
                tp_pct = rec.dept_pct_quantity + rec.dept_pct_quality + rec.dept_pct_progress
                rec.task_score_tp = (tp_pct / 3.0) * max_pts / 100.0

            # Tổng
            rec.total_score_nv = rec.general_score_nv + rec.task_score_nv
            rec.total_score_tp = rec.general_score_tp + rec.task_score_tp

            # Xếp loại TK/TP
            score_tp = rec.total_score_tp
            if score_tp >= 90:
                rec.classification_tp = 'excellent'
            elif score_tp >= 70:
                rec.classification_tp = 'good'
            elif score_tp >= 50:
                rec.classification_tp = 'fair'
            else:
                rec.classification_tp = 'poor'

    def action_copy_nv_scores_to_tp(self):
        """Sao chép điểm NV → TK/TP để dùng làm điểm bắt đầu."""
        self.ensure_one()
        if not self.can_edit_dept_score:
            raise UserError(
                'Chỉ trưởng khoa/phòng mới có thể sao chép điểm khi phiếu đang ở trạng thái "Đã gửi".'
            )
        # Phần I: copy self_score → dept_score cho từng dòng tiêu chí
        for line in self.criteria_line_ids:
            line.dept_score = line.self_score
        # Phần II: copy pct_* → dept_pct_*
        self.dept_pct_quantity = self.pct_quantity
        self.dept_pct_quality = self.pct_quality
        self.dept_pct_progress = self.pct_progress
        self.dept_pct_field_result = self.pct_field_result
        self.dept_pct_organization = self.pct_organization
        self.dept_pct_team_cohesion = self.pct_team_cohesion
        return {'type': 'ir.actions.act_window_close'}

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """When employee selects a template, load its criteria immediately."""
        self.criteria_line_ids = [(5, 0, 0)]
        if not self.template_id:
            return
        tmpl = self.template_id
        lines = tmpl.criteria_ids.filtered(lambda c: c.criteria_id).sorted('sequence')
        if lines:
            self.criteria_line_ids = [
                (0, 0, {'criteria_id': tc.criteria_id.id})
                for tc in lines
            ]
        else:
            # Biểu mẫu chưa gắn tiêu chí hợp lệ — dùng danh mục toàn hệ thống
            criteria = self.env['bv.evaluation.criteria'].search([
                ('category', '=', 'general'),
                ('is_parent', '=', False),
                ('active', '=', True),
            ], order='sequence')
            self.criteria_line_ids = [(0, 0, {'criteria_id': c.id}) for c in criteria]

    @api.onchange('employee_id', 'month', 'year')
    def _onchange_populate_criteria(self):
        """Fallback: when no template selected, populate from global master criteria."""
        if not self.employee_id or not self.month or not self.year:
            return
        if self.criteria_line_ids or self.template_id:
            return  # Already populated or will be handled by template onchange
        criteria = self.env['bv.evaluation.criteria'].search([
            ('category', '=', 'general'),
            ('is_parent', '=', False),
            ('active', '=', True),
        ], order='sequence')
        self.criteria_line_ids = [(0, 0, {'criteria_id': c.id}) for c in criteria]

    def _populate_criteria_lines(self):
        """Auto-populate criteria lines.
        Priority: template criteria (chỉ dòng có criteria_id) → danh mục toàn hệ thống."""
        CriteriaLine = self.env['bv.evaluation.criteria.line']
        for rec in self:
            if rec.template_id and rec.template_id.criteria_ids.filtered(lambda c: c.criteria_id):
                self._populate_from_template(rec, CriteriaLine)
            else:
                self._populate_from_global_master(rec, CriteriaLine)

    def _populate_from_global_master(self, rec, CriteriaLine):
        criteria = self.env['bv.evaluation.criteria'].search([
            ('category', '=', 'general'),
            ('is_parent', '=', False),
            ('active', '=', True),
        ])
        existing = rec.criteria_line_ids.mapped('criteria_id')
        for c in criteria:
            if c not in existing:
                CriteriaLine.create({'evaluation_id': rec.id, 'criteria_id': c.id})

    def _populate_from_template(self, rec, CriteriaLine):
        """Create criteria lines from template — each row already references master."""
        existing = rec.criteria_line_ids.mapped('criteria_id')
        for tc in rec.template_id.criteria_ids.filtered(lambda c: c.criteria_id).sorted('sequence'):
            if tc.criteria_id in existing:
                continue
            CriteriaLine.create({
                'evaluation_id': rec.id,
                'criteria_id': tc.criteria_id.id,
            })

    _EVIDENCE_BIN_NAME_PAIRS = (
        ('evidence_quantity', 'evidence_quantity_name'),
        ('evidence_quality', 'evidence_quality_name'),
        ('evidence_progress', 'evidence_progress_name'),
        ('evidence_field_result', 'evidence_field_result_name'),
        ('evidence_organization', 'evidence_organization_name'),
        ('evidence_team_cohesion', 'evidence_team_cohesion_name'),
    )

    def _fill_evidence_pdf_names(self, vals):
        """Gán tên file mặc định khi có binary nhưng client không gửi *_name (file.name rỗng)."""
        if not vals:
            return vals
        vals = dict(vals)
        for fbin, fname in self._EVIDENCE_BIN_NAME_PAIRS:
            if fbin not in vals:
                continue
            if vals.get(fbin) and not (vals.get(fname) or '').strip():
                vals[fname] = 'minh-chung.pdf'
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._fill_evidence_pdf_names(v) for v in vals_list]
        records = super().create(vals_list)
        records.filtered(lambda r: not r.criteria_line_ids)._populate_criteria_lines()
        return records

    def write(self, vals):
        vals = self._fill_evidence_pdf_names(vals)
        return super().write(vals)

    @api.constrains('pct_quantity', 'pct_quality', 'pct_progress',
                     'pct_field_result', 'pct_organization', 'pct_team_cohesion')
    def _check_pct_range(self):
        for rec in self:
            fields_check = [
                ('pct_quantity', 'a - % Số lượng'),
                ('pct_quality', 'b - % Chất lượng'),
                ('pct_progress', 'c - % Tiến độ'),
            ]
            if rec.is_manager:
                fields_check += [
                    ('pct_field_result', 'd - % Kết quả lĩnh vực'),
                    ('pct_organization', 'đ - % Khả năng tổ chức'),
                    ('pct_team_cohesion', 'e - % Năng lực đoàn kết'),
                ]
            for fname, label in fields_check:
                val = getattr(rec, fname)
                if val < 0 or val > 100:
                    raise ValidationError(f'{label} phải từ 0% đến 100%')

    @api.constrains(
        'evidence_quantity', 'evidence_quantity_name',
        'evidence_quality', 'evidence_quality_name',
        'evidence_progress', 'evidence_progress_name',
        'evidence_field_result', 'evidence_field_result_name',
        'evidence_organization', 'evidence_organization_name',
        'evidence_team_cohesion', 'evidence_team_cohesion_name',
    )
    def _check_evidence_pdf(self):
        pairs = [
            ('evidence_quantity', 'evidence_quantity_name', 'a – Số lượng'),
            ('evidence_quality', 'evidence_quality_name', 'b – Chất lượng'),
            ('evidence_progress', 'evidence_progress_name', 'c – Tiến độ'),
            ('evidence_field_result', 'evidence_field_result_name', 'd – Kết quả lĩnh vực'),
            ('evidence_organization', 'evidence_organization_name', 'đ – Tổ chức triển khai'),
            ('evidence_team_cohesion', 'evidence_team_cohesion_name', 'e – Đoàn kết'),
        ]
        for rec in self:
            for fbin, fname, label in pairs:
                data = getattr(rec, fbin)
                name = (getattr(rec, fname) or '').strip()
                if not data:
                    continue
                try:
                    raw = base64.b64decode(data)
                except Exception:
                    raise ValidationError(
                        f'Minh chứng "{label}": không đọc được dữ liệu file (Base64).'
                    ) from None
                if not raw.startswith(b'%PDF'):
                    raise ValidationError(
                        f'Minh chứng "{label}": nội dung file không phải PDF hợp lệ '
                        '(thiếu tiêu đề %PDF).'
                    )
                if name and not name.lower().endswith('.pdf'):
                    raise ValidationError(
                        f'Minh chứng "{label}": chỉ chấp nhận file PDF (.pdf).\n'
                        f'File đang chọn: "{name}".\n'
                        'Vui lòng chọn lại file có định dạng PDF.'
                    )

    @api.constrains('dept_pct_quantity', 'dept_pct_quality', 'dept_pct_progress',
                     'dept_pct_field_result', 'dept_pct_organization', 'dept_pct_team_cohesion')
    def _check_dept_pct_range(self):
        for rec in self:
            fields_check = [
                ('dept_pct_quantity', 'a - % Số lượng (TP chấm)'),
                ('dept_pct_quality', 'b - % Chất lượng (TP chấm)'),
                ('dept_pct_progress', 'c - % Tiến độ (TP chấm)'),
            ]
            if rec.is_manager:
                fields_check += [
                    ('dept_pct_field_result', 'd - % Kết quả lĩnh vực (TP chấm)'),
                    ('dept_pct_organization', 'đ - % Tổ chức triển khai (TP chấm)'),
                    ('dept_pct_team_cohesion', 'e - % Đoàn kết (TP chấm)'),
                ]
            for fname, label in fields_check:
                val = getattr(rec, fname)
                if val < 0 or val > 100:
                    raise ValidationError(f'{label} phải từ 0% đến 100%')

    # --- Config helper ---
    def _get_config(self):
        return self.env['bv.evaluation.config'].get_config(
            year=self.year if isinstance(self.year, int) else None)

    def _send_notification(self, user, title, message, notif_type='info'):
        """Send sticky notification via bus and mail activity."""
        self.env['bus.bus']._sendone(
            user.partner_id, 'bv_danh_gia/notification', {
                'title': title,
                'message': message,
                'type': notif_type,
            })

    def _check_and_warn_ratio(self):
        """Check ratio after approval and warn TCCB if exceeded."""
        config = self._get_config()
        if not config.auto_warn_ratio:
            return

        for rec in self:
            if rec.classification != 'excellent':
                continue

            dept_evals = self.search([
                ('department_id', '=', rec.department_id.id),
                ('year', '=', rec.year),
                ('month', '=', rec.month),
                ('state', 'in', ['dept_approved', 'hr_reviewed', 'approved']),
            ])
            excellent_count = len(dept_evals.filtered(lambda e: e.classification == 'excellent'))
            good_count = len(dept_evals.filtered(lambda e: e.classification == 'good'))

            if good_count > 0:
                ratio = excellent_count * 100.0 / good_count
                max_ratio = config.max_excellent_ratio

                if ratio > max_ratio:
                    hr_users = self.env.ref('bv_danh_gia.group_evaluation_hr').users
                    for hr_user in hr_users:
                        self._send_notification(
                            hr_user,
                            '⚠ Cảnh báo tỷ lệ xếp loại',
                            f'Khoa/Phòng "{rec.department_id.name}" - '
                            f'Tháng {rec.month}/{rec.year}: '
                            f'Tỷ lệ Xuất sắc/Tốt = {ratio:.1f}% '
                            f'(vượt giới hạn {max_ratio}%)',
                            'warning')

    def action_open_custom_form(self):
        """Open the custom evaluation form view.

        Self-heals before opening:
        1. Drops any criteria_line records with NULL criteria_id (orphans
           from older module versions or partial saves).
        2. Populates lines from template / global catalog if currently empty.
        """
        self.ensure_one()
        bad_lines = self.criteria_line_ids.filtered(lambda l: not l.criteria_id)
        if bad_lines:
            bad_lines.sudo().unlink()
        if not self.criteria_line_ids:
            self._populate_criteria_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'bv_danh_gia.evaluation_form_custom',
            'name': f'Phiếu đánh giá - {self.display_name}',
            'context': {'eval_id': self.id, 'active_id': self.id},
        }

    # --- Export actions ---
    def action_export_docx(self):
        """Open URL to download DOCX file."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/bv_danh_gia/export_mau01/{self.id}',
            'target': 'new',
        }

    # --- Workflow helpers ---
    def _get_workflow_steps(self):
        """Return the effective workflow_steps for this record.
        Template setting takes priority over global config."""
        self.ensure_one()
        if self.template_id and self.template_id.workflow_steps:
            return self.template_id.workflow_steps
        config = self._get_config()
        # Derive from global config flags
        if config.auto_approve_dept and config.auto_approve_hr and config.auto_approve_director:
            return 'auto'
        if config.auto_approve_dept and config.auto_approve_hr:
            return 'skip_dept'
        if config.auto_approve_dept:
            return 'skip_dept'
        return 'full'

    def _advance_workflow_after_submit(self, config):
        """Skip states based on workflow_steps after employee submits."""
        self.ensure_one()
        steps = self._get_workflow_steps()
        if steps in ('skip_dept', 'minimal', 'auto'):
            self.state = 'dept_approved'
        if steps in ('skip_hr', 'minimal', 'auto') and self.state == 'dept_approved':
            self.state = 'hr_reviewed'
        if steps in ('minimal', 'auto') and self.state == 'hr_reviewed':
            self.state = 'approved'
            self._check_and_warn_ratio()

    def _notify_employee_approved(self):
        """Gửi thông báo NV khi phiếu chuyển sang approved (nếu bật trong cấu hình)."""
        self.ensure_one()
        config = self._get_config()
        if config.notify_on_approve and self.employee_id.user_id:
            self._send_notification(
                self.employee_id.user_id,
                'Phiếu đánh giá đã được phê duyệt',
                f'Phiếu đánh giá Tháng {self.month}/{self.year} của bạn '
                f'đã được phê duyệt. Tổng điểm: {self.total_score:.1f}',
                'success')

    def _advance_workflow_after_dept(self, config):
        """Skip HR/Director states after dept manager approves."""
        self.ensure_one()
        steps = self._get_workflow_steps()
        if steps == 'nv_tp':
            self.state = 'approved'
            self._check_and_warn_ratio()
            self._notify_employee_approved()
            return
        if steps in ('skip_hr',) and self.state == 'dept_approved':
            self.state = 'hr_reviewed'
        if (config.auto_approve_director or steps in ('minimal', 'auto')) \
                and self.state == 'hr_reviewed':
            self.state = 'approved'
            self._check_and_warn_ratio()

    # --- Workflow actions ---
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Chỉ có thể gửi phiếu ở trạng thái Nháp.')
            if not rec.contract_type:
                raise UserError(
                    'Vui lòng chọn loại hợp đồng (Hợp đồng lao động / Viên chức / Công chức) '
                    'trong phần Thông tin kỳ đánh giá trước khi gửi.'
                )
            if rec.total_score <= 0:
                raise UserError('Vui lòng chấm điểm trước khi gửi.')
            rec.state = 'submitted'

            config = rec._get_config()

            # Notify department manager (only if dept step is active)
            steps = rec._get_workflow_steps()
            if config.notify_on_submit and steps not in ('skip_dept', 'minimal', 'auto'):
                dept_manager = rec.department_id.manager_id
                if dept_manager and dept_manager.user_id:
                    rec._send_notification(
                        dept_manager.user_id,
                        'Phiếu đánh giá mới cần duyệt',
                        f'{rec.employee_id.name} đã gửi phiếu đánh giá '
                        f'Tháng {rec.month}/{rec.year} ({rec.total_score:.1f} điểm)')

            rec._advance_workflow_after_submit(config)

    def action_dept_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError('Chỉ có thể duyệt phiếu đã gửi.')
            rec.state = 'dept_approved'
            rec._advance_workflow_after_dept(rec._get_config())

    def action_hr_review(self):
        for rec in self:
            if rec.state != 'dept_approved':
                raise UserError('Chỉ có thể xét duyệt phiếu đã được trưởng khoa duyệt.')
            steps = rec._get_workflow_steps()
            if steps == 'nv_tp_tccb':
                rec.state = 'approved'
                rec._check_and_warn_ratio()
                rec._notify_employee_approved()
                continue
            rec.state = 'hr_reviewed'

            config = rec._get_config()
            if config.auto_approve_director:
                rec.state = 'approved'
                rec._check_and_warn_ratio()

    def action_approve(self):
        for rec in self:
            if rec.state != 'hr_reviewed':
                raise UserError('Chỉ có thể phê duyệt phiếu đã qua TCCB.')
            rec.state = 'approved'

            rec._notify_employee_approved()

            rec._check_and_warn_ratio()

    def action_reject(self):
        for rec in self:
            if rec.state == 'draft':
                raise UserError('Không thể trả lại phiếu ở trạng thái Nháp.')
            rec.state = 'rejected'

            config = rec._get_config()
            if config.notify_on_reject and rec.employee_id.user_id:
                rec._send_notification(
                    rec.employee_id.user_id,
                    'Phiếu đánh giá bị trả lại',
                    f'Phiếu đánh giá Tháng {rec.month}/{rec.year} của bạn '
                    f'đã bị trả lại. Vui lòng kiểm tra và chỉnh sửa.',
                    'danger')

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('rejected', 'submitted'):
                raise UserError('Chỉ có thể đặt lại phiếu bị trả lại hoặc đã gửi.')
            rec.state = 'draft'

    # --- Cron jobs ---
    @api.model
    def _cron_send_monthly_reminder(self):
        """Send activity reminders to employees who haven't created this month's evaluation."""
        today = datetime.date.today()
        current_month = str(today.month)
        current_year = today.year
        config = self.env['bv.evaluation.config'].get_config(year=current_year)
        deadline_day = config.monthly_submit_deadline_day or 10

        employees = self.env['hr.employee'].search([
            ('user_id', '!=', False),
            ('active', '=', True),
        ])
        existing = self.search([
            ('month', '=', current_month),
            ('year', '=', current_year),
        ]).mapped('employee_id')

        missing = employees - existing
        for emp in missing:
            if emp.user_id:
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'note': f'Vui lòng tạo phiếu tự đánh giá Tháng {current_month}/{current_year}. '
                            f'Hạn chót: ngày {deadline_day} tháng sau.',
                    'user_id': emp.user_id.id,
                    'res_model_id': self.env['ir.model']._get_id('bv.monthly.evaluation'),
                    'res_id': emp.id,
                    'date_deadline': today + datetime.timedelta(days=deadline_day),
                    'summary': f'Tự đánh giá Tháng {current_month}/{current_year}',
                })

                # Also send bus notification
                self.env['bus.bus']._sendone(
                    emp.user_id.partner_id, 'bv_danh_gia/notification', {
                        'title': 'Nhắc nhở tự đánh giá',
                        'message': f'Bạn chưa tạo phiếu tự đánh giá '
                                   f'Tháng {current_month}/{current_year}. '
                                   f'Hạn chót: ngày {deadline_day} tháng sau.',
                        'type': 'warning',
                    })

    @api.model
    def _cron_send_quarterly_deadline_reminder(self):
        """Remind employees about quarterly deadline."""
        today = datetime.date.today()
        current_month = today.month
        current_year = today.year
        quarter_end_months = {3, 6, 9, 12}

        if current_month not in quarter_end_months:
            return

        config = self.env['bv.evaluation.config'].get_config(year=current_year)
        reminder_days = config.reminder_days_before or 5
        deadline_day = config.quarterly_deadline_day or 10

        if today.day > reminder_days:
            return

        quarter = (current_month - 1) // 3 + 1
        months_in_quarter = [str(m) for m in range((quarter - 1) * 3 + 1, quarter * 3 + 1)]

        # Warn about draft evaluations
        draft_evals = self.search([
            ('month', 'in', months_in_quarter),
            ('year', '=', current_year),
            ('state', '=', 'draft'),
        ])

        for ev in draft_evals:
            if ev.employee_id.user_id:
                ev.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=ev.employee_id.user_id.id,
                    note=f'Phiếu đánh giá Tháng {ev.month}/{ev.year} chưa được gửi. '
                         f'Deadline tổng hợp quý: ngày {deadline_day}/{current_month}/{current_year}.',
                    date_deadline=datetime.date(current_year, current_month, deadline_day),
                    summary=f'Deadline Quý {quarter}: gửi phiếu đánh giá',
                )

        # Warn about pending approvals
        pending_evals = self.search([
            ('month', 'in', months_in_quarter),
            ('year', '=', current_year),
            ('state', 'in', ['submitted', 'dept_approved']),
        ])

        if pending_evals:
            hr_users = self.env.ref('bv_danh_gia.group_evaluation_hr').users
            for hr_user in hr_users:
                self.env['bus.bus']._sendone(
                    hr_user.partner_id, 'bv_danh_gia/notification', {
                        'title': f'⏰ Deadline Quý {quarter} sắp đến',
                        'message': f'Còn {len(pending_evals)} phiếu đánh giá chưa duyệt xong. '
                                   f'Hạn chót: {deadline_day}/{current_month}/{current_year}.',
                        'type': 'warning',
                    })

    @api.model
    def _cron_check_ratio_warning(self):
        """Periodic check for ratio violations and notify TCCB."""
        today = datetime.date.today()
        config = self.env['bv.evaluation.config'].get_config(year=today.year)
        if not config.notify_ratio_warning:
            return

        current_month = str(today.month)
        departments = self.env['hr.department'].search([])

        violations = []
        for dept in departments:
            dept_evals = self.search([
                ('department_id', '=', dept.id),
                ('year', '=', today.year),
                ('month', '=', current_month),
                ('state', 'in', ['dept_approved', 'hr_reviewed', 'approved']),
            ])
            if not dept_evals:
                continue

            excellent = len(dept_evals.filtered(lambda e: e.classification == 'excellent'))
            good = len(dept_evals.filtered(lambda e: e.classification == 'good'))

            if good > 0:
                ratio = excellent * 100.0 / good
                if ratio > config.max_excellent_ratio:
                    violations.append(
                        f'{dept.name}: {ratio:.1f}% '
                        f'({excellent} xuất sắc / {good} tốt)')

        if violations:
            hr_users = self.env.ref('bv_danh_gia.group_evaluation_hr').users
            message = 'Các khoa/phòng vượt tỷ lệ xuất sắc:\n' + '\n'.join(violations)
            for hr_user in hr_users:
                self.env['bus.bus']._sendone(
                    hr_user.partner_id, 'bv_danh_gia/notification', {
                        'title': '⚠ Cảnh báo tỷ lệ xếp loại',
                        'message': message,
                        'type': 'danger',
                    })
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'note': message,
                    'user_id': hr_user.id,
                    'res_model_id': self.env['ir.model']._get_id('bv.evaluation.config'),
                    'res_id': config.id,
                    'date_deadline': today + datetime.timedelta(days=3),
                    'summary': 'Cảnh báo tỷ lệ xếp loại vượt giới hạn',
                })
