from odoo import models, fields, api


class EvaluationConfig(models.Model):
    _name = 'bv.evaluation.config'
    _description = 'Cấu hình hệ thống đánh giá'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)
    active = fields.Boolean(default=True)
    year = fields.Integer(string='Năm áp dụng', required=True,
                          default=lambda self: fields.Date.today().year)

    # --- Tỷ lệ xếp loại ---
    max_excellent_ratio = fields.Float(
        string='Tỷ lệ Xuất sắc tối đa (%)', default=20.0,
        help='Tỷ lệ % tối đa "Hoàn thành xuất sắc" so với "Hoàn thành tốt" (mặc định: 20%)')
    max_excellent_ratio_special = fields.Float(
        string='Tỷ lệ Xuất sắc tối đa - trường hợp đặc biệt (%)', default=25.0,
        help='Áp dụng cho cơ quan có thành tích nổi trội (tối đa: 25%)')
    min_group_size_for_ratio = fields.Integer(
        string='Số người tối thiểu áp dụng tỷ lệ', default=5,
        help='Nhóm dưới số này được chọn 01 người Xuất sắc nếu đủ điều kiện')
    auto_warn_ratio = fields.Boolean(
        string='Tự động cảnh báo khi vượt tỷ lệ', default=True)

    # --- Workflow ---
    auto_approve_dept = fields.Boolean(
        string='Tự động duyệt cấp Trưởng khoa', default=False,
        help='Bỏ qua bước duyệt trưởng khoa, phiếu gửi thẳng TCCB')
    auto_approve_hr = fields.Boolean(
        string='Tự động duyệt cấp TCCB', default=False,
        help='Bỏ qua bước xét duyệt TCCB, phiếu gửi thẳng BGĐ')
    auto_approve_director = fields.Boolean(
        string='Tự động duyệt cấp BGĐ', default=False,
        help='Tự động phê duyệt cuối cùng (không khuyến nghị)')

    # --- Deadline ---
    monthly_submit_deadline_day = fields.Integer(
        string='Hạn chót gửi phiếu tháng (ngày)', default=10,
        help='Nhân viên phải gửi phiếu trước ngày này của tháng sau')
    quarterly_deadline_day = fields.Integer(
        string='Hạn chót tổng hợp quý (ngày)', default=10,
        help='Hoàn thành tổng hợp quý trước ngày này của tháng cuối quý')
    quarterly_report_deadline_day = fields.Integer(
        string='Hạn chót gửi Sở Y tế (ngày)', default=15,
        help='Gửi kết quả về Sở Y tế trước ngày này của tháng cuối quý')
    reminder_days_before = fields.Integer(
        string='Nhắc trước deadline (ngày)', default=5,
        help='Gửi nhắc nhở trước deadline bao nhiêu ngày')

    # --- Thông báo ---
    notify_on_submit = fields.Boolean(string='Thông báo khi NV gửi phiếu', default=True)
    notify_on_approve = fields.Boolean(string='Thông báo khi được duyệt', default=True)
    notify_on_reject = fields.Boolean(string='Thông báo khi bị trả lại', default=True)
    notify_ratio_warning = fields.Boolean(
        string='Thông báo cảnh báo tỷ lệ', default=True,
        help='Gửi thông báo cho TCCB khi tỷ lệ Xuất sắc vượt giới hạn')

    @api.depends('year')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'Cấu hình đánh giá năm {rec.year}'

    _unique_year = models.Constraint(
        'UNIQUE(year)',
        'Chỉ có một cấu hình cho mỗi năm!'
    )

    @api.model
    def get_config(self, year=None):
        """Get config for a given year, fallback to latest active config."""
        if year:
            config = self.search([('year', '=', year), ('active', '=', True)], limit=1)
            if config:
                return config
        config = self.search([('active', '=', True)], order='year desc', limit=1)
        if not config:
            config = self.create({'year': fields.Date.today().year})
        return config
