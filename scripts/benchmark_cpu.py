"""Standalone Linux llama.cpp CPU check, NOT the Docker-backed desktop runtime."""
import argparse
import json
import sys
from pathlib import Path
import re
import resource
import subprocess
import tempfile
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--output', default='reports/real-cpu.json')
    args = p.parse_args()
    cases = [
        ('spanish', 'Responde en español: escribe exactamente dos consejos breves para organizar archivos.'),
        ('english', 'In English, give exactly two short tips for organizing files.'),
        ('python', 'Write only a Python function square(n) that returns n multiplied by itself.'),
        ('arithmetic', 'Calculate 24.5 * 40. Answer with only the number.'),
    ]
    results = []
    def limit():
        resource.setrlimit(resource.RLIMIT_AS, (8_000_000_000, 8_000_000_000))
    with tempfile.TemporaryDirectory() as tmp:
        for name, prompt in cases:
            rss = Path(tmp) / (name + '.rss')
            command = [str(Path(args.runtime).resolve()), 'cli', '-m', str(Path(args.model).resolve()),
                       '-t', '2', '-tb', '2', '-c', '2048', '-n', '192', '-ngl', '0',
                       '--reasoning', 'off', '--single-turn', '--color', 'off', '--seed', '42', '--perf', '-p', prompt]
            start = time.monotonic()
            worker = 'import subprocess,resource,sys,pathlib; r=subprocess.call(sys.argv[2:]); pathlib.Path(sys.argv[1]).write_text(str(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)); sys.exit(r)'
            completed = subprocess.run([sys.executable, '-c', worker, str(rss), *command],
                                       capture_output=True, text=True, timeout=240, preexec_fn=limit)
            rates = re.search(r'Prompt: ([\d.]+) t/s \| Generation: ([\d.]+) t/s', completed.stdout)
            answer = completed.stdout.split('> ' + prompt, 1)[-1].split('[ Prompt:', 1)[0].strip()
            results.append({'case': name, 'prompt': prompt, 'returncode': completed.returncode,
                            'wall_seconds_including_load': round(time.monotonic() - start, 3),
                            'peak_rss_kib': int(rss.read_text().strip().splitlines()[-1]),
                            'prompt_tokens_per_second': float(rates[1]) if rates else None,
                            'generation_tokens_per_second': float(rates[2]) if rates else None,
                            'answer': answer, 'stderr': completed.stderr[-2000:]})
    result = {'scope': 'Standalone official llama.cpp CPU CLI; not full Nexo/Docker integration or a physical 8 GB PC',
              'virtual_address_space_limit_bytes': 8_000_000_000, 'threads': 2, 'context_tokens': 2048,
              'maximum_output_tokens': 192, 'reasoning': 'off', 'model': Path(args.model).name,
              'cpu': next((x.split(':', 1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')), 'unknown'),
              'results': results}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))
    if any(r['returncode'] for r in results):
        raise SystemExit(1)

if __name__ == '__main__':
    main()
