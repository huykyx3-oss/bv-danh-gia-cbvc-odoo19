import io
import json
from odoo import http
from odoo.http import request, content_disposition


class ExportDocxController(http.Controller):

    @http.route('/bv_danh_gia/export_mau01/<int:eval_id>', type='http', auth='user')
    def export_mau01_docx(self, eval_id, **kwargs):
        """Export Mẫu 01 - Phiếu theo dõi, đánh giá CBVC as DOCX."""
        evaluation = request.env['bv.monthly.evaluation'].browse(eval_id)
        if not evaluation.exists():
            return request.not_found()

        try:
            from docx import Document
            from docx.shared import Pt, Inches, Cm
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.enum.table import WD_TABLE_ALIGNMENT
        except ImportError:
            return request.make_response(
                json.dumps({'error': 'Thư viện python-docx chưa được cài đặt. '
                            'Chạy: pip install python-docx'}),
                headers=[('Content-Type', 'application/json')])

        doc = Document()

        style = doc.styles['Normal']
        style.font.name = 'Times New Roman'
        style.font.size = Pt(13)
        for font_name in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
            setattr(style.font, font_name, 'Times New Roman')

        def _set_cell_text(cell, text, align=WD_ALIGN_PARAGRAPH.LEFT, bold=False, italic=False):
            cell.text = ''
            p = cell.paragraphs[0]
            p.alignment = align
            run = p.add_run(text or '')
            run.bold = bold
            run.italic = italic
            run.font.name = 'Times New Roman'
            run.font.size = Pt(13)
            return p

        def _add_paragraph(text='', align=WD_ALIGN_PARAGRAPH.LEFT, bold=False, italic=False):
            p = doc.add_paragraph()
            p.alignment = align
            run = p.add_run(text or '')
            run.bold = bold
            run.italic = italic
            run.font.name = 'Times New Roman'
            run.font.size = Pt(13)
            return p

        def _fmt_score(value):
            if value is None:
                return ''
            num = float(value)
            if num.is_integer():
                return str(int(num))
            return f'{num:.2f}'.rstrip('0').rstrip('.')

        # --- Header ---
        table_header = doc.add_table(rows=1, cols=2)
        table_header.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell_left = table_header.cell(0, 0)
        cell_right = table_header.cell(0, 1)

        _set_cell_text(cell_left, 'TÊN CƠ QUAN,\nTỔ CHỨC, ĐƠN VỊ', WD_ALIGN_PARAGRAPH.CENTER, bold=True)
        p_right = _set_cell_text(
            cell_right,
            'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc',
            WD_ALIGN_PARAGRAPH.CENTER,
            bold=True,
        )
        p_right.add_run('\n──────────────').font.size = Pt(13)

        _add_paragraph('Mẫu số 01', WD_ALIGN_PARAGRAPH.RIGHT, bold=True)
        _add_paragraph('PHIẾU THEO DÕI, ĐÁNH GIÁ CÁN BỘ, CÔNG CHỨC, VIÊN CHỨC', WD_ALIGN_PARAGRAPH.CENTER, bold=True)

        month_labels = dict([
            ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'),
            ('4', 'Tháng 4'), ('5', 'Tháng 5'), ('6', 'Tháng 6'),
            ('7', 'Tháng 7'), ('8', 'Tháng 8'), ('9', 'Tháng 9'),
            ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12'),
        ])
        _add_paragraph(
            f'(Kỳ theo dõi, đánh giá: {month_labels.get(evaluation.month, "")} năm {evaluation.year})',
            WD_ALIGN_PARAGRAPH.CENTER,
            italic=True,
        )

        # --- Personal info ---
        _add_paragraph(f'Họ và tên: {evaluation.employee_id.name or ""}')
        _add_paragraph(f'Chức vụ, chức danh: {evaluation.job_id.name or ""}')
        _add_paragraph(f'Đơn vị công tác: {evaluation.department_id.name or ""}')

        # --- I. Tiêu chí chung ---
        _add_paragraph('I. KẾT QUẢ THEO DÕI, ĐÁNH GIÁ THEO TIÊU CHÍ CHUNG', bold=True)

        table = doc.add_table(rows=2, cols=4)
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        headers = ['TT', 'Tiêu chí chấm điểm', 'Điểm tối đa', 'Điểm tự chấm']
        sub_headers = ['(1)', '(2)', '(3)', '(4)']
        for i, h in enumerate(headers):
            _set_cell_text(table.rows[0].cells[i], h, WD_ALIGN_PARAGRAPH.CENTER, bold=True)
            _set_cell_text(table.rows[1].cells[i], sub_headers[i], WD_ALIGN_PARAGRAPH.CENTER, italic=True)

        general_score_max = evaluation.general_score_max or 30.0
        task_score_max = evaluation.task_score_max or 70.0

        for idx, line in enumerate(evaluation.criteria_line_ids, 1):
            row = table.add_row()
            _set_cell_text(row.cells[0], str(idx), WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell_text(row.cells[1], line.criteria_id.name or '', WD_ALIGN_PARAGRAPH.LEFT)
            _set_cell_text(row.cells[2], _fmt_score(line.max_score), WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell_text(row.cells[3], _fmt_score(line.self_score), WD_ALIGN_PARAGRAPH.CENTER)

        total_row = table.add_row()
        total_row.cells[0].merge(total_row.cells[1])
        _set_cell_text(total_row.cells[0], 'Tổng cộng', WD_ALIGN_PARAGRAPH.CENTER, bold=True)
        _set_cell_text(total_row.cells[2], _fmt_score(general_score_max), WD_ALIGN_PARAGRAPH.CENTER, bold=True)
        _set_cell_text(total_row.cells[3], _fmt_score(evaluation.general_score), WD_ALIGN_PARAGRAPH.CENTER, bold=True)

        # --- II. Tổng hợp ---
        _add_paragraph('II. TỔNG HỢP KẾT QUẢ THEO DÕI, ĐÁNH GIÁ CÁN BỘ, CÔNG CHỨC, VIÊN CHỨC', bold=True)
        _add_paragraph(f'1. Điểm tiêu chí chung: {_fmt_score(evaluation.general_score)} điểm')
        _add_paragraph('2. Điểm tiêu chí kết quả thực hiện nhiệm vụ:')
        _add_paragraph(f'- a là điểm tỷ lệ phần trăm (%) về số lượng kết quả thực hiện nhiệm vụ: {_fmt_score(evaluation.pct_quantity)}%')
        _add_paragraph(f'- b là điểm tỷ lệ phần trăm (%) về chất lượng kết quả thực hiện nhiệm vụ: {_fmt_score(evaluation.pct_quality)}%')
        _add_paragraph(f'- c là điểm tỷ lệ phần trăm (%) về tiến độ kết quả thực hiện nhiệm vụ: {_fmt_score(evaluation.pct_progress)}%')
        if evaluation.is_manager:
            _add_paragraph(
                f'- d là điểm tỷ lệ phần trăm (%) về kết quả hoạt động của lĩnh vực được giao lãnh đạo, quản lý, phụ trách: {_fmt_score(evaluation.pct_field_result)}%'
            )
            _add_paragraph(
                f'- đ là điểm tỷ lệ phần trăm (%) về khả năng tổ chức triển khai thực hiện nhiệm vụ: {_fmt_score(evaluation.pct_organization)}%'
            )
            _add_paragraph(
                f'- e là điểm tỷ lệ phần trăm (%) về năng lực tập hợp, đoàn kết công chức thuộc phạm vi quản lý: {_fmt_score(evaluation.pct_team_cohesion)}%'
            )

        role_label = 'giữ chức vụ' if evaluation.is_manager else 'không giữ chức vụ'
        _add_paragraph(
            f'Điểm tiêu chí kết quả thực hiện nhiệm vụ (đối với CBCCVC {role_label}): {_fmt_score(evaluation.task_score)} / {_fmt_score(task_score_max)} điểm'
        )
        _add_paragraph(
            f'3. Tổng điểm theo dõi, đánh giá cán bộ, công chức, viên chức: {_fmt_score(evaluation.total_score)} điểm',
            bold=True,
        )
        _add_paragraph(f'4. Ưu điểm: {evaluation.strengths or ""}')
        _add_paragraph(f'5. Hạn chế, khuyết điểm: {evaluation.weaknesses or ""}')
        _add_paragraph(f'6. Ý kiến nhận xét của cấp có thẩm quyền theo dõi, đánh giá: {evaluation.authority_comment or ""}')

        # --- Signatures ---
        sig_table = doc.add_table(rows=1, cols=2)
        sig_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        for col_idx, title_text in enumerate([
            ('CBCCVC TỰ ĐÁNH GIÁ', '(Ký tên, ghi rõ họ tên)'),
            ('CẤP CÓ THẨM QUYỀN\nTHEO DÕI, ĐÁNH GIÁ', '(Ký tên, ghi rõ họ tên)'),
        ]):
            title, subtitle = title_text
            cell = sig_table.cell(0, col_idx)
            cell.text = ''
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run('....., ngày....tháng.....năm.....').italic = True
            p.add_run('\n')
            p.add_run(title).bold = True
            p.add_run('\n')
            p.add_run(subtitle).italic = True
            if col_idx == 0 and evaluation.employee_id.name:
                p.add_run(f'\n\n\n{evaluation.employee_id.name}')

        # Write to buffer
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        filename = f'Mau_01_{evaluation.employee_id.name}_{evaluation.month}_{evaluation.year}.docx'
        return request.make_response(
            buffer.getvalue(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
                ('Content-Disposition', content_disposition(filename)),
            ])

    @http.route('/bv_danh_gia/export_mau02/<int:record_id>', type='http', auth='user')
    def export_mau02_docx(self, record_id, **kwargs):
        """Export Mẫu 02 - Phiếu xếp loại chất lượng CBVC as DOCX."""
        record = request.env['bv.yearly.classification'].browse(record_id)
        if not record.exists():
            return request.not_found()

        try:
            from docx import Document
            from docx.shared import Pt
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.enum.table import WD_TABLE_ALIGNMENT
        except ImportError:
            return request.make_response(
                json.dumps({'error': 'Thư viện python-docx chưa được cài đặt.'}),
                headers=[('Content-Type', 'application/json')])

        doc = Document()
        style = doc.styles['Normal']
        style.font.name = 'Times New Roman'
        style.font.size = Pt(13)

        # Header
        table_header = doc.add_table(rows=1, cols=2)
        cell_left = table_header.cell(0, 0)
        cell_right = table_header.cell(0, 1)

        p = cell_left.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run('TÊN CƠ QUAN,\nTỔ CHỨC, ĐƠN VỊ\n───────')
        r.bold = True
        r.font.size = Pt(12)

        p = cell_right.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run('CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc\n───────────────')
        r.bold = True
        r.font.size = Pt(12)

        doc.add_paragraph()
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = title.add_run('PHIẾU XẾP LOẠI CHẤT LƯỢNG CÁN BỘ, CÔNG CHỨC, VIÊN CHỨC')
        r.bold = True
        r.font.size = Pt(14)

        sub = doc.add_paragraph()
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub.add_run(f'Năm {record.year}')

        doc.add_paragraph(f'Họ và tên: {record.employee_id.name or ""}')
        doc.add_paragraph(f'Chức vụ, chức danh: {record.job_id.name or ""}')
        doc.add_paragraph(f'Đơn vị công tác: {record.department_id.name or ""}')

        # I. Tổng hợp
        h1 = doc.add_paragraph()
        h1.add_run('I. TỔNG HỢP KẾT QUẢ THEO DÕI, ĐÁNH GIÁ').bold = True

        table = doc.add_table(rows=1, cols=3)
        table.style = 'Table Grid'
        for i, h in enumerate(['Tháng', 'Tổng điểm', 'Ghi chú']):
            cell = table.rows[0].cells[i]
            cell.text = h
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for r in p.runs:
                    r.bold = True

        month_data = [
            (1, record.month_1), (2, record.month_2), (3, record.month_3),
            ('Quý I', record.quarter_1_avg, 'TB cộng 3 tháng'),
            (4, record.month_4), (5, record.month_5), (6, record.month_6),
            ('Quý II', record.quarter_2_avg, 'TB cộng 3 tháng'),
            (7, record.month_7), (8, record.month_8), (9, record.month_9),
            ('Quý III', record.quarter_3_avg, 'TB cộng 3 tháng'),
            (10, record.month_10), (11, record.month_11), (12, record.month_12),
            ('Quý IV', record.quarter_4_avg, 'TB cộng 3 tháng'),
            ('TB cả năm', record.yearly_average, 'TB cộng 12 tháng'),
        ]

        for item in month_data:
            row = table.add_row()
            if len(item) == 3:
                row.cells[0].text = str(item[0])
                row.cells[1].text = f'{item[1]:.2f}'
                row.cells[2].text = item[2]
                for p in row.cells[0].paragraphs:
                    for r in p.runs:
                        r.bold = True
            else:
                row.cells[0].text = str(item[0])
                row.cells[1].text = str(item[1]) if item[1] > 0 else ''
                row.cells[2].text = ''
            for i in [0, 1]:
                for p in row.cells[i].paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        clf_labels = {
            'excellent': 'Hoàn thành xuất sắc nhiệm vụ',
            'good': 'Hoàn thành tốt nhiệm vụ',
            'fair': 'Hoàn thành nhiệm vụ',
            'poor': 'Không hoàn thành nhiệm vụ',
        }

        # II. Tự xếp loại
        doc.add_paragraph()
        h2 = doc.add_paragraph()
        h2.add_run('II. CBCCVC TỰ ĐÁNH GIÁ, XẾP LOẠI CHẤT LƯỢNG').bold = True
        for clf_key, clf_label in clf_labels.items():
            marker = '■' if record.self_classification == clf_key else '□'
            doc.add_paragraph(f'   {marker} {clf_label}')

        # III. Kết quả
        h3 = doc.add_paragraph()
        h3.add_run('III. KẾT QUẢ XẾP LOẠI CỦA CẤP CÓ THẨM QUYỀN').bold = True
        for clf_key, clf_label in clf_labels.items():
            marker = '■' if record.final_classification == clf_key else '□'
            doc.add_paragraph(f'   {marker} {clf_label}')

        # IV. Đề xuất
        h4 = doc.add_paragraph()
        h4.add_run('IV. ĐỀ XUẤT PHƯƠNG ÁN XỬ LÝ').bold = True
        doc.add_paragraph(record.proposed_action or '')

        # Signatures
        doc.add_paragraph()
        sig_table = doc.add_table(rows=4, cols=2)
        for col_idx, (t, s) in enumerate([
            ('CBCCVC TỰ XẾP LOẠI', '(Ký tên, ghi rõ họ tên)'),
            ('CẤP CÓ THẨM QUYỀN XẾP LOẠI', '(Ký tên, ghi rõ họ tên)'),
        ]):
            sig_table.cell(0, col_idx).text = '......, ngày .... tháng .... năm ....'
            for p in sig_table.cell(0, col_idx).paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p = sig_table.cell(1, col_idx).paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run(t).bold = True
            p = sig_table.cell(2, col_idx).paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run(s).italic = True

        p = sig_table.cell(3, 0).paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(f'\n\n\n{record.employee_id.name or ""}')

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        filename = f'Mau_02_{record.employee_id.name}_{record.year}.docx'
        return request.make_response(
            buffer.getvalue(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
                ('Content-Disposition', content_disposition(filename)),
            ])
