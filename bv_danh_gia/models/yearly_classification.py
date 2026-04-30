from odoo import models, fields, api
from odoo.exceptions import UserError

CLASSIFICATION = [
    ('excellent', 'Hoàn thành xuất sắc nhiệm vụ'),
    ('good', 'Hoàn thành tốt nhiệm vụ'),
    ('fair', 'Hoàn thành nhiệm vụ'),
    ('poor', 'Không hoàn thành nhiệm vụ'),
]


class YearlyClassification(models.Model):
    _name = 'bv.yearly.classification'
    _description = 'Phiếu xếp loại chất lượng CBVC năm (Mẫu số 02)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc, employee_id'

    employee_id = fields.Many2one(
        'hr.employee', string='Họ và tên', required=True, tracking=True)
    department_id = fields.Many2one(
        'hr.department', string='Đơn vị công tác',
        related='employee_id.department_id', store=True)
    job_id = fields.Many2one(
        'hr.job', string='Chức vụ, chức danh',
        related='employee_id.job_id', store=True)
    year = fields.Integer(string='Năm', required=True, tracking=True)

    quarterly_ids = fields.One2many(
        'bv.quarterly.summary', 'yearly_classification_id',
        string='Tổng hợp quý')

    # Monthly scores for the full table (Mẫu 02)
    month_1 = fields.Float(string='Tháng 1')
    month_2 = fields.Float(string='Tháng 2')
    month_3 = fields.Float(string='Tháng 3')
    quarter_1_avg = fields.Float(string='Quý I', compute='_compute_quarter_avgs', store=True)
    month_4 = fields.Float(string='Tháng 4')
    month_5 = fields.Float(string='Tháng 5')
    month_6 = fields.Float(string='Tháng 6')
    quarter_2_avg = fields.Float(string='Quý II', compute='_compute_quarter_avgs', store=True)
    month_7 = fields.Float(string='Tháng 7')
    month_8 = fields.Float(string='Tháng 8')
    month_9 = fields.Float(string='Tháng 9')
    quarter_3_avg = fields.Float(string='Quý III', compute='_compute_quarter_avgs', store=True)
    month_10 = fields.Float(string='Tháng 10')
    month_11 = fields.Float(string='Tháng 11')
    month_12 = fields.Float(string='Tháng 12')
    quarter_4_avg = fields.Float(string='Quý IV', compute='_compute_quarter_avgs', store=True)

    yearly_average = fields.Float(
        string='Điểm trung bình cả năm', compute='_compute_yearly_average', store=True)

    self_classification = fields.Selection(
        CLASSIFICATION, string='CBVC tự xếp loại')
    final_classification = fields.Selection(
        CLASSIFICATION, string='Cấp có thẩm quyền xếp loại', tracking=True)
    proposed_action = fields.Text(string='Đề xuất phương án xử lý')

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('self_rated', 'Đã tự xếp loại'),
        ('approved', 'Đã phê duyệt'),
    ], string='Trạng thái', default='draft', tracking=True)

    display_name = fields.Char(compute='_compute_display_name', store=True)

    _unique_employee_year = models.Constraint(
        'UNIQUE(employee_id, year)',
        'Mỗi nhân viên chỉ có một phiếu xếp loại trong một năm!'
    )

    @api.depends('employee_id', 'year')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.employee_id.name or ""} - Năm {rec.year}'

    def _quarter_avg(self, m1, m2, m3):
        scores = [s for s in [m1, m2, m3] if s > 0]
        return sum(scores) / len(scores) if scores else 0.0

    @api.depends(
        'month_1', 'month_2', 'month_3',
        'month_4', 'month_5', 'month_6',
        'month_7', 'month_8', 'month_9',
        'month_10', 'month_11', 'month_12')
    def _compute_quarter_avgs(self):
        for rec in self:
            rec.quarter_1_avg = rec._quarter_avg(rec.month_1, rec.month_2, rec.month_3)
            rec.quarter_2_avg = rec._quarter_avg(rec.month_4, rec.month_5, rec.month_6)
            rec.quarter_3_avg = rec._quarter_avg(rec.month_7, rec.month_8, rec.month_9)
            rec.quarter_4_avg = rec._quarter_avg(rec.month_10, rec.month_11, rec.month_12)

    @api.depends(
        'month_1', 'month_2', 'month_3', 'month_4', 'month_5', 'month_6',
        'month_7', 'month_8', 'month_9', 'month_10', 'month_11', 'month_12')
    def _compute_yearly_average(self):
        for rec in self:
            all_scores = [
                rec.month_1, rec.month_2, rec.month_3,
                rec.month_4, rec.month_5, rec.month_6,
                rec.month_7, rec.month_8, rec.month_9,
                rec.month_10, rec.month_11, rec.month_12,
            ]
            valid = [s for s in all_scores if s > 0]
            rec.yearly_average = sum(valid) / len(valid) if valid else 0.0

    def action_self_rate(self):
        for rec in self:
            if not rec.self_classification:
                raise UserError('Vui lòng chọn mức tự xếp loại trước khi gửi.')
            rec.state = 'self_rated'

    def action_approve(self):
        for rec in self:
            if not rec.final_classification:
                raise UserError('Vui lòng chọn mức xếp loại của cấp thẩm quyền.')
            rec.state = 'approved'

    def action_export_docx(self):
        """Open URL to download DOCX file."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/bv_danh_gia/export_mau02/{self.id}',
            'target': 'new',
        }

    def action_populate_from_monthly(self):
        """Pull monthly scores from bv.monthly.evaluation records."""
        MonthlyEval = self.env['bv.monthly.evaluation']
        for rec in self:
            for m in range(1, 13):
                eval_rec = MonthlyEval.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('year', '=', rec.year),
                    ('month', '=', str(m)),
                    ('state', 'in', ['approved', 'hr_reviewed', 'dept_approved']),
                ], limit=1)
                if eval_rec:
                    setattr(rec, f'month_{m}', eval_rec.total_score)
