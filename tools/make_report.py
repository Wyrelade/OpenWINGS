#!/usr/bin/env python3
"""Build an objdiff-format progress report (report.json, version 2) for decomp.dev.

OpenWINGS is a behavioural decomp, not a matching one, so objdiff itself is not used. The report
maps our own progress levels onto objdiff's measures:

  matched  (matched_code / matched_functions, fuzzy 100%) = verified: reproduced by recon/ code
           and passing a trace diff test (re/verified.csv)
  complete (complete_code)                                = named: symbol with evidence in
           re/symbols.csv (includes verified)

Inputs (all committed): re/functions.csv (the 975 game functions, VA + size, from the Ghidra
export), re/symbols.csv, re/verified.csv.  Output: build/report.json (or the path given).

usage: make_report.py [out.json]
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_VERSION = 2


def load_va_set(path, kind=None):
    out = {}
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            if kind and r.get('kind') != kind:
                continue
            out[int(r['va'], 16)] = r['name']
    return out


def measures(funcs, named, verified):
    total = sum(s for _, s in funcs)
    m_code = sum(s for va, s in funcs if va in verified)
    c_code = sum(s for va, s in funcs if va in named or va in verified)
    m_funcs = sum(1 for va, _ in funcs if va in verified)
    pct = lambda a, b: (100.0 * a / b) if b else 0.0
    return {
        'fuzzy_match_percent': pct(m_code, total),
        'total_code': str(total),
        'matched_code': str(m_code),
        'matched_code_percent': pct(m_code, total),
        'total_functions': len(funcs),
        'matched_functions': m_funcs,
        'matched_functions_percent': pct(m_funcs, len(funcs)),
        'complete_code': str(c_code),
        'complete_code_percent': pct(c_code, total),
        'total_units': 1,
        'complete_units': 0,
    }


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build', 'report.json')
    with open(os.path.join(ROOT, 're', 'functions.csv'), newline='') as f:
        funcs = [(int(r['va'], 16), int(r['size'])) for r in csv.DictReader(f)]
    fset = {va for va, _ in funcs}
    named = {va: n for va, n in load_va_set(os.path.join(ROOT, 're', 'symbols.csv'), 'func').items()
             if va in fset}
    verified = {va: n for va, n in load_va_set(os.path.join(ROOT, 're', 'verified.csv')).items()
                if va in fset}
    m = measures(funcs, named, verified)
    items = []
    for va, size in funcs:
        name = verified.get(va) or named.get(va) or f'FUN_{va:08x}'
        items.append({
            'name': name,
            'size': str(size),
            'fuzzy_match_percent': 100.0 if va in verified else 0.0,
            'metadata': {'virtual_address': str(va)},
            'address': str(va),
        })
    report = {
        'measures': m,
        'units': [{
            'name': 'wings140/game',
            'measures': m,
            'functions': items,
            'metadata': {'complete': False, 'module_name': 'WINGS.EXE'},
        }],
        'version': REPORT_VERSION,
        'categories': [{'id': 'game', 'name': 'Game code', 'measures': m}],
    }
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w') as f:
        json.dump(report, f, indent=1)
    print(f'{len(funcs)} functions, named {len(named)}, verified {len(verified)} -> {out}')


if __name__ == '__main__':
    main()
