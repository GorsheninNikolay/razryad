#!/usr/bin/env python3
"""Load generated fixtures. Uses a portable JSON snapshot for demo and CI."""
from pathlib import Path
import json
from generate import generate, check

def main():
 p=Path(__file__).parent/'data'/'fixtures.json'
 if not p.exists():
  p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(generate(42),ensure_ascii=False,indent=2),encoding='utf-8')
 data=json.loads(p.read_text(encoding='utf-8')); check(data)
 print('seed: idempotent fixture snapshot validated')
 for k,v in data['meta']['counts'].items(): print(f'{k}: {v}')
if __name__=='__main__':
 from load import main as load_database
 load_database()
