import re
from datetime import date
from html import unescape
from pathlib import Path
import subprocess
import pymupdf
import pytest
from evaluation.generate_fixtures import create_pdf
from polisdiff.engine import load_catalogue, evaluate, evidence
from polisdiff.extraction import extract_pdf, render_evidence, PDFError
from polisdiff.localization import locate_on_page, trigger_range, quote_html
from polisdiff.models import Report, Status
from polisdiff.presentation import finding_details
from polisdiff.export import html_report
from polisdiff.retrieval import Retriever
from polisdiff.service import audit_document
from polisdiff.session import select_evidence, invalidate_result, input_identity

ROOT = Path(__file__).resolve().parents[1]
SUM = 'Общая страховая сумма составляет 60 000 000 сум.'
PAY = 'Страховое возмещение выплачивается в течение 9 рабочих дней после принятия решения страховщиком.'
NOTICE = 'Страхователю сообщается решение о страховом возмещении в течение 20 дней после письменного заявления.'


def analyzed(tmp_path, lines, *, rotation=0, applicable=date(2026, 3, 19)):
    path = tmp_path/'case.pdf'
    create_pdf(path, [lines])
    if rotation:
        with pymupdf.open(path) as pdf:
            pdf[0].set_rotation(rotation)
            data = pdf.tobytes()
    else:
        data = path.read_bytes()
    doc = extract_pdf(data, isolated=False)
    report = audit_document(doc, date(2026,10,10), applicable, Retriever('lexical'))
    return data, doc, report


@pytest.mark.parametrize('rule_id,text,matched', [
    ('OSAGO_SUM', SUM, '60 000 000 сум'),
    ('OSAGO_PAYMENT', PAY, '9 рабочих дней'),
    ('OSAGO_DECISION_NOTICE', NOTICE, '20 дней'),
    ('OSAGO_SUM', 'Sugʻurta summasi 60 000 000 soʻm.', '60 000 000 soʻm'),
    ('OSAGO_SUM', 'Sugʼurta summasi 60 000 000 soʼm.', '60 000 000 soʼm'),
    ('OSAGO_SUM', 'Суғурта суммаси 60 000 000 сўм.', '60 000 000 сўм'),
    ('OSAGO_PAYMENT', "Sug‘urta tovoni qaror qabul qilingan kundan 9 ish kuni ichida amalga oshiriladi.", '9 ish kuni'),
    ('OSAGO_SUM', 'Общая страховая сумма составляет 60\u00a0000\u00a0000 сум.', '60'),
])
def test_exact_original_geometry(tmp_path, rule_id, text, matched):
    data, doc, report = analyzed(tmp_path, [text])
    finding = next(f for f in report.findings if f.rule_id == rule_id)
    assert finding.status == Status.POTENTIAL_CONFLICT
    ev = finding.evidence[0]
    with pymupdf.open(stream=data, filetype='pdf') as pdf:
        loc = locate_on_page(pdf[0], finding, ev)
        assert loc.state == 'precise'
        assert matched in ev.quote[loc.start:loc.end]
        # Check visible words at coordinates independently of evidence offsets.
        visible = ' '.join(pdf[0].get_textbox(pymupdf.Rect(r)) for r in loc.rectangles)
        assert '60' in visible if rule_id == 'OSAGO_SUM' else matched in visible
        assert all(r != ev.bbox for r in loc.rectangles)


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_rotation_preserves_geometry_and_bounded_render(tmp_path, rotation):
    data, doc, report = analyzed(tmp_path, [SUM], rotation=rotation)
    result = render_evidence(data, doc, report.findings[0], report.findings[0].evidence[0])
    assert result['location']['state'] == 'precise'
    pix = pymupdf.Pixmap(result['png'])
    assert max(pix.width, pix.height) <= 1401
    assert (pix.width > pix.height) == (rotation in {90,270})


def test_identical_numbers_do_not_select_first_page_occurrence(tmp_path):
    data, doc, report = analyzed(tmp_path, ['Премия по отдельному продукту: 60 000 000 сум.', SUM,
        'Другая справочная сумма: 60 000 000 сум.'])
    f = report.findings[0]
    with pymupdf.open(stream=data, filetype='pdf') as pdf:
        loc = locate_on_page(pdf[0], f, f.evidence[0])
        assert loc.state == 'precise'
        occurrences = pdf[0].search_for('60 000 000 сум')
        assert len(occurrences) == 3
        assert pymupdf.Rect(loc.rectangles[0]).intersects(occurrences[1])
        assert not pymupdf.Rect(loc.rectangles[0]).intersects(occurrences[0])
        assert not pymupdf.Rect(loc.rectangles[0]).intersects(occurrences[2])


