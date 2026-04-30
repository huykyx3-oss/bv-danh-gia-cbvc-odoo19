from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import datetime

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
    template_id = fields.Many2one(
        'bv.evaluation.template', string='Biểu mẫu đánh giá',
        domain="[('active', '=', True), ('template_type', '=', 'monthly')]",
        help='Biểu mẫu đánh giá do TCCB tạo')

    # --- Tiêu chí chung (30 điểm) ---
    criteria_line_ids = fields.One2many(
        'bv.evaluation.criteria.line', 'evaluation_id',
        string='Tiêu chí chung')
    general_score = fields.Float(
        string='Điểm tiêu chí chung', compute='_compute_general_score',
        store=True, tracking=True)

    # --- Tiêu chí kết quả nhiệm vụ (70 điểm) ---
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
    task_score = fields.Float(
        string='Điểm tiêu chí KQTHNV', compute='_compute_task_score',
        store=True, tracking=True)

    # --- Tổng điểm ---
    total_score = fields.Float(
        string='Tổng điểm', compute='_compute_total_score',
        store=True, tracking=True)
    classification = fields.Selection(
        CLASSIFICATION, string='Mức xếp loại',
        compute='_compute_classification', store=True, tracking=True)

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

    @api.depends('criteria_line_ids.final_score')
    def _compute_general_score(self):
        for rec in self:
            rec.general_score = sum(rec.criteria_line_ids.mapped('final_score'))

    @api.depends(
        'is_manager',
        'pct_quantity', 'pct_quality', 'pct_progress',
        'pct_field_result', 'pct_organization', 'pct_team_cohesion')
    def _compute_task_score(self):
        for rec in self:
            if rec.is_manager:
                total_pct = (
                    rec.pct_quantity + rec.pct_quality + rec.pct_progress
                    + rec.pct_field_result + rec.pct_organization + rec.pct_team_cohesion
                )
                rec.task_score = (total_pct / 6.0) * 70.0 / 100.0
            else:
                total_pct = rec.pct_quantity + rec.pct_quality + rec.pct_progress
                rec.task_score = (total_pct / 3.0) * 70.0 / 100.0

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

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """When employee selects a template, load its criteria immediately."""
        # Always clear existing lines when template changes
        self.criteria_line_ids = [(5, 0, 0)]
        if not self.template_id:
            return

        tmpl = self.template_id
        # Ensure criteria are synced to master
        if tmpl.criteria_ids and not all(
            tc.synced_criteria_id for tc in tmpl.criteria_ids.filtered(lambda c: c.parent_line_id)
        ):
            tmpl._sync_criteria_to_master()

        # Build lines from synced leaf criteria (those with parent = a group)
        leaf_tcs = tmpl.criteria_ids.filtered(
            lambda c: c.parent_line_id and c.synced_criteria_id
        ).sorted('sequence')

        if leaf_tcs:
            self.criteria_line_ids = [
                (0, 0, {'criteria_id': tc.synced_criteria_id.id})
                for tc in leaf_tcs
            ]
        else:
            # Fallback: template has no parent grouping, load all synced criteria
            all_tcs = tmpl.criteria_ids.filtered(
                lambda c: c.synced_criteria_id
            ).sorted('sequence')
            self.criteria_line_ids = [
                (0, 0, {'criteria_id': tc.synced_criteria_id.id})
                for tc in all_tcs
            ]

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
        Priority: template criteria → global master criteria."""
        CriteriaLine = self.env['bv.evaluation.criteria.line']
        for rec in self:
            if rec.template_id and rec.template_id.criteria_ids:
                # Use template criteria — map parent lines to bv.evaluation.criteria
                self._populate_from_template(rec, CriteriaLine)
            else:
                # Fallback: use global master criteria
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
        """Create criteria lines from template, auto-creating master criteria as needed.
        Two-pass: parents first so child parent_id references are valid."""
        Criteria = self.env['bv.evaluation.criteria']
        parent_map = {}  # template_criteria_id → bv.evaluation.criteria id

        # Pass 1: create/find parent (group) criteria
        for tc in rec.template_id.criteria_ids.filtered(lambda c: not c.parent_line_id).sorted('sequence'):
            existing_parent = Criteria.search([
                ('name', '=', tc.name),
                ('category', '=', 'general'),
                ('parent_id', '=', False),
            ], limit=1)
            if not existing_parent:
                existing_parent = Criteria.create({
                    'name': tc.name,
                    'code': tc.code or '',
                    'category': 'general',
                    'max_score': tc.max_score,
                    'sequence': tc.sequence,
                })
            parent_map[tc.id] = existing_parent.id

        # Pass 2: create/find leaf criteria and their evaluation lines
        for tc in rec.template_id.criteria_ids.filtered(lambda c: c.parent_line_id).sorted('sequence'):
            parent_criteria_id = parent_map.get(tc.parent_line_id.id)
            existing = Criteria.search([
                ('name', '=', tc.name),
                ('category', '=', 'general'),
                ('parent_id', '=', parent_criteria_id),
            ], limit=1)
            if not existing:
                existing = Criteria.create({
                    'name': tc.name,
                    'code': tc.code or '',
                    'category': 'general',
                    'max_score': tc.max_score,
                    'sequence': tc.sequence,
                    'parent_id': parent_criteria_id,
                    'note': tc.note or '',
                })
            CriteriaLine.create({
                'evaluation_id': rec.id,
                'criteria_id': existing.id,
            })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._populate_criteria_lines()
        return records

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
        """Open the custom evaluation form view."""
        self.ensure_one()
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

    def _advance_workflow_after_dept(self, config):
        """Skip HR/Director states after dept manager approves."""
        self.ensure_one()
        steps = self._get_workflow_steps()
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

            config = rec._get_config()
            if config.notify_on_approve and rec.employee_id.user_id:
                rec._send_notification(
                    rec.employee_id.user_id,
                    'Phiếu đánh giá đã được phê duyệt',
                    f'Phiếu đánh giá Tháng {rec.month}/{rec.year} của bạn '
                    f'đã được phê duyệt. Tổng điểm: {rec.total_score:.1f}',
                    'success')

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
