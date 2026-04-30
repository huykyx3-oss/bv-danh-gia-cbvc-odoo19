from odoo import models, fields, api


class EvaluationCriteria(models.Model):
    _name = 'bv.evaluation.criteria'
    _description = 'Tiêu chí đánh giá'
    _order = 'category, sequence, id'
    _parent_name = 'parent_id'
    _rec_names_search = ['name', 'code']

    name = fields.Char(string='Tên tiêu chí', required=True)
    code = fields.Char(string='Mã tiêu chí')
    parent_id = fields.Many2one('bv.evaluation.criteria', string='Tiêu chí cha', ondelete='cascade')
    child_ids = fields.One2many('bv.evaluation.criteria', 'parent_id', string='Tiêu chí con')
    category = fields.Selection([
        ('general', 'Tiêu chí chung'),
        ('task_result', 'Kết quả thực hiện nhiệm vụ'),
    ], string='Phân loại', required=True, default='general')
    max_score = fields.Float(string='Điểm tối đa', required=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    active = fields.Boolean(string='Hoạt động', default=True)
    note = fields.Text(string='Ghi chú / Hướng dẫn chấm')
    is_parent = fields.Boolean(string='Là tiêu chí cha', compute='_compute_is_parent', store=True)

    @api.depends('child_ids')
    def _compute_is_parent(self):
        for rec in self:
            rec.is_parent = bool(rec.child_ids)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            if rec.code:
                rec.display_name = f'[{rec.code}] {rec.name or ""}'
            else:
                rec.display_name = rec.name or ''
