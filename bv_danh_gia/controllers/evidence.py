import base64
from odoo import http
from odoo.http import request, Response


EVIDENCE_FIELDS = {
    'quantity', 'quality', 'progress',
    'field_result', 'organization', 'team_cohesion',
}


class EvidenceController(http.Controller):
    """Serve evidence PDF files for monthly evaluations.

    URL: /bv_danh_gia/monthly_evaluation/<id>/evidence/<field_name>
    Access is governed by the record-level ir.rule on bv.monthly.evaluation —
    if the current user cannot read the record, a 403 is returned.
    """

    @http.route(
        '/bv_danh_gia/monthly_evaluation/<int:eval_id>/evidence/<string:field_name>',
        type='http', auth='user', methods=['GET'],
    )
    def download_evidence(self, eval_id, field_name, **kwargs):
        # Validate field name to prevent arbitrary field access
        if field_name not in EVIDENCE_FIELDS:
            return Response('File không hợp lệ.', status=400)

        binary_field = f'evidence_{field_name}'
        name_field = f'evidence_{field_name}_name'

        # Access-checked read (record rules apply automatically via user env)
        eval_rec = request.env['bv.monthly.evaluation'].browse(eval_id)
        if not eval_rec.exists():
            return Response('Không tìm thấy phiếu đánh giá.', status=404)

        data = getattr(eval_rec, binary_field, None)
        filename = getattr(eval_rec, name_field, None) or f'minh_chung_{field_name}.pdf'

        if not data:
            return Response('Chưa có file minh chứng.', status=404)

        try:
            file_bytes = base64.b64decode(data)
        except Exception:
            return Response('File bị lỗi.', status=500)

        return request.make_response(
            file_bytes,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'inline; filename="{filename}"'),
                ('Content-Length', str(len(file_bytes))),
            ],
        )
