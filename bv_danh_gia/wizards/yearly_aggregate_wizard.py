from odoo import models, fields, api
from odoo.exceptions import UserError


class YearlyAggregateWizard(models.TransientModel):
    _name = 'bv.yearly.aggregate.wizard'
    _description = 'Wizard tổng hợp xếp loại năm từ phiếu tháng'

    year = fields.Integer(string='Năm', required=True,
                          default=lambda self: fields.Date.today().year)
    department_id = fields.Many2one(
        'hr.department', string='Khoa/Phòng',
        help='Để trống để tổng hợp tất cả')

    def action_aggregate(self):
        self.ensure_one()
        MonthlyEval = self.env['bv.monthly.evaluation']
        YearlyClassification = self.env['bv.yearly.classification']

        domain = [
            ('year', '=', self.year),
            ('state', 'in', ['dept_approved', 'hr_reviewed', 'approved']),
        ]
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))

        evals = MonthlyEval.search(domain)
        if not evals:
            raise UserError(f'Không tìm thấy phiếu đánh giá đã duyệt cho năm {self.year}.')

        employee_ids = evals.mapped('employee_id')
        created_count = 0

        for emp in employee_ids:
            emp_evals = evals.filtered(lambda e: e.employee_id == emp)
            monthly_scores = {int(e.month): e.total_score for e in emp_evals}

            existing = YearlyClassification.search([
                ('employee_id', '=', emp.id),
                ('year', '=', self.year),
            ], limit=1)

            vals = {
                'employee_id': emp.id,
                'year': self.year,
            }
            for m in range(1, 13):
                vals[f'month_{m}'] = monthly_scores.get(m, 0.0)

            if existing:
                existing.write(vals)
            else:
                YearlyClassification.create(vals)
                created_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Tổng hợp năm hoàn tất',
                'message': f'Đã tổng hợp {len(employee_ids)} nhân viên cho năm {self.year}. '
                           f'Tạo mới: {created_count}, Cập nhật: {len(employee_ids) - created_count}.',
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': 'Xếp loại năm',
                    'res_model': 'bv.yearly.classification',
                    'view_mode': 'list,form',
                    'domain': [('year', '=', self.year)],
                },
            },
        }
