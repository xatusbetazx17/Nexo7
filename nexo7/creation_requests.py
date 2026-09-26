"""Chat creation routing and bounded output validation, independent of model brand."""
import json
import re
from .scenarios import folded
from .creative import render, file
from .doc_export import export_document


def schema(kind):
    """Native constrained decoding; renderer validation remains authoritative."""
    if kind == 'drawing':
        return {'type':'object','properties':{
            'background':{'type':'string','pattern':'^#[0-9a-fA-F]{6}$'},
            'shapes':{'type':'array','minItems':1,'maxItems':4,'items':{
                'type':'object','properties':{
                    'type':{'type':'string','enum':['ellipse','rect','line']},
                    'box':{'type':'array','minItems':4,'maxItems':4,'items':{'type':'integer','minimum':0,'maximum':512}},
                    'color':{'type':'string','pattern':'^#[0-9a-fA-F]{6}$'}},
                'required':['type','box','color'],'additionalProperties':False}}},
            'required':['background','shapes'],'additionalProperties':False}
    return None


def intent(text):
    text = folded(text).strip(' ¿?!.')
    text = re.sub(r'^(?:please |por favor |can you |could you |would you |puedes |podrias )+', '', text)
    if re.match(r'^draw (?:conclusions|a conclusion|comparisons|a comparison|on|from|attention|lots)\b', text):
        return None
    if re.match(r'^(?:draw(?: me)?|sketch(?: me)?|paint(?: me)?|dibuja(?:me)?|dibujar|pinta(?:me)?)\b', text):
        return 'drawing'
    if re.match(r'^(?:make|create|generate|crea|creame|genera|generame|haz|hazme)\b', text):
        if re.search(r'\b(?:image|picture|photo|photograph|portrait|illustration|drawing|imagen|foto|fotografia|retrato|dibujo|ilustracion)\b', text[:100]):
            return 'drawing'
        if re.search(r'\b(?:music|melody|musica|melodia)\b', text[:100]):
            return 'music'
    if re.match(r'^(?:write|draft|make|create|generate|prepare|escribe|escribeme|redacta|redactame|crea|creame|haz|hazme|prepara|generar|genera)\b', text):
        if re.search(r'\b(?:document|docx|word|letter|report|essay|checklist|documento|carta|informe|ensayo)\b', text[:120]):
            return 'document'
    if text.startswith('/draw '):
        return 'drawing'
    if text.startswith('/document '):
        return 'document'
    if text.startswith('/music '):
        return 'music'
    return None


def instructions(kind):
    if kind == 'document':
        return ('Write only the requested document content, with a short # title and concise paragraphs. '
                'The application will export your text to a Word DOCX and a text file. Do not refuse file creation. '
                'Do not claim to have saved or sent anything. Use placeholders for missing personal details. '
                'Match the user language. Never invent citations or facts. Keep this draft short enough to finish.')
    if kind == 'music':
        return ('Compose a short instrumental melody. Output ONLY JSON: '
                '{"bpm":100,"instrument":"soft","notes":[{"pitch":60,"start":0,"duration":1}]} '
                'Use 4 to 8 notes, MIDI pitches 48-84, consecutive integer start beats and duration 1. '
                'No vocals. No explanation. The application renders your score as WAV and MIDI.')
    return ('You design simple illustrations. Output ONLY a JSON object, not prose or code. '
            'The application draws your shapes, so do not say you cannot draw. '
            'Canvas is 512x512. Use 2 to 4 shapes with integer coordinates from 0 to 512 and #RRGGBB colors. '
            'Allowed shape types: ellipse, rect, line. Each box is [left,top,right,bottom]. '
            'For ellipse and rect right>left and bottom>top. Example schema: '
            '{"background":"#ffffff","shapes":[{"type":"ellipse","box":[80,100,400,400],"color":"#ffcc00"}]} '
            'Represent the requested subject with these shapes. No explanation.')


