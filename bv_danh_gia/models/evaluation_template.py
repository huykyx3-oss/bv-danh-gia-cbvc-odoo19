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

    # Nhãn hiển thị 6 tiêu chí KQTHNV (TCCB có thể đổi tên, không thêm mới)
    label_pct_a = fields.Char(
        string='Nhãn tiêu chí a (Số lượng)',
        default='a) Tỷ lệ % số lượng kết quả thực hiện nhiệm vụ')
    label_pct_b = fields.Char(
        string='Nhãn tiêu chí b (Chất lượng)',
        default='b) Tỷ lệ % chất lượng kết quả thực hiện nhiệm vụ')
    label_pct_c = fields.Char(
        string='Nhãn tiêu chí c (Tiến độ)',
        default='c) Tỷ lệ % tiến độ kết quả thực hiện nhiệm vụ')
    label_pct_d = fields.Char(
        string='Nhãn tiêu chí d (Kết quả lĩnh vực — lãnh đạo)',
        default='d) Tỷ lệ % kết quả hoạt động lĩnh vực phụ trách')
    label_pct_dd = fields.Char(
        string='Nhãn tiêu chí đ (Tổ chức — lãnh đạo)',
        default='đ) Tỷ lệ % khả năng tổ chức triển khai')
    label_pct_e = fields.Char(
        string='Nhãn tiêu chí e (Đoàn kết — lãnh đạo)',
        default='e) Tỷ lệ % năng lực tập hợp, đoàn kết')

    # Workflow configuration per template
    workflow_steps = fields.Selection([
        ('full', 'NV → TK/TP → TCCB → BGĐ'),
        ('nv_tp_tccb', 'NV → TK/TP → TCCB (không qua BGĐ)'),
        ('nv_tp', 'NV → TK/TP (trưởng khoa duyệt là kết thúc)'),
        ('skip_dept', 'Bỏ qua TK/TP: NV → TCCB → BGĐ'),
        ('skip_hr', 'Bỏ qua TCCB: NV → TK/TP → BGĐ'),
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
        """No-op kept for compatibility.

        With the new design, template criteria already reference master records
        (via `criteria_id` Many2one), so syncing is implicit.
        Override values (max_score per template) live only on the template line.
        """
        return True

    def action_apply_to_evaluations(self):
        """Manual button: gives user feedback that template is ready to use."""
        for rec in self:
            missing = rec.criteria_ids.filtered(lambda c: not c.criteria_id)
            if missing:
                raise UserError(
                    f'Có {len(missing)} dòng chưa chọn tiêu chí từ danh mục. '
                    'Vui lòng hoàn thiện trước khi áp dụng.'
                )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sẵn sàng sử dụng',
                'message': f'Biểu mẫu "{self.name}" đã sẵn sàng — nhân viên có thể chọn ngay.',
                'type': 'success',
                'sticky': False,
            },
        }

    def action_add_criteria_from_master(self):
        """Quickly add multiple criteria from master catalog."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Thêm tiêu chí từ danh mục',
            'res_model': 'bv.evaluation.criteria',
            'view_mode': 'list',
            'domain': [('is_parent', '=', False), ('active', '=', True)],
            'context': {
                'default_template_id': self.id,
                'tree_view_ref': 'bv_danh_gia.view_evaluation_criteria_tree',
            },
            'target': 'new',
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

    # ─── Primary picker: chọn 1 lần từ danh mục, mọi thông tin tự điền ───
    criteria_id = fields.Many2one(
        'bv.evaluation.criteria',
        string='Tiêu chí (chọn từ danh mục)',
        domain="[('is_parent', '=', False), ('active', '=', True)]",
        required=True, ondelete='restrict',
        help='Gõ tên hoặc mã để tìm tiêu chí có sẵn. '
             'Bấm "Tạo và chỉnh sửa..." để thêm tiêu chí mới vào danh mục.')

    # Hiển thị thông tin từ master (read-only, kế thừa từ criteria_id)
    code = fields.Char(
        related='criteria_id.code', string='Mã',
        readonly=True, store=False)
    name = fields.Char(
        related='criteria_id.name', string='Tên tiêu chí',
        readonly=True, store=False)
    parent_id = fields.Many2one(
        related='criteria_id.parent_id', string='Tiêu chí cha',
        readonly=True, store=True)

    # Per-template overrides
    max_score = fields.Float(
        string='Điểm tối đa', required=True, default=0.0,
        help='Điểm áp dụng cho biểu mẫu này. '
             'Tự động lấy từ danh mục khi chọn tiêu chí, có thể chỉnh riêng.')
    sequence = fields.Integer(
        string='Thứ tự', default=10,
        help='Số nhỏ hơn = hiển thị lên đầu')
    note = fields.Text(
        string='Hướng dẫn chấm',
        help='Nếu để trống sẽ dùng hướng dẫn từ danh mục')

    # Backward-compat alias used by views/imports
    synced_criteria_id = fields.Many2one(
        related='criteria_id', string='Đã đồng bộ',
        readonly=True, store=False)

    _unique_template_criteria = models.Constraint(
        'unique(template_id, criteria_id)',
        "Mỗi tiêu chí chỉ được thêm một lần vào cùng một biểu mẫu.")

    @api.onchange('criteria_id')
    def _onchange_criteria_id(self):
        """Auto-populate per-template values from master when a criteria is picked."""
        if not self.criteria_id:
            return
        src = self.criteria_id
        if not self.max_score:
            self.max_score = src.max_score
        if not self.note:
            self.note = src.note or ''
        if not self.sequence or self.sequence == 10:
            self.sequence = src.sequence or 10
