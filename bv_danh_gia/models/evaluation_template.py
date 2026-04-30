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

    def _sync_criteria_to_master(self):
        """Sync all template criteria to bv.evaluation.criteria master table.
        Runs automatically on save so employees can immediately use the template."""
        Criteria = self.env['bv.evaluation.criteria']
        parent_map = {}  # tc.id -> criteria.id

        # Pass 1: parent groups
        for tc in self.criteria_ids.filtered(lambda c: not c.parent_line_id).sorted('sequence'):
            if tc.synced_criteria_id:
                # Update existing
                tc.synced_criteria_id.write({
                    'name': tc.name, 'code': tc.code or '',
                    'max_score': tc.max_score, 'sequence': tc.sequence,
                })
                parent_map[tc.id] = tc.synced_criteria_id.id
            else:
                # Find existing by name or create
                existing = Criteria.search([
                    ('name', '=', tc.name), ('category', '=', 'general'),
                    ('parent_id', '=', False),
                ], limit=1)
                if not existing:
                    existing = Criteria.create({
                        'name': tc.name, 'code': tc.code or '',
                        'category': 'general', 'max_score': tc.max_score,
                        'sequence': tc.sequence,
                    })
                tc.synced_criteria_id = existing.id
                parent_map[tc.id] = existing.id

        # Pass 2: leaf criteria
        for tc in self.criteria_ids.filtered(lambda c: c.parent_line_id).sorted('sequence'):
            parent_id = parent_map.get(tc.parent_line_id.id)
            if tc.synced_criteria_id:
                tc.synced_criteria_id.write({
                    'name': tc.name, 'code': tc.code or '',
                    'max_score': tc.max_score, 'sequence': tc.sequence,
                    'parent_id': parent_id, 'note': tc.note or '',
                })
            else:
                existing = Criteria.search([
                    ('name', '=', tc.name), ('category', '=', 'general'),
                    ('parent_id', '=', parent_id),
                ], limit=1)
                if not existing:
                    existing = Criteria.create({
                        'name': tc.name, 'code': tc.code or '',
                        'category': 'general', 'max_score': tc.max_score,
                        'sequence': tc.sequence, 'parent_id': parent_id,
                        'note': tc.note or '',
                    })
                tc.synced_criteria_id = existing.id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.criteria_ids:
                rec._sync_criteria_to_master()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'criteria_ids' in vals:
            for rec in self:
                rec._sync_criteria_to_master()
        return result

    def action_apply_to_evaluations(self):
        """Manual sync button: sync criteria and return notification."""
        for rec in self:
            rec._sync_criteria_to_master()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đồng bộ thành công',
                'message': f'Đã đồng bộ tiêu chí từ biểu mẫu "{self.name}" vào hệ thống.',
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

    # Helper: pick from master catalog to auto-fill name/code/score
    source_criteria_id = fields.Many2one(
        'bv.evaluation.criteria',
        string='Chọn từ danh mục',
        help='Chọn tiêu chí có sẵn trong danh mục để tự động điền tên và điểm tối đa. '
             'Bạn vẫn có thể chỉnh sửa sau khi chọn.',
        store=False)

    name = fields.Char(string='Tên tiêu chí', required=True)
    code = fields.Char(string='Mã')
    parent_line_id = fields.Many2one(
        'bv.evaluation.template.criteria', string='Tiêu chí cha (trong biểu mẫu)',
        domain="[('template_id', '=', template_id), ('id', '!=', id)]",
        ondelete='cascade',
        help='Chọn nhóm tiêu chí cha trong cùng biểu mẫu này. '
             'Để trống nếu đây là tiêu chí gốc/nhóm.')
    max_score = fields.Float(string='Điểm tối đa', required=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    note = fields.Text(string='Hướng dẫn chấm')
    synced_criteria_id = fields.Many2one(
        'bv.evaluation.criteria', string='Tiêu chí đã đồng bộ',
        readonly=True)

    @api.onchange('source_criteria_id')
    def _onchange_source_criteria(self):
        if not self.source_criteria_id:
            return
        src = self.source_criteria_id
        self.name = src.name
        self.code = src.code or ''
        self.max_score = src.max_score
        self.note = src.note or ''
        # If the source has a parent, try to find matching parent in this template
        if src.parent_id:
            parent_match = self.template_id.criteria_ids.filtered(
                lambda c: c.name == src.parent_id.name and not c.parent_line_id
            )
            if parent_match:
                self.parent_line_id = parent_match[0]