def test_multiline_value_uses_separate_line_boxes(tmp_path):
    # The shared paragraph builder folds newlines; create two actual PDF lines.
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from evaluation.generate_fixtures import font_path
    path = tmp_path/'multiline.pdf'
    pdfmetrics.registerFont(TTFont('MultilineFont',str(font_path())))
    c = canvas.Canvas(str(path),pagesize=(595,842))
    c.setFont('MultilineFont',10)
    c.drawString(40,790,'Общая страховая сумма составляет 60 000')
    c.drawString(40,774,'000 сум.')
    c.save()
    data = path.read_bytes()
    doc = extract_pdf(data,isolated=False)
    report = audit_document(doc,date(2026,10,10),date(2026,3,19),Retriever('lexical'))
    f = report.findings[0]
    with pymupdf.open(stream=data, filetype='pdf') as pdf:
        loc = locate_on_page(pdf[0], f, f.evidence[0])
        assert loc.state == 'precise' and len(loc.rectangles) == 2
        assert '60 000\n000 сум' in f.evidence[0].quote[loc.start:loc.end]
        assert loc.rectangles[0][3] < loc.rectangles[1][1]


def test_columns_and_table_reading_order_must_match(tmp_path):
    path = tmp_path/'layout.pdf'
    create_pdf(path, [[SUM]])
    with pymupdf.open(path) as pdf:
        page = pdf[0]
        page.insert_text((330,400), '60 000 000', fontsize=11)
        page.insert_text((50,400), 'Table: separate value', fontsize=11)
        data = pdf.tobytes()
    doc = extract_pdf(data, isolated=False)
    report = audit_document(doc,date(2026,10,10),date(2026,3,19),Retriever('lexical'))
    f = report.findings[0]
    with pymupdf.open(stream=data,filetype='pdf') as pdf:
        loc = locate_on_page(pdf[0],f,f.evidence[0])
        assert loc.state == 'precise'
        assert all(r[1] < 200 for r in loc.rectangles)


@pytest.mark.parametrize('damage', ['quote','offset','empty','number'])
def test_mismatched_evidence_never_draws_rectangles(tmp_path,damage):
    data, doc, report = analyzed(tmp_path,[SUM])
    f = report.findings[0]
    ev = f.evidence[0].model_copy(deep=True)
    if damage == 'quote': ev.quote = ev.quote.replace('60','80')
    if damage == 'offset': ev.start += 1
    if damage == 'empty': ev.quote = ''
    if damage == 'number': ev.extracted_value = 80000000
    with pymupdf.open(stream=data,filetype='pdf') as pdf:
        loc = locate_on_page(pdf[0],f,ev)
        assert loc.state != 'precise' and not loc.rectangles


@pytest.mark.parametrize('applicable', [None, date(2010,1,1), date(2024,9,6)])
def test_date_uncertainty_and_historical_reference_are_preserved(tmp_path, applicable):
    data, doc, report = analyzed(tmp_path,[SUM], applicable=applicable)
    f = report.findings[0]
    d = finding_details(report,f,'en')
    assert d['draft'] is None
    if applicable is None or applicable.year == 2010:
        assert f.status == Status.UNVERIFIABLE and f.expected_value is None
        assert not d['comparable'] and 'contract change is not recommended' in d['remediation']
    else:
        assert f.expected_value == 40000000 and d['comparable']
        assert '40 000 000' in d['reference']


@pytest.mark.parametrize('text,code', [
    (PAY.replace('страховщиком','суда'), None),
    (SUM+' Общая страховая сумма: 80 000 000 сум.', 'competing_or_ambiguous_terms'),
    ('Договор регулируется правилами №141.', 'incorporation_by_reference'),
])
def test_blocking_reasons_prevent_contract_remediation(tmp_path,text,code):
    _,_,report = analyzed(tmp_path,[text])
    f = report.findings[1] if 'суда' in text else report.findings[0]
    assert f.status == Status.UNVERIFIABLE
    if code: assert code in f.uncertainty
    d = finding_details(report,f,'en')
    assert d['draft'] is None and not d['comparable']
    assert 'not recommended' in d['remediation']


