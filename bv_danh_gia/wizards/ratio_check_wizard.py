from odoo import models, fields, api
from odoo.exceptions import UserError


class RatioCheckWizard(models.TransientModel):
    _name = 'bv.ratio.check.wizard'
    _description = 'Wizard kiểm tra tỷ lệ xếp loại xuất sắc'

    quarter = fields.Selection([
        ('1', 'Quý I'), ('2', 'Quý II'),
        ('3', 'Quý III'), ('4', 'Quý IV'),
    ], string='Quý')
    year = fields.Integer(string='Năm', required=True,
                          default=lambda self: fields.Date.today().year)
    department_id = fields.Many2one(
        'hr.department', string='Khoa/Phòng',
        help='Để trống để kiểm tra tất cả khoa/phòng')
    check_type = fields.Selection([
        ('quarterly', 'Theo quý'),
        ('yearly', 'Theo năm'),
    ], string='Loại kiểm tra', required=True, default='quarterly')
    max_ratio = fields.Float(
        string='Tỷ lệ xuất sắc tối đa (%)', default=20.0,
        help='Theo QĐ 06/2026: tối đa 20% (trường hợp đặc biệt: 25%)')
    result_html = fields.Html(string='Kết quả kiểm tra', readonly=True)

    def action_check(self):
        self.ensure_one()

        if self.check_type == 'quarterly':
            if not self.quarter:
                raise UserError('Vui lòng chọn quý cần kiểm tra.')
            return self._check_quarterly()
        else:
            return self._check_yearly()

    def _check_quarterly(self):
        QuarterlySummary = self.env['bv.quarterly.summary']
        domain = [
            ('quarter', '=', self.quarter),
            ('year', '=', self.year),
        ]
        if self.department_id:
            departments = self.department_id
        else:
            departments = self.env['hr.department'].search([])

        html_parts = ['<h4>Kết quả kiểm tra tỷ lệ xếp loại - Quý %s/%s</h4>' %
                       (self.quarter, self.year)]
        html_parts.append('<table class="table table-bordered table-sm">')
        html_parts.append(
            '<thead><tr><th>Khoa/Phòng</th><th>Tổng NV</th>'
            '<th>Xuất sắc</th><th>Tốt</th><th>Tỷ lệ XS/Tốt</th>'
            '<th>Giới hạn</th><th>Kết quả</th></tr></thead><tbody>')

        for dept in departments:
            summaries = QuarterlySummary.search(domain + [('department_id', '=', dept.id)])
            if not summaries:
                continue

            total = len(summaries)
            excellent = len(summaries.filtered(lambda s: s.classification == 'excellent'))
            good = len(summaries.filtered(lambda s: s.classification == 'good'))
            ratio = (excellent * 100.0 / good) if good > 0 else 0.0
            ok = ratio <= self.max_ratio

            color = 'green' if ok else 'red'
            status = 'ĐẠT' if ok else 'VƯỢT QUÁ'

            html_parts.append(
                f'<tr><td>{dept.name}</td><td class="text-center">{total}</td>'
                f'<td class="text-center">{excellent}</td>'
                f'<td class="text-center">{good}</td>'
                f'<td class="text-center">{ratio:.1f}%</td>'
                f'<td class="text-center">{self.max_ratio}%</td>'
                f'<td class="text-center" style="color:{color}"><strong>{status}</strong></td></tr>')

        html_parts.append('</tbody></table>')

        self.result_html = ''.join(html_parts)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kết quả kiểm tra tỷ lệ',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _check_yearly(self):
        YearlyClassification = self.env['bv.yearly.classification']
        if self.department_id:
            departments = self.department_id
        else:
            departments = self.env['hr.department'].search([])

        html_parts = ['<h4>Kết quả kiểm tra tỷ lệ xếp loại - Năm %s</h4>' % self.year]
        html_parts.append('<table class="table table-bordered table-sm">')
        html_parts.append(
            '<thead><tr><th>Khoa/Phòng</th><th>Tổng NV</th>'
            '<th>Xuất sắc</th><th>Tốt</th><th>Tỷ lệ XS/Tốt</th>'
            '<th>Giới hạn</th><th>Kết quả</th></tr></thead><tbody>')

        for dept in departments:
            records = YearlyClassification.search([
                ('year', '=', self.year),
                ('department_id', '=', dept.id),
                ('state', '=', 'approved'),
            ])
            if not records:
                continue

            total = len(records)
            excellent = len(records.filtered(lambda r: r.final_classification == 'excellent'))
            good = len(records.filtered(lambda r: r.final_classification == 'good'))
            ratio = (excellent * 100.0 / good) if good > 0 else 0.0
            ok = ratio <= self.max_ratio

            color = 'green' if ok else 'red'
            status = 'ĐẠT' if ok else 'VƯỢT QUÁ'

            html_parts.append(
                f'<tr><td>{dept.name}</td><td class="text-center">{total}</td>'
                f'<td class="text-center">{excellent}</td>'
                f'<td class="text-center">{good}</td>'
                f'<td class="text-center">{ratio:.1f}%</td>'
                f'<td class="text-center">{self.max_ratio}%</td>'
                f'<td class="text-center" style="color:{color}"><strong>{status}</strong></td></tr>')

        html_parts.append('</tbody></table>')

        # Special rule: groups < 5 people can have 1 excellent
        html_parts.append(
            '<p><em>Lưu ý: Nhóm dưới 05 người được chọn 01 người xếp loại '
            '"Hoàn thành xuất sắc nhiệm vụ" nếu đáp ứng đủ điều kiện '
            '(Điều 18, QĐ 06/2026/QĐ-UBND).</em></p>')

        self.result_html = ''.join(html_parts)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kết quả kiểm tra tỷ lệ',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
