from odoo import models, fields, api
from odoo.exceptions import ValidationError


class EvaluationTaskLine(models.Model):
    _name = 'bv.evaluation.task.line'
    _description = 'Chi tiết nhiệm vụ tháng'
    _order = 'sequence, id'

    evaluation_id = fields.Many2one(
        'bv.monthly.evaluation', string='Phiếu đánh giá',
        required=True, ondelete='cascade')
    sequence = fields.Integer(string='STT', default=10)
    task_name = fields.Char(string='Nhiệm vụ được giao', required=True)
    output_product = fields.Char(string='Sản phẩm/Công việc đầu ra')
    deadline = fields.Date(string='Thời hạn hoàn thành')
    completion_date = fields.Date(string='Ngày hoàn thành thực tế')
    quantity_pct = fields.Float(string='% Số lượng', default=100.0)
    quality_pct = fields.Float(string='% Chất lượng', default=100.0)
    progress_pct = fields.Float(string='% Tiến độ', default=100.0)
    is_on_time = fields.Boolean(string='Đúng tiến độ', compute='_compute_is_on_time', store=True)
    note = fields.Text(string='Ghi chú')

    @api.depends('deadline', 'completion_date')
    def _compute_is_on_time(self):
        for line in self:
            if line.deadline and line.completion_date:
                line.is_on_time = line.completion_date <= line.deadline
            else:
                line.is_on_time = True

    @api.constrains('quantity_pct', 'quality_pct', 'progress_pct')
    def _check_pct_range(self):
        for line in self:
            for field_name, label in [
                ('quantity_pct', '% Số lượng'),
                ('quality_pct', '% Chất lượng'),
                ('progress_pct', '% Tiến độ'),
            ]:
                val = getattr(line, field_name)
                if val < 0 or val > 100:
                    raise ValidationError(f'{label} của nhiệm vụ "{line.task_name}" phải từ 0% đến 100%')
