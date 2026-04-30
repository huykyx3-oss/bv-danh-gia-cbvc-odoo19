from odoo import models, fields, api
from odoo.exceptions import UserError

CLASSIFICATION = [
    ('excellent', 'Hoàn thành xuất sắc nhiệm vụ'),
    ('good', 'Hoàn thành tốt nhiệm vụ'),
    ('fair', 'Hoàn thành nhiệm vụ'),
    ('poor', 'Không hoàn thành nhiệm vụ'),
]


class QuarterlySummary(models.Model):
    _name = 'bv.quarterly.summary'
    _description = 'Tổng hợp đánh giá quý'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc, quarter desc, employee_id'

    employee_id = fields.Many2one(
        'hr.employee', string='Họ và tên', required=True, tracking=True)
    department_id = fields.Many2one(
        'hr.department', string='Đơn vị công tác',
        related='employee_id.department_id', store=True)
    job_id = fields.Many2one(
        'hr.job', string='Chức vụ',
        related='employee_id.job_id', store=True)
    quarter = fields.Selection([
        ('1', 'Quý I'), ('2', 'Quý II'),
        ('3', 'Quý III'), ('4', 'Quý IV'),
    ], string='Quý', required=True, tracking=True)
    year = fields.Integer(string='Năm', required=True, tracking=True)

    month1_score = fields.Float(string='Điểm tháng 1 của quý')
    month2_score = fields.Float(string='Điểm tháng 2 của quý')
    month3_score = fields.Float(string='Điểm tháng 3 của quý')
    average_score = fields.Float(
        string='Điểm trung bình quý', compute='_compute_average', store=True)
    classification = fields.Selection(
        CLASSIFICATION, string='Mức xếp loại',
        compute='_compute_classification', store=True)

    monthly_eval_ids = fields.Many2many(
        'bv.monthly.evaluation', string='Phiếu đánh giá tháng',
        compute='_compute_monthly_evals')

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('dept_approved', 'Trưởng khoa duyệt'),
        ('hr_reviewed', 'TCCB xét duyệt'),
        ('approved', 'BGĐ phê duyệt'),
    ], string='Trạng thái', default='draft', tracking=True)

    yearly_classification_id = fields.Many2one(
        'bv.yearly.classification', string='Phiếu xếp loại năm',
        ondelete='set null')

    display_name = fields.Char(compute='_compute_display_name', store=True)

    _unique_employee_quarter_year = models.Constraint(
        'UNIQUE(employee_id, quarter, year)',
        'Mỗi nhân viên chỉ có một bản tổng hợp trong một quý!'
    )

    @api.depends('employee_id', 'quarter', 'year')
    def _compute_display_name(self):
        quarter_labels = dict(self._fields['quarter'].selection)
        for rec in self:
            q = quarter_labels.get(rec.quarter, '')
            rec.display_name = f'{rec.employee_id.name or ""} - {q}/{rec.year}'

    def _compute_monthly_evals(self):
        for rec in self:
            q = int(rec.quarter) if rec.quarter else 1
            months = [str(m) for m in range((q - 1) * 3 + 1, q * 3 + 1)]
            rec.monthly_eval_ids = self.env['bv.monthly.evaluation'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('year', '=', rec.year),
                ('month', 'in', months),
            ])

    @api.depends('month1_score', 'month2_score', 'month3_score')
    def _compute_average(self):
        for rec in self:
            scores = [s for s in [rec.month1_score, rec.month2_score, rec.month3_score] if s > 0]
            rec.average_score = sum(scores) / len(scores) if scores else 0.0

    @api.depends('average_score')
    def _compute_classification(self):
        for rec in self:
            score = rec.average_score
            if score >= 90:
                rec.classification = 'excellent'
            elif score >= 70:
                rec.classification = 'good'
            elif score >= 50:
                rec.classification = 'fair'
            else:
                rec.classification = 'poor'

    def action_dept_approve(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Chỉ duyệt được bản tổng hợp ở trạng thái Nháp.')
            rec.state = 'dept_approved'

    def action_hr_review(self):
        for rec in self:
            if rec.state != 'dept_approved':
                raise UserError('Chỉ xét duyệt được bản tổng hợp đã qua trưởng khoa.')
            rec.state = 'hr_reviewed'

    def action_approve(self):
        for rec in self:
            if rec.state != 'hr_reviewed':
                raise UserError('Chỉ phê duyệt được bản tổng hợp đã qua TCCB.')
            rec.state = 'approved'
