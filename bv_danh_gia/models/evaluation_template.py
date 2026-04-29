from odoo import models, fields, api
from odoo.exceptions import UserError


class EvaluationTemplate(models.Model):
    _name = 'bv.evaluation.template'
    _description = 'Biểu mẫu đánh giá (TCCB tạo/sửa/xóa)'
    _order = 'sequence, id'

    name = fields.Char(string='Tên biểu mẫu', required=True)
    code = fields.Char(string='Mã biểu mẫu')
    description = fields.Text(string='Mô tả')
    active = fields.Boolean(string='Đang sử dụng', default=True)
    sequence = fields.Integer(string='Thứ tự', default=10)

    template_type = fields.Selection([
        ('monthly', 'Đánh giá hằng tháng'),
        ('quarterly', 'Tổng hợp quý'),
        ('yearly', 'Xếp loại năm'),
        ('custom', 'Tùy chỉnh'),
    ], string='Loại biểu mẫu', required=True, default='monthly')

    apply_to = fields.Selection([
        ('all', 'Tất cả CBVC'),
        ('manager', 'Chỉ lãnh đạo, quản lý'),
        ('staff', 'Chỉ nhân viên (không giữ chức vụ)'),
    ], string='Áp dụng cho', default='all')

    year_from = fields.Integer(string='Áp dụng từ năm')
    year_to = fields.Integer(string='Đến năm', help='Để trống nếu áp dụng vô thời hạn')

    # Criteria configuration within template
    criteria_ids = fields.One2many(
        'bv.evaluation.template.criteria', 'template_id',
        string='Tiêu chí đánh giá')
    total_general_score = fields.Float(
        string='Tổng điểm tiêu chí chung', compute='_compute_totals', store=True)
    task_score_weight = fields.Float(
        string='Trọng số điểm KQTHNV', default=70.0,
        help='Điểm tối đa cho phần kết quả thực hiện nhiệm vụ')

    # Workflow configuration per template
    workflow_steps = fields.Selection([
        ('full', 'Đầy đủ: NV → Trưởng khoa → TCCB → BGĐ'),
        ('skip_dept', 'Bỏ qua trưởng khoa: NV → TCCB → BGĐ'),
        ('skip_hr', 'Bỏ qua TCCB: NV → Trưởng khoa → BGĐ'),
        ('minimal', 'Tối giản: NV → BGĐ'),
        ('auto', 'Tự động duyệt hoàn toàn'),
    ], string='Quy trình duyệt', default='full')

    created_by = fields.Many2one('res.users', string='Người tạo',
                                  default=lambda self: self.env.user, readonly=True)
    date_created = fields.Date(string='Ngày tạo', default=fields.Date.today, readonly=True)

    @api.depends('criteria_ids.max_score')
    def _compute_totals(self):
        for rec in self:
            rec.total_general_score = sum(rec.criteria_ids.mapped('max_score'))

    def action_duplicate_template(self):
        """Allow TCCB to quickly create a new template from an existing one."""
        self.ensure_one()
        new = self.copy(default={
            'name': f'{self.name} (Bản sao)',
            'active': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Biểu mẫu mới',
            'res_model': self._name,
            'res_id': new.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_apply_to_evaluations(self):
        """Apply this template's criteria to new evaluations."""
        self.ensure_one()
        Criteria = self.env['bv.evaluation.criteria']
        for tc in self.criteria_ids.filtered(lambda c: not c.synced_criteria_id):
            parent = False
            if tc.parent_line_id and tc.parent_line_id.synced_criteria_id:
                parent = tc.parent_line_id.synced_criteria_id.id

            new_criteria = Criteria.create({
                'name': tc.name,
                'code': tc.code,
                'category': 'general',
                'max_score': tc.max_score,
                'sequence': tc.sequence,
                'parent_id': parent,
                'note': tc.note,
            })
            tc.synced_criteria_id = new_criteria.id

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đồng bộ thành công',
                'message': f'Đã đồng bộ {len(self.criteria_ids)} tiêu chí từ biểu mẫu "{self.name}" '
                           'vào hệ thống tiêu chí đánh giá.',
                'type': 'success',
                'sticky': False,
            },
        }

    def action_archive(self):
        """Soft-delete: archive the template."""
        self.write({'active': False})

    def unlink(self):
        for rec in self:
            eval_count = self.env['bv.monthly.evaluation'].search_count([
                ('template_id', '=', rec.id),
            ])
            if eval_count > 0:
                raise UserError(
                    f'Không thể xóa biểu mẫu "{rec.name}" vì đã có {eval_count} '
                    'phiếu đánh giá sử dụng. Hãy lưu trữ (archive) thay vì xóa.')
        return super().unlink()


class EvaluationTemplateCriteria(models.Model):
    _name = 'bv.evaluation.template.criteria'
    _description = 'Tiêu chí trong biểu mẫu đánh giá'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'bv.evaluation.template', string='Biểu mẫu',
        required=True, ondelete='cascade')
    name = fields.Char(string='Tên tiêu chí', required=True)
    code = fields.Char(string='Mã')
    parent_line_id = fields.Many2one(
        'bv.evaluation.template.criteria', string='Tiêu chí cha',
        ondelete='cascade')
    max_score = fields.Float(string='Điểm tối đa', required=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    note = fields.Text(string='Hướng dẫn chấm')
    synced_criteria_id = fields.Many2one(
        'bv.evaluation.criteria', string='Tiêu chí đã đồng bộ',
        readonly=True)
