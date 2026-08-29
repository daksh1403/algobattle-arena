# AlgoBattle Sandbox CLI

## Quick Start

```bash
cd backend
source .venv/bin/activate
python sandbox/cli.py --problems
```

## Usage

### Run code directly
```bash
python sandbox/cli.py --lang python --code "print('hello')"
python sandbox/cli.py --lang python --file solution.py
```

### Solve problems
```bash
python sandbox/cli.py --solve fibonacci
python sandbox/cli.py --solve two-sum
python sandbox/cli.py --solve binary-search
```

### Interactive mode
```bash
python sandbox/cli.py --interactive
```

## Available Problems

| Problem | Difficulty | Description |
|---------|-----------|-------------|
| two-sum | Easy | Find indices that add to target |
| binary-search | Easy | Search in sorted array |
| fibonacci | Easy | Nth Fibonacci number |
| reverse-string | Easy | Reverse a string |
| palindrome | Easy | Check if palindrome |
| fizzbuzz | Easy | Classic FizzBuzz |

## Run Tests
```bash
cd backend
source .venv/bin/activate
python -m pytest sandbox/tests/test_sandbox.py -v
```

## Features
- Multi-language support (Python, C++, JavaScript, Java, Go, Rust)
- Time limit enforcement
- Memory limit enforcement
- Wrong answer detection
- Runtime error handling
- Compilation error detection
