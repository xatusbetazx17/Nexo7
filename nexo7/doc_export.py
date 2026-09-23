"""Bounded macro-free DOCX export using only local standard-library code."""
import base64
import io
import re
import zipfile
from xml.sax.saxutils import escape


def export_document(body):
    title, text = body.get('title'), body.get('content')
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
        raise ValueError('Use a document title of 1–160 characters')
    if not isinstance(text, str) or not 1 <= len(text.encode('utf-8', errors='surrogatepass')) <= 200000:
        raise ValueError('Document text must contain 1–200000 UTF-8 bytes')
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]', title + text):
        raise ValueError('Unsupported control character in document')
    def paragraph(value, style=''):
        props = '<w:pPr><w:pStyle w:val="' + style + '"/></w:pPr>' if style else ''
        return '<w:p>' + props + '<w:r><w:t xml:space="preserve">' + escape(value) + '</w:t></w:r></w:p>'
    paragraphs = [paragraph(title.strip(), 'Title')]
    for line in text.splitlines():
        heading = re.match(r'^(#{1,3})\s+(.+)$', line)
        paragraphs.append(paragraph(heading[2], 'Heading'+str(len(heading[1]))) if heading else paragraph(line))
    ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="'+ns+'"><w:body>'+''.join(paragraphs)+'<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'
    types = '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'
    rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    styles = '<w:styles xmlns:w="'+ns+'"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:sz w:val="22"/></w:rPr></w:style>'
    for name, size in [('Title',36),('Heading1',32),('Heading2',28),('Heading3',24)]:
        styles += '<w:style w:type="paragraph" w:styleId="'+name+'"><w:name w:val="'+name+'"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="'+str(size)+'"/></w:rPr></w:style>'
    styles += '</w:styles>'
    relationships = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in [('[Content_Types].xml',types),('_rels/.rels',rels),('word/document.xml',xml),('word/styles.xml',styles),('word/_rels/document.xml.rels',relationships)]:
            archive.writestr(name, value.encode('utf-8'))
    return {'name':'Nexo-document.docx','mime':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'data':base64.b64encode(output.getvalue()).decode('ascii'), 'notice':'Created locally. Review content and formatting in your word processor; no macros, remote links or model call.'}
