"""Frozen required-dependency graph; conflicts block, never rewrite declarations."""
import argparse
import json
from pathlib import Path
from modrinth_benchmark import Client, choose_version, timestamp, save, encoded, sha


def resolve(client, root_version, cutoff):
    nodes = {}
    edges = []
    problems = []
    visiting = set()

    def issue(kind, parent, dependency, detail):
        problems.append({'kind': kind, 'parent': parent, 'dependency': dependency, 'detail': detail})

    def visit(version, parent=None, request=None):
        pid, vid = version['project_id'], version['id']
        if timestamp(version['date_published']) > timestamp(cutoff):
            issue('after_cutoff', parent, request, vid)
            return
        if '1.21.1' not in version.get('game_versions', []) or 'neoforge' not in version.get('loaders', []):
            issue('wrong_platform', parent, request, vid)
            return
        if pid in nodes:
            if nodes[pid]['version']['id'] != vid:
                issue('version_conflict', parent, request, {'selected': nodes[pid]['version']['id'], 'requested': vid})
            return
        nodes[pid] = {'project_id': pid, 'version': version, 'external_required': True}
        visiting.add(vid)
        for dep in version.get('dependencies', []):
            kind = dep.get('dependency_type')
            edge = {'from_version': vid, 'declaration': dep, 'resolved_version': None}
            edges.append(edge)
            if kind in ('optional', 'incompatible', 'embedded'):
                edge['action'] = {'optional': 'not_auto_installed', 'incompatible': 'check_after_closure', 'embedded': 'provided_in_parent_archive_not_auto_installed'}[kind]
                # Embedded artifacts remain provenance declarations; a dependency on an unidentifiable embedded
                # archive must not be marked solved by inventing an externally selected version.
                continue
            if kind != 'required':
                issue('unknown_dependency_type', vid, dep, kind)
                continue
            try:
                if dep.get('version_id'):
                    child = client.get('/version/' + dep['version_id'])
                    if child['id'] != dep['version_id'] or (dep.get('project_id') and child['project_id'] != dep['project_id']):
                        issue('identity_mismatch', vid, dep, child['id'])
                        continue
                elif dep.get('project_id'):
                    candidates = client.get('/project/' + dep['project_id'] + '/version', {'loaders': '["neoforge"]', 'game_versions': '["1.21.1"]'})
                    child = choose_version(candidates, cutoff)
                    if child is None:
                        issue('no_compatible_dependency', vid, dep, dep['project_id'])
                        continue
                    if child['project_id'] != dep['project_id']:
                        issue('identity_mismatch', vid, dep, child['project_id'])
                        continue
                else:
                    issue('unresolved_file_dependency', vid, dep, dep.get('file_name'))
                    continue
                edge['resolved_version'] = child['id']
                edge['cycle'] = child['id'] in visiting
                visit(child, vid, dep)
            except (OSError, ValueError, KeyError) as error:
                issue('metadata_error', vid, dep, str(error))
        visiting.remove(vid)

    visit(root_version)
    for edge in edges:
        dep = edge['declaration']
        if dep.get('dependency_type') != 'incompatible':
            continue
        matches = [n['version']['id'] for pid, n in nodes.items() if
                   (not dep.get('project_id') or pid == dep['project_id']) and
                   (not dep.get('version_id') or n['version']['id'] == dep['version_id'])]
        if not dep.get('project_id') and not dep.get('version_id'):
            issue('unresolved_incompatibility', edge['from_version'], dep, dep.get('file_name'))
        elif matches:
            issue('incompatible_dependency', edge['from_version'], dep, matches)
    return {'schema': 1, 'root_version': root_version['id'], 'cutoff': cutoff,
            'nodes': nodes, 'edges': edges, 'problems': problems,
            'status': 'BLOCKED_DEPENDENCY' if problems else 'METADATA_CLOSURE_REVIEW_REQUIRED',
            'limits': ['Modrinth metadata only; platform/TOML/JarJar and actual source dependencies still require audit.',
                       'No version-constraint solver/backtracking; conflicting selected versions block.',
                       'No downloaded or executed JAR; embedded artifacts require archive/source audit.']}


def audit_development(client, sample_file):
    frozen = json.loads(Path(sample_file).read_bytes())
    if sha(encoded(frozen['samples'])) != frozen['sample_sha256']:
        raise ValueError('Frozen sample integrity failure')
    result = []
    for row in frozen['samples']:
        if row['group'] != 'development':
            continue
        graph = resolve(client, row['version'], frozen['commitment']['cutoff'])
        metadata = client.get('/project/' + row['project_id'])
        record = {'sample_id': row['sample_id'], 'project_id': row['project_id'], 'title': row['title'],
                  'version_id': row['version']['id'], 'metadata': metadata, 'dependency_graph': graph,
                  'source_url': metadata.get('source_url'), 'license': metadata.get('license'),
                  'status': 'BLOCKED_DEPENDENCY' if graph['problems'] else 'NOT_RUN',
                  'engine_verified': False, 'source_version_link_verified': False,
                  'next_step': 'Verify original source/tag and release relation; audit TOML/platform declarations before translation.'}
        path=client.root / 'development_records' / (row['sample_id'] + '.json')
        record['metadata_status']=record['status']
        if path.exists():
            prior=json.loads(path.read_bytes())
            if prior.get('project_id')!=row['project_id'] or prior.get('version_id')!=row['version']['id']:
                raise ValueError('Existing assessment belongs to a different frozen project/version')
            # Metadata re-audits refresh machine findings, never erase independently collected progress.
            for key,value in prior.items():
                if key not in record:record[key]=value
            if prior.get('status') and prior['status']!='NOT_RUN':record['status']=prior['status']
            record['source_version_link_verified']=prior.get('source_version_link_verified',False)
            record['engine_verified']=prior.get('engine_verified',False)
        journal=client.root/'results/events.jsonl'
        if journal.exists():
            from modrinth_results import Ledger
            ledger=Ledger(client.root)
            with ledger.locked():events=ledger.read()
            previous=[e for e in events if e['kind']=='result' and e['sample_id']==row['sample_id']]
            if previous:
                record['status']=previous[-1]['payload']['status']
                record['assessment_event_sha256']=previous[-1]['sha256']
                record['assessment_status_source']='results/events.jsonl'
        save(path, record)
        result.append(record)
    save(client.root / 'development_audit.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('round_root')
    args = parser.parse_args()
    client = Client(args.round_root)
    records = audit_development(client, client.root / 'samples.json')
    print(json.dumps({'development_samples': len(records), 'blocked_dependencies': sum(bool(r['dependency_graph']['problems']) for r in records),
                      'source_links': sum(bool(r['source_url']) for r in records), 'engine_verified': False}))


if __name__ == '__main__':
    main()