def test_appendix_is_locatable_but_never_contract_remediation(tmp_path):
    data, doc, report = analyzed(tmp_path,[SUM])
    for p in doc.passages: p.section = 'regulatory_appendix'
    f = evaluate(load_catalogue()[1][0],doc,doc.passages,date(2026,3,19),date(2026,10,10))
    report.findings[0] = f
    d = finding_details(report,f,'en')
    assert f.status == Status.UNVERIFIABLE and 'appendix_only' in f.uncertainty
    assert not d['comparable'] and d['draft'] is None
    assert 'incorporated' in ' '.join(d['verification']) or 'appendix' in ' '.join(d['verification'])
    assert render_evidence(data,doc,f,f.evidence[0])['location']['state'] == 'precise_unavailable'


@pytest.mark.parametrize('rule_index', [0,1,2])
@pytest.mark.parametrize('status', list(Status))
def test_guidance_for_every_rule_status_and_html_json_consistency(tmp_path,rule_index,status):
    _,_,report = analyzed(tmp_path,[SUM,PAY,NOTICE])
    f = report.findings[rule_index]
    f.status = status
    if status in {Status.NOT_FOUND,Status.UNVERIFIABLE}:
        f.evidence=[]
    if status == Status.UNVERIFIABLE: f.uncertainty=['unreadable_pages']
    before=report.model_dump_json()
    d=finding_details(report,f,'en')
    html=html_report(report,'en')
    for key in ['checked','found','reference','reason','remediation','verification_state']:
        assert d[key] in unescape(html)
    assert all(v in unescape(html) for v in d['verification'])
    assert d['human_legal_review'] and d['draft'] is None
    assert Report.model_validate_json(before).model_dump_json() == before
    assert report.model_dump_json() == before
    if status == Status.MATCH_FOUND: assert 'No change' in d['remediation']
    if status == Status.NOT_FOUND: assert 'insert a clause' in d['remediation']
    if status == Status.UNVERIFIABLE:
        assert d['remediation_kind'] == 'Technical document review'
        assert 'OCR is unsupported' in ' '.join(d['verification'])
    if status == Status.POTENTIAL_CONFLICT: assert 'If the date' in d['remediation']


def test_escaped_highlight_and_old_report_readability():
    report=Report.model_validate_json((ROOT/'evaluation/reports/lexical/regression_evaluation/ru-Cyrl_match.json').read_bytes())
    f=report.findings[0]
    ev=f.evidence[0]
    ev.quote='<script>evil()</script> '+SUM+' & <img src=x>'
    ev.extracted_value=60000000
    marked=quote_html(ev,f)
    assert '<mark>60 000 000 сум</mark>' in marked
    assert '<script>' not in marked and '<img' not in marked
    assert '<mark class="ctx">страховая сумма</mark>' in marked  # subject highlighted next to the value
    assert ev.quote == unescape(re.sub(r'<mark[^>]*>|</mark>', '', marked))
    assert finding_details(report,f)['draft'] is None


def test_evidence_render_timeout_and_stale_selection(tmp_path,monkeypatch):
    import polisdiff.extraction as extraction
    data,doc,report=analyzed(tmp_path,[SUM])
    f=report.findings[0]
    ev=f.evidence[0]
    with pytest.raises(PDFError,match='Stale'):
        render_evidence(data+b'changed',doc,f,ev)
    def timeout(*args,**kwargs):
        assert kwargs['timeout']==15
        raise subprocess.TimeoutExpired(args[0],15)
    monkeypatch.setattr(extraction.subprocess,'run',timeout)
    with pytest.raises(PDFError,match='timed out'):
        render_evidence(data,doc,f,ev)
    identity=input_identity(data,report.audit_date,report.applicable_date,'lexical')
    state={'report':report,'input_fingerprint':identity,'preview':b'old'}
    select_evidence(state,ev.page,ev.passage_id,f.rule_id)
    assert 'preview' not in state
    invalidate_result(state,None)
    assert not state