def builtin(text):
    """Only exact simple requests use clearly labeled, hand-authored illustrations."""
    text = folded(text).strip(' ¿?!.')
    match = re.fullmatch(r'(?:please |por favor |can you |could you |puedes )*(?:draw(?: me)?|sketch(?: me)?|dibuja(?:me)?|/draw) (?:a |an |un |una )?(chicken|hen|pollo|gallina|hand|mano)(?: please| por favor)?', text)
    if not match:
        return None
    shapes = []
    def shape(kind, box, color):
        shapes.append(dict(type=kind, box=box, color=color))
    if match[1] in ('hand', 'mano'):
        skin = '#d99b73'
        shape('rect', [200,340,305,470], skin)
        for box in ([160,120,200,320],[210,70,250,320],[260,90,300,320],[310,140,350,320],[110,260,175,335]):
            shape('ellipse', box, skin)
        shape('ellipse', [155,225,350,400], skin)
        shape('line', [202,307,295,302], '#ae7051')
        shape('line', [200,325,230,360], '#ae7051')
    else:
        shape('line', [215,350,205,420], '#ce7a20')
        shape('line', [285,350,300,420], '#ce7a20')
        shape('line', [180,420,225,420], '#ce7a20')
        shape('line', [280,420,325,420], '#ce7a20')
        shape('ellipse', [85,200,200,280], '#e4a545')
        shape('ellipse', [125,195,350,375], '#f6c85c')
        shape('ellipse', [185,235,290,325], '#e4a545')
        for box in ([285,90,310,145],[309,80,333,140],[330,90,353,145]):
            shape('ellipse', box, '#d94646')
        shape('ellipse', [270,120,385,240], '#f6c85c')
        shape('ellipse', [343,157,357,171], '#232b36')
        shape('rect', [374,182,414,200], '#ce7a20')
        shape('ellipse', [344,213,365,247], '#d94646')
    return {'background':'#f4f7fb', 'shapes':shapes}


def create(kind, text):
    if kind == 'document':
        if re.search(r"\b(?:i (?:cannot|can't|am unable to) (?:create|generate|save|produce) (?:a |an |the |this )?(?:word|docx|document|file)|no puedo (?:crear|generar|guardar) (?:un |el |este )?(?:documento|archivo))\b", text[:200], re.I):
            raise ValueError('The model returned a refusal instead of document content')
        title = text.splitlines()[0].lstrip('# ').strip()[:160] or 'Nexo document'
        return [export_document({'title':title, 'content':text}),
                file('Nexo-document.txt', 'text/plain', text.encode('utf-8'))]
    clean = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.I)
    spec = json.loads(clean)
    if kind == 'drawing' and isinstance(spec, dict):
        # Common equivalent shape vocabulary from small models; all normalized
        # values still pass the renderer's strict coordinate/count/type limits.
        from .creative import number
        from PIL import ImageColor
        def normalized_color(value):
            if isinstance(value, str) and re.fullmatch(r'[a-zA-Z]{1,24}', value):
                try:
                    rgb = ImageColor.getrgb(value)
                    return '#%02x%02x%02x' % rgb
                except ValueError:
                    pass
            return value
        if 'background' in spec:
            spec['background'] = normalized_color(spec['background'])
        shapes = spec.get('shapes')
        if isinstance(shapes, list) and len(shapes) <= 128:
            for shape in shapes:
                if not isinstance(shape, dict):
                    continue
                shape['color'] = normalized_color(shape.get('color', shape.get('fill', '#000000')))
                if shape.get('type') == 'rectangle':
                    shape['type'] = 'rect'
                if shape.get('type') == 'circle':
                    center = shape.get('center', [shape.get('cx'), shape.get('cy')])
                    if not isinstance(center, list) or len(center) != 2:
                        raise ValueError('Circle center must contain x and y')
                    x, y = [number(v, 0, 1024, 'center') for v in center]
                    radius = number(shape.get('radius', shape.get('r')), 1, 512, 'radius')
                    shape['type'], shape['box'] = 'ellipse', [round(x-radius), round(y-radius), round(x+radius), round(y+radius)]
    return render({'kind':kind, 'spec':spec})['files']
