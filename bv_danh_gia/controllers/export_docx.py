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

        # --- Header ---
        table_header = doc.add_table(rows=1, cols=2)
        table_header.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell_left = table_header.cell(0, 0)
        cell_right = table_header.cell(0, 1)

        p_left = cell_left.paragraphs[0]
        p_left.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p_left.add_run('TÊN CƠ QUAN, TỔ CHỨC, ĐƠN VỊ')
        run.bold = True
        run.font.size = Pt(12)
        p_left.add_run(f'\n{evaluation.department_id.name or ""}').font.size = Pt(12)

        p_right = cell_right.paragraphs[0]
        p_right.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p_right.add_run('CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM')
        run.bold = True
        run.font.size = Pt(12)
        run2 = p_right.add_run('\nĐộc lập - Tự do - Hạnh phúc')
        run2.bold = True
        run2.font.size = Pt(12)
        p_right.add_run('\n──────────────').font.size = Pt(12)

        for cell in [cell_left, cell_right]:
            for border_name in ['top', 'bottom', 'left', 'right']:
                cell._element.xpath('.//w:tcPr', namespaces={
                    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
                })

        doc.add_paragraph()

        # --- Title ---
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title.add_run('PHIẾU THEO DÕI, ĐÁNH GIÁ CÁN BỘ, CÔNG CHỨC, VIÊN CHỨC')
        run.bold = True
        run.font.size = Pt(14)

        month_labels = dict([
            ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'),
            ('4', 'Tháng 4'), ('5', 'Tháng 5'), ('6', 'Tháng 6'),
            ('7', 'Tháng 7'), ('8', 'Tháng 8'), ('9', 'Tháng 9'),
            ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12'),
        ])
        subtitle = doc.add_paragraph()
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle.add_run(
            f'(Kỳ theo dõi, đánh giá: {month_labels.get(evaluation.month, "")} '
            f'năm {evaluation.year})')

        # --- Personal info ---
        doc.add_paragraph(f'Họ và tên: {evaluation.employee_id.name or ""}')
        doc.add_paragraph(f'Chức vụ, chức danh: {evaluation.job_id.name or ""}')
        doc.add_paragraph(f'Đơn vị công tác: {evaluation.department_id.name or ""}')

        # --- I. Tiêu chí chung ---
        h1 = doc.add_paragraph()
        run = h1.add_run('I. KẾT QUẢ THEO DÕI, ĐÁNH GIÁ THEO TIÊU CHÍ CHUNG')
        run.bold = True

        table = doc.add_table(rows=1, cols=6)
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        headers = ['TT', 'Tiêu chí chấm điểm', 'Điểm tối đa',
                   'Điểm tự chấm', 'Điểm TK chấm', 'Điểm cuối']
        for i, h in enumerate(headers):
            cell = table.rows[0].cells[i]
            cell.text = h
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for r in p.runs:
                    r.bold = True
                    r.font.size = Pt(11)

        for idx, line in enumerate(evaluation.criteria_line_ids, 1):
            row = table.add_row()
            row.cells[0].text = str(idx)
            row.cells[1].text = line.criteria_id.name or ''
            row.cells[2].text = str(line.max_score)
            row.cells[3].text = str(line.self_score)
            row.cells[4].text = str(line.dept_score)
            row.cells[5].text = str(line.final_score)
            for i in [0, 2, 3, 4, 5]:
                for p in row.cells[i].paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        total_row = table.add_row()
        total_row.cells[0].text = ''
        p = total_row.cells[1].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = p.add_run('Tổng cộng')
        run.bold = True
        total_row.cells[2].text = '30'
        total_row.cells[3].text = str(sum(evaluation.criteria_line_ids.mapped('self_score')))
        total_row.cells[4].text = str(sum(evaluation.criteria_line_ids.mapped('dept_score')))
        total_row.cells[5].text = str(evaluation.general_score)
        for i in [2, 3, 4, 5]:
            for p in total_row.cells[i].paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for r in p.runs:
                    r.bold = True

        # --- II. Tổng hợp ---
        doc.add_paragraph()
        h2 = doc.add_paragraph()
        run = h2.add_run('II. TỔNG HỢP KẾT QUẢ THEO DÕI, ĐÁNH GIÁ')
        run.bold = True

        doc.add_paragraph(f'1. Điểm tiêu chí chung: {evaluation.general_score}')
        doc.add_paragraph('2. Điểm tiêu chí kết quả thực hiện nhiệm vụ:')
        doc.add_paragraph(f'   - a: % Số lượng: {evaluation.pct_quantity}%')
        doc.add_paragraph(f'   - b: % Chất lượng: {evaluation.pct_quality}%')
        doc.add_paragraph(f'   - c: % Tiến độ: {evaluation.pct_progress}%')
        if evaluation.is_manager:
            doc.add_paragraph(f'   - d: % Kết quả lĩnh vực: {evaluation.pct_field_result}%')
            doc.add_paragraph(f'   - đ: % Tổ chức triển khai: {evaluation.pct_organization}%')
            doc.add_paragraph(f'   - e: % Đoàn kết: {evaluation.pct_team_cohesion}%')

        doc.add_paragraph(f'   Điểm KQTHNV: {evaluation.task_score:.2f} điểm')

        p_total = doc.add_paragraph()
        run = p_total.add_run(f'3. Tổng điểm: {evaluation.total_score:.2f} điểm')
        run.bold = True

        doc.add_paragraph(f'4. Ưu điểm: {evaluation.strengths or ""}')
        doc.add_paragraph(f'5. Hạn chế, khuyết điểm: {evaluation.weaknesses or ""}')
        doc.add_paragraph(
            f'6. Ý kiến nhận xét của cấp có thẩm quyền: '
            f'{evaluation.authority_comment or ""}')

        # --- Signatures ---
        doc.add_paragraph()
        sig_table = doc.add_table(rows=4, cols=2)
        sig_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        for col_idx, (title_text, subtitle_text) in enumerate([
            ('CBCCVC TỰ ĐÁNH GIÁ', '(Ký tên, ghi rõ họ tên)'),
            ('CẤP CÓ THẨM QUYỀN\nTHEO DÕI, ĐÁNH GIÁ', '(Ký tên, ghi rõ họ tên)'),
        ]):
            cell_date = sig_table.cell(0, col_idx)
            cell_date.text = '......, ngày .... tháng .... năm ....'
            for p in cell_date.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER

            cell_title = sig_table.cell(1, col_idx)
            p = cell_title.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(title_text)
            run.bold = True

            cell_sub = sig_table.cell(2, col_idx)
            p = cell_sub.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run(subtitle_text).italic = True

        cell_name = sig_table.cell(3, 0)
        p = cell_name.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(f'\n\n\n{evaluation.employee_id.name or ""}')

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
