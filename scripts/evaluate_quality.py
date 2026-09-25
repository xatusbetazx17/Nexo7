"""Small reproducible diagnostic, not a general intelligence benchmark. No generated code execution."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nexo7 import native_runtime as native
from nexo7.providers import NativeProvider

CASES=[
 ('definition_en','What is a chicken? Answer in one simple sentence.',('bird','poultry'),('black and white','native to europe','mammal')),
 ('definition_es','¿Qué es una gallina? Responde en una oración sencilla.',('ave',),('mamífer','siempre blanca')),
 ('deduction','All zorps are blue. Luma is a zorp. What color is Luma? Answer just the color.',('blue',),()),
 ('ordering','Ana is older than Ben. Ben is older than Cam. Who is youngest? Answer just the name.',('cam',),()),
 ('arithmetic','A box has 6 bags with 7 marbles each. You remove 5 marbles. How many remain? Answer just the number.',('37',),()),
 ('arithmetic_es','Hay 5 cajas con 8 libros cada una. Se regalan 6 libros. ¿Cuántos quedan? Responde solo el número.',('34',),()),
 ('unknown','What is the current population of the fictional planet Xorvila? If it cannot be known, say UNKNOWN.',('unknown',),()),
 ('json','Return only JSON with name Ana and age 30. Use keys name and age.',(),()),
 ('code','Write only Python code defining square(n) that returns n*n.',(),()),
 ('instruction','Reply with exactly these two words: amber maple',('amber maple',),()),
]


def grade(name,text):
    import ast,re
    value=re.sub(r'^```[^\n]*\n|\n```\s*$','',text.strip()).strip()
    if name=='json':
        try:return json.loads(value)=={'name':'Ana','age':30}
        except ValueError:return False
    if name=='code':
        try:
            tree=ast.parse(value);func=tree.body[0]
            return (len(tree.body)==1 and isinstance(func,ast.FunctionDef) and func.name=='square' and
                [a.arg for a in func.args.args]==['n'] and len(func.body)==1 and isinstance(func.body[0],ast.Return) and
                ast.dump(func.body[0].value)==ast.dump(ast.parse('n*n',mode='eval').body))
        except (SyntaxError,AttributeError,IndexError):return False
    if name.startswith('definition_'):return None  # Needs semantic human review; keyword presence is insufficient.
    case=next(c for c in CASES if c[0]==name)
    if name in ('deduction','ordering','arithmetic','arithmetic_es','unknown','instruction'):
        return value.casefold().strip(' .!\n')==case[2][0]
    return any(w in value.casefold() for w in case[2]) and not any(w in value.casefold() for w in case[3])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',choices=['qwen3.5:0.8b','qwen3.5:2b','qwen2.5:1.5b','lfm2-vl:450m'],required=True)
    parser.add_argument('--budget-gb',type=float,default=3)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();limit=int(args.budget_gb*1e9)
    if not 1_500_000_000<=limit<=12_000_000_000:parser.error('Budget must be 1.5–12 GB')
    original=native.native_plan
    def plan(cpu_only=False,performance='balanced'):
        value=original(True,'balanced')
        if limit>value['ram_limit_bytes']:raise ValueError('Requested benchmark budget exceeds measured safe budget')
        model=native.CATALOG['models'][args.model]
        value.update(ram_limit_bytes=limit,low_memory=True,profiles=[dict(model=args.model,minimum_budget=limit,max_download=model['size'],context_tokens=4096,download_bytes=model['size'])])
        return value
    args.data_dir.mkdir(parents=True,exist_ok=True)
    report={'model':args.model,'budget_bytes':limit,'case_count':len(CASES),'scope':'CPU, 4096 context; literal diagnostic grading, not a benchmark of factual accuracy in general','cases':[]}
    with patch.object(native,'native_plan',side_effect=plan):
        cfg,actual=native.start_native(str(args.data_dir/'quality.sqlite'),cpu_only=True,performance='fast',emit=lambda message:print(message,flush=True))
    try:
        report['guard']=actual['guard'];report['enforced_limit_bytes']=actual['enforced_limit_bytes']
        provider=NativeProvider(cfg)
        for name,prompt,*_ in CASES:
            started=time.perf_counter()
            try:
                answer=provider.complete('Answer accurately and concisely. Follow the requested output format. Admit uncertainty.',[{'role':'user','content':prompt}],[],cfg.model,128)
                text=answer.text;passed=grade(name,text) if not answer.incomplete else False;error=None
            except Exception as exc:text='';passed=False;error=str(exc)
            report['cases'].append(dict(id=name,prompt=prompt,answer=text,passed=passed,error=error,seconds=round(time.perf_counter()-started,3)))
            print(name,passed,flush=True)
    finally:native.stop_native(cfg)
    report['passed_count']=sum(r['passed'] is True for r in report['cases'])
    report['automatically_scored_cases']=sum(r['passed'] is not None for r in report['cases'])
    report['manual_review_required']=['definition_en','definition_es']
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'model':args.model,'passed':report['passed_count'],'total':len(CASES)}))
if __name__=='__main__':main()
