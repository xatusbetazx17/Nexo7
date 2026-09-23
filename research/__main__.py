"""python -m research --help (stdlib data commands; optional training dependencies)."""
import argparse
from .data import prepare


def main():
    parser = argparse.ArgumentParser(description="Nexo7 optional model research; separate from desktop inference")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("source"); p.add_argument("output")
    p = commands.add_parser("distill")
    p.add_argument("dataset"); p.add_argument("output")
    p.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    p.add_argument("--teacher", required=True); p.add_argument("--revision", required=True)
    p.add_argument("--output-license", required=True)
    p.add_argument("--limit", type=int, default=20)
    for command in ("train", "evaluate", "merge"):
        p = commands.add_parser(command)
        p.add_argument("--model", required=True, help="Local safetensors directory or Hugging Face repository")
        p.add_argument("--revision", help="Required immutable 40-character commit for remote models")
        p.add_argument("--output", required=True)
        p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
        p.add_argument("--threads", type=int, default=4)
        if command != "merge":
            p.add_argument("--dataset", required=True)
            p.add_argument("--max-length", type=int, default=512)
            p.add_argument("--seed", type=int, default=42)
        if command == "train":
            p.add_argument("--steps", type=int, default=100)
            p.add_argument("--rank", type=int, default=8)
            p.add_argument("--learning-rate", type=float, default=0.0002)
        else:
            p.add_argument("--adapter", required=command == "merge")
        if command == "evaluate":
            p.add_argument("--split", choices=("validation", "test"), default="validation")
            p.add_argument("--max-new-tokens", type=int, default=128)
    p = commands.add_parser("compare")
    p.add_argument("baseline"); p.add_argument("candidate"); p.add_argument("output")
    p.add_argument("--memory-gb", type=float, default=3.0)
    p.add_argument("--max-slowdown", type=float, default=1.1)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.source, args.output)
    elif args.command == "distill":
        from .distill import generate
        generate(args.dataset, args.output, args.endpoint, args.teacher, args.revision, args.output_license, args.limit)
    elif args.command == "compare":
        from .evaluate import compare
        compare(args.baseline, args.candidate, args.output, args.memory_gb, args.max_slowdown)
    else:
        from . import training
        getattr(training, args.command)(args)


if __name__ == "__main__":
    main()
