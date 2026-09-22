"""Deterministic regression gate for reviewed packs; not a model intelligence benchmark."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nexo7.config import Config
from nexo7.engine import Engine
from nexo7.learning import Learning, validate_pack, privacy_warnings, FORMAT
from nexo7.store import Store


def main():
    root=Path(__file__).resolve().parents[1]
    pack=json.loads((root/'nexo7/knowledge/community.json').read_text(encoding='utf-8'))
    entries=validate_pack(pack)
    for entry in entries:
        if privacy_warnings(entry):raise ValueError('Review possible sensitive data in bundled pack')
    store=Store(':memory:')
    try:
        engine=Engine(Config(),store);learning=Learning(store)
        before=sum(bool(engine.chat(e['question'],private=True)['sources']) for e in entries)
        learning.import_pack(pack,True)
        after=0
        for entry in entries:
            response=engine.chat(entry['question'],private=True)
            assert response['sources'],entry['language']
            assert any(entry['answer'][:60] in s['text'] for s in response['sources'])
            after+=1
        for expression,expected in [('24.5 * 40','980.0'),('(18+6)/3','8.0'),('7*9','63')]:
            result=engine.chat('/calc '+expression,private=True)
            assert result['answer']==expected and result['stats']['model_calls']==0
        store.set_preferences({'use_learning':False})
        assert all(not engine.chat(e['question'],private=True)['sources'] for e in entries)
        report={'scope':'Reviewed pack schema/privacy heuristics, exact-question retrieval and calculator regression; not semantic accuracy, held-out generalization or weight training',
                'pack_examples':len(entries),'retrieval_before':before,'retrieval_after':after,'calculator_regressions_passed':3,'learning_disable_passed':True,'passed':True}
        output=root/'reports/learning-regression.json';output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report))
    finally:store.close()


if __name__=='__main__':main()
