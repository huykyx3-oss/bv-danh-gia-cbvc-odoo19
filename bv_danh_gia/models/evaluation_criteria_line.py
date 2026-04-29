from odoo import models, fields, api
from odoo.exceptions import ValidationError


class EvaluationCriteriaLine(models.Model):
    _name = 'bv.evaluation.criteria.line'
    _description = 'Dòng chấm điểm tiêu chí chung'
    _order = 'sequence, id'

    evaluation_id = fields.Many2one(
        'bv.monthly.evaluation', string='Phiếu đánh giá',
        required=True, ondelete='cascade')
    criteria_id = fields.Many2one(
        'bv.evaluation.criteria', string='Tiêu chí',
        required=True, domain="[('category', '=', 'general'), ('is_parent', '=', False)]")
    sequence = fields.Integer(related='criteria_id.sequence', store=True)
    parent_criteria_id = fields.Many2one(
        related='criteria_id.parent_id', store=True, string='Nhóm tiêu chí')
    max_score = fields.Float(related='criteria_id.max_score', string='Điểm tối đa', readonly=True)
    self_score = fields.Float(string='Điểm tự chấm', default=0.0)
    dept_score = fields.Float(string='Điểm trưởng khoa chấm', default=0.0)
    final_score = fields.Float(string='Điểm cuối cùng', compute='_compute_final_score', store=True)
    note = fields.Text(string='Ghi chú')

    @api.depends('self_score', 'dept_score', 'evaluation_id.state')
    def _compute_final_score(self):
        for line in self:
            if line.evaluation_id.state in ('dept_approved', 'hr_reviewed', 'approved'):
                line.final_score = line.dept_score
            else:
                line.final_score = line.self_score

    @api.constrains('self_score', 'dept_score', 'max_score')
    def _check_score_range(self):
        for line in self:
            if line.self_score < 0 or line.self_score > line.max_score:
                raise ValidationError(
                    f'Điểm tự chấm tiêu chí "{line.criteria_id.name}" phải từ 0 đến {line.max_score}')
            if line.dept_score < 0 or line.dept_score > line.max_score:
                raise ValidationError(
                    f'Điểm trưởng khoa chấm tiêu chí "{line.criteria_id.name}" phải từ 0 đến {line.max_score}')