def test_damaged_or_unsupported_text_never_suggests_contract_edit(tmp_path):
    _, doc, _ = analyzed(tmp_path,['Unreadable or unsupported source text without identifiable insurance conditions.'])
    doc.pages[0].readable=False
    doc.warnings=['Page 1: insufficient or damaged text; OCR is not enabled. Manual review required.']
    report=audit_document(doc,date(2026,10,10),date(2026,3,19),Retriever('lexical'))
    for f in report.findings:
        assert f.status==Status.UNVERIFIABLE and not f.evidence
        d=finding_details(report,f,'en')
        assert d['draft'] is None and d['remediation_kind']=='Technical document review'
        assert 'not grounds to edit' in ' '.join(d['verification'])


def test_rotated_text_direction_abstains_from_box_highlight(tmp_path):
    pdf=pymupdf.open()
    page=pdf.new_page()
    page.insert_text((150,700),"Sug'urta summasi 60 000 000 so'm.",rotate=90,fontsize=12)
    data=pdf.tobytes()
    pdf.close()
    doc=extract_pdf(data,isolated=False)
    report=audit_document(doc,date(2026,10,10),date(2026,3,19),Retriever('lexical'))
    f=report.findings[0]
    assert f.status==Status.POTENTIAL_CONFLICT
    with pymupdf.open(stream=data,filetype='pdf') as pdf:
        loc=locate_on_page(pdf[0],f,f.evidence[0])
        assert loc.state=='precise_unavailable' and not loc.rectangles
        assert loc.start is not None  # Text offsets still support a marked quote.


def test_overlapping_duplicate_text_abstains(tmp_path):
    pdf=pymupdf.open()
    page=pdf.new_page()
    for _ in range(2):
        page.insert_text((40,80),"Sug'urta summasi 60 000 000 so'm.",fontsize=12)
    data=pdf.tobytes()
    pdf.close()
    doc=extract_pdf(data,isolated=False)
    report=audit_document(doc,date(2026,10,10),date(2026,3,19),Retriever('lexical'))
    f=report.findings[0]
    assert f.evidence
    with pymupdf.open(stream=data,filetype='pdf') as pdf:
        for ev in f.evidence:
            loc=locate_on_page(pdf[0],f,ev)
            assert loc.state!='precise' and not loc.rectangles


def test_ambiguous_values_and_lossy_normalization_have_no_text_mark(tmp_path):
    _,_,report=analyzed(tmp_path,[SUM])
    f=report.findings[0]
    ev=f.evidence[0].model_copy(deep=True)
    ev.quote='Общая страховая сумма 60 000 000 сум и 80 000 000 сум.'
    assert trigger_range(f,ev) is None
    ev.quote='Общая страховая сумма ６０ ０００ ０００ сум.'
    assert trigger_range(f,ev) is None


def test_incomplete_old_report_does_not_suggest_numeric_contract_correction(tmp_path):
    _,_,report=analyzed(tmp_path,[SUM])
    f=report.findings[0]
    report.applicable_date=None
    d=finding_details(report,f,'en')
    assert not d['comparable'] and 'not recommended' in d['remediation'] and d['draft'] is None


def test_image_blocks_cannot_shift_text_geometry_identifiers(tmp_path):
    # blocks/rawdict use different image-preservation defaults; numeric block
    # identifiers cannot be used to join these two APIs.
    from io import BytesIO
    from PIL import Image
    image=BytesIO()
    Image.new('RGB',(4,4),'white').save(image,format='PNG')
    with pymupdf.open() as pdf:
        page=pdf.new_page()
        page.insert_image(pymupdf.Rect(20,20,30,30),stream=image.getvalue())
        page.insert_text((40,80),"Sug'urta summasi 60 000 000 so'm.",fontsize=12)
        blocks=[b for b in page.get_text('blocks',sort=True) if b[6]==0]
        raw=[b for b in page.get_text('rawdict')['blocks'] if b['type']==0]
        assert blocks[0][5] != raw[0]['number']
        data=pdf.tobytes()
    doc=extract_pdf(data,isolated=False)
    report=audit_document(doc,date(2026,10,10),date(2026,3,19),Retriever('lexical'))
    f=report.findings[0]
    with pymupdf.open(stream=data,filetype='pdf') as pdf:
        loc=locate_on_page(pdf[0],f,f.evidence[0])
        assert loc.state=='precise'
        assert '60 000 000' in pdf[0].get_textbox(pymupdf.Rect(loc.rectangles[0]))
