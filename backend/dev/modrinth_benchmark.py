"""Reproducible, read-only Modrinth sampling. This tool never runs mod JARs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

API = 'https://api.modrinth.com/v2'
UA = 'NeoCore-CompatibilityResearch/0.1 (local read-only compatibility study)'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value) + b'\n')


def timestamp(value):
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('Explicit UTC offset required')
    return date.astimezone(timezone.utc)


class Client:
    def __init__(self, root):
        self.root = Path(root)

    def get(self, endpoint, params=None):
        url = API + endpoint + ('?' + urllib.parse.urlencode(params) if params else '')
        key = sha(url.encode())
        path = self.root / 'responses' / (key + '.json')
        if path.exists():
            record = json.loads(path.read_bytes())
            if record['url'] != url or sha(encoded(record['data'])) != record['data_sha256']:
                raise ValueError('Cached response integrity failure: ' + url)
            return record['data']
        for attempt in range(5):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=45) as response:
                    data = json.load(response)
                save(path, {'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                            'data_sha256': sha(encoded(data)), 'data': data})
                return data
            except urllib.error.HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == 4:
                    raise
                time.sleep(min(30, max(2 ** attempt, int(error.headers.get('Retry-After', '1')))))
            except (TimeoutError, urllib.error.URLError):
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)


def choose_version(versions, cutoff, game='1.21.1', loader='neoforge'):
    limit = timestamp(cutoff)
    eligible = [v for v in versions if game in v.get('game_versions', []) and
                loader in v.get('loaders', []) and timestamp(v['date_published']) <= limit and
                v.get('version_type') in ('release', 'beta', 'alpha') and v.get('status', 'listed') == 'listed']
    channels = {'release': 0, 'beta': 1, 'alpha': 2}
    return min(eligible, key=lambda v: (channels[v['version_type']], -timestamp(v['date_published']).timestamp(), v['id'])) if eligible else None


def ordered(ids, seed):
    if not seed or '\n' in seed:
        raise ValueError('Nonempty single-line seed required')
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate candidate ID')
    return sorted(ids, key=lambda pid: (sha((seed + '\n' + pid).encode('utf-8')), pid))


def capture(client, cutoff):
    facets = [['project_type:mod'], ['categories:neoforge'], ['versions:1.21.1'],
              ['created_timestamp<=' + str(int(timestamp(cutoff).timestamp()))]]
    params = {'facets': json.dumps(facets), 'index': 'newest', 'limit': 100}
    first = client.get('/search', dict(params, offset=0))
    total = first['total_hits']
    offsets = list(range(100, total, 100))
    with ThreadPoolExecutor(max_workers=4) as pool:
        pages = [first] + list(pool.map(lambda offset: client.get('/search', dict(params, offset=offset)), offsets))
    hits = [h for p in pages for h in p['hits']]
    ids = [h['project_id'] for h in hits]
    if any(p['total_hits'] != total for p in pages) or len(ids) != total or len(set(ids)) != total:
        raise ValueError('Search changed or pagination incomplete; freeze refused (responses retained)')
    # A second boundary request cannot prove transaction isolation; record this API limitation.
    result = {'schema': 1, 'cutoff': cutoff, 'api': API, 'facets': facets, 'index': 'newest',
              'total_search_hits': total, 'candidate_ids': sorted(ids), 'hits': sorted(hits, key=lambda h: h['project_id']),
              'qualification': 'Search frame; exact version qualification is deferred along frozen random order.',
              'limitations': ['API has no historical transactional snapshot. Search tags reflect capture time; publication cutoff is enforced on chosen versions.'],
              'candidate_ids_sha256': sha(encoded(sorted(ids)))}
    save(client.root / 'candidates.json', result)
    return result


def draw(client, frame, seed, development=20, evaluation=100):
    if development < 0 or evaluation < 1:
        raise ValueError('Invalid sample sizes')
    if sha(encoded(frame['candidate_ids'])) != frame['candidate_ids_sha256']:
        raise ValueError('Candidate frame hash mismatch')
    ids = ordered(frame['candidate_ids'], seed)
    commitment = {'schema': 1, 'seed': seed, 'cutoff': frame['cutoff'],
                  'candidate_ids_sha256': frame['candidate_ids_sha256'],
                  'order_sha256': sha(encoded(ids)), 'development': development, 'evaluation': evaluation,
                  'qualification_rule': 'first eligible projects in frozen SHA256 permutation; release then beta then alpha; cutoff; exact 1.21.1/neoforge',
                  'heldout_policy': 'Do not inspect/adapt heldout source or gameplay before implementation freeze.'}
    path = client.root / 'commitment.json'
    if path.exists() and json.loads(path.read_bytes()) != commitment:
        raise ValueError('Existing commitment differs; use a new round')
    save(path, commitment)  # Written before any version qualification or result inspection.
    hits = {h['project_id']: h for h in frame['hits']}
    rows = []
    rejected = []
    def qualified_order():
        with ThreadPoolExecutor(max_workers=4) as pool:
            for start in range(0,len(ids),8):
                batch=ids[start:start+8]
                results=list(pool.map(lambda pid: client.get('/project/'+pid+'/version', {'loaders':'["neoforge"]','game_versions':'["1.21.1"]'}),batch))
                for offset,(pid,versions) in enumerate(zip(batch,results)):
                    yield start+offset+1,pid,versions
    for rank, pid, versions in qualified_order():
        version = choose_version(versions, frame['cutoff'])
        if version is None:
            rejected.append({'project_id': pid, 'draw_rank': rank, 'reason': 'no_eligible_version_at_cutoff'})
            continue
        if version['project_id']!=pid:
            raise ValueError('Version qualification project identity mismatch: '+pid)
        hit = hits[pid]
        rows.append({'sample_id': 'S%03d' % (len(rows) + 1), 'project_id': pid, 'slug': hit['slug'],
                     'title': hit['title'], 'description': hit['description'], 'categories': hit['categories'],
                     'client_side': hit.get('client_side'), 'server_side': hit.get('server_side'),
                     'draw_rank': rank, 'group': 'development' if len(rows) < development else 'evaluation',
                     'version': version, 'status': 'NOT_RUN', 'engine_evidence': [], 'history': []})
        if len(rows) >= development + evaluation:
            break
    result = {'schema': 1, 'commitment': commitment, 'frame_size': len(ids), 'samples': rows,
              'qualification_rejections': rejected, 'sample_sha256': sha(encoded(rows)),
              'coverage': 'Full captured search frame randomly permuted; unvisited remainder not version-qualified.',
              'status': 'FROZEN' if len(rows) == development + evaluation else 'INSUFFICIENT_ELIGIBLE_CANDIDATES'}
    path = client.root / 'samples.json'
    if path.exists() and json.loads(path.read_bytes()) != result:
        raise ValueError('Frozen sample changed; use a new round')
    save(path, result)
    save(client.root / 'development.json', [r for r in rows if r['group'] == 'development'])
    save(client.root / 'evaluation.json', [r for r in rows if r['group'] == 'evaluation'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['capture', 'draw'])
    parser.add_argument('root')
    parser.add_argument('--cutoff')
    parser.add_argument('--seed')
    parser.add_argument('--development', type=int, default=20)
    parser.add_argument('--evaluation', type=int, default=100)
    args = parser.parse_args()
    client = Client(args.root)
    if args.command == 'capture':
        if not args.cutoff:
            parser.error('--cutoff required')
        if (client.root / 'candidates.json').exists():
            parser.error('Snapshot already exists; use a new directory')
        result = capture(client, args.cutoff)
        print(json.dumps({'captured': result['total_search_hits'], 'sha256': result['candidate_ids_sha256']}))
    else:
        if not args.seed:
            parser.error('--seed required')
        result = draw(client, json.loads((client.root / 'candidates.json').read_bytes()), args.seed, args.development, args.evaluation)
        print(json.dumps({'status': result['status'], 'samples': len(result['samples']), 'rejections': len(result['qualification_rejections'])}))


if __name__ == '__main__':
    main()
