#!/usr/bin/env python3
"""scripts/fetch_arxiv.py

Fetch the latest arXiv papers for a query and write arxiv_data.json

Usage (local):
  python3 scripts/fetch_arxiv.py --query "cat:cs.AI OR all:machine learning" --max 20

When run from GitHub Actions the workflow sets `ARXIV_QUERY` and `MAX_RESULTS`.
"""
from __future__ import annotations
import argparse
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import ssl
import sys

ATOM = '{http://www.w3.org/2005/Atom}'


def _build_ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        try:
            return ssl.create_default_context()
        except Exception:
            return None


def fetch(query: str, max_results: int = 20):
    encoded = urllib.parse.quote(query)
    url = (
        'https://export.arxiv.org/api/query?'
        f'search_query={encoded}&start=0&max_results={max_results}'
        '&sortBy=lastUpdatedDate&sortOrder=descending'
    )
    req = urllib.request.Request(url, headers={'User-Agent': 'arXiv-fetcher/1.0'})
    ctx = _build_ssl_context()
    # If ctx is None, urllib will ignore the context parameter on some platforms; keep as is
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        raw = r.read()
    root = ET.fromstring(raw)
    papers = []
    for entry in root.findall(ATOM + 'entry'):
        def _text(el):
            return el.text.strip().replace('\n', ' ') if el is not None and el.text else ''

        id_url = _text(entry.find(ATOM + 'id'))
        title = _text(entry.find(ATOM + 'title'))
        summary = _text(entry.find(ATOM + 'summary'))
        updated = _text(entry.find(ATOM + 'updated'))
        authors = [a.find(ATOM + 'name').text for a in entry.findall(ATOM + 'author') if a.find(ATOM + 'name') is not None]
        pdf = id_url.replace('/abs/', '/pdf/')
        if pdf and not pdf.endswith('.pdf'):
            pdf = pdf + '.pdf'
        papers.append({'id': id_url, 'title': title, 'summary': summary, 'authors': authors, 'updated': updated, 'pdf': pdf})
    return papers


def write_output(path: str, query: str, papers: list):
    out = {'query': query, 'fetched_at': int(time.time()), 'papers': papers}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser()
    p.add_argument('--query', default=None, help='arXiv query string (raw, not URL-encoded)')
    p.add_argument('--max', type=int, default=20, help='max results')
    p.add_argument('--out', default='docs/arxiv_data.json', help='output JSON path')
    args = p.parse_args(argv)

    # allow environment-driven defaults (used by CI workflows)
    import os
    query = args.query or os.environ.get('ARXIV_QUERY') or 'all:machine learning'
    max_results = int(os.environ.get('MAX_RESULTS', args.max))

    print(f'Fetching arXiv for query: {query} (max={max_results})')
    try:
        papers = fetch(query, max_results)
        # ensure output directory exists
        out_path = args.out
        import os
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        write_output(out_path, query, papers)
        # also write a copy at repo root for local preview convenience
        try:
            if out_path.startswith('docs/'):
                write_output('arxiv_data.json', query, papers)
        except Exception:
            pass
        print(f'Wrote {out_path} with {len(papers)} papers')
    except Exception as e:
        print('Error fetching arXiv:', str(e))
        fallback = {'query': query, 'fetched_at': int(time.time()), 'error': str(e), 'papers': []}
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(fallback, f, ensure_ascii=False, indent=2)
        print('Wrote fallback', args.out)


if __name__ == '__main__':
    main()
