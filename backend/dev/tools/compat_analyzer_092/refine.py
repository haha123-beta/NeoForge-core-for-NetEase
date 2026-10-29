"""Correct evidence attribution without changing the frozen 0.9.1 artifacts."""
import copy,collections

def refine(graph):
    graph=copy.deepcopy(graph);nodes=graph['blocker_nodes'];replacements={}
    for file,row in graph['files'].items():
        diagnostic=row.get('baseline_diagnostic') or {}
        details=diagnostic.get('details') or {}
        if details.get('category')!='generic_superclass':continue
        for key in list(row['measured_blockers']):
            old=nodes[key]
            if old['category']!='COMPILER_SEMANTICS':continue
            identity=details.get('resolved_name')
            if not identity:continue
            newkey='COMPILER_SEMANTICS:generic_superclass:'+identity
            new=nodes.setdefault(newkey,dict(id=newkey,category='COMPILER_SEMANTICS',symbol='generic_superclass:'+identity,
                summary='Generic ancestor contract requires lowering: '+identity,certainty='MEASURED_DIAGNOSTIC',
                repair_group=newkey,files=[],evidence=[],behavior_verified=False))
            new['files'].append(file)
            new['evidence'].append(dict(source='0.9.0_report',file=file,line=diagnostic.get('line'),
                reason=diagnostic.get('reason'),details=details))
            row['measured_blockers']=[newkey if k==key else k for k in row['measured_blockers']]
            row['static_requirements']=[newkey if k==key else k for k in row['static_requirements']]
            replacements.setdefault(key,[]).append(newkey)
            for edge in graph.get('edges',[]):
                if edge.get('from')==file and edge.get('to')==key:edge['to']=newkey
    for key in replacements:
        if not any(key in r['measured_blockers']+r['static_requirements'] for r in graph['files'].values()):nodes.pop(key)
    graph['version']='0.9.2'
    graph.setdefault('summary',{})['node_categories']=dict(collections.Counter(n['category'] for n in nodes.values()))
    graph['diagnostic_refinement']={'old_to_new':{k:sorted(set(v)) for k,v in replacements.items()},
        'reason':'Group by resolved ancestor identity, preserve each file reason; no shared sample diagnosis',
        'production_type_pollution_observed':False,'measured_generation_gain':0}
    return graph

def calibrate(before,after):
    a={r['file']:r for r in before['results']};b={r['file']:r for r in after['results']}
    if set(a)!=set(b):raise ValueError('File sets differ; calibration requires identical inputs')
    def closed(rows):
        ready=set()
        while True:
            new={n for n,r in rows.items() if r['status']=='GENERATED_REVIEW_REQUIRED' and not r.get('missing_generated_dependencies') and set(r.get('project_dependencies',[]))<=ready}
            if new<=ready:return ready
            ready.update(new)
    changes=[]
    for n in sorted(a):
        x,y=a[n],b[n]
        if x!=y:changes.append(dict(file=n,before=x,after=y,new_frontier=y.get('reason'),
            FIRST_DIAGNOSTIC_REMOVED=x['status']!='GENERATED_REVIEW_REQUIRED' and y['status']=='GENERATED_REVIEW_REQUIRED',
            frontier_changed_unverified=x['status']!='GENERATED_REVIEW_REQUIRED' and y['status']!='GENERATED_REVIEW_REQUIRED' and x.get('reason')!=y.get('reason')))
    return dict(FIRST_DIAGNOSTIC_REMOVED=[r['file'] for r in changes if r['FIRST_DIAGNOSTIC_REMOVED']],
        first_diagnostic_policy='Conservative: generation confirms removal; changed wording or another manual diagnostic alone does not prove removal',
        FRONTIER_CHANGED_UNVERIFIED=[r['file'] for r in changes if r['frontier_changed_unverified']],
        ALL_KNOWN_REQUIREMENTS_CLEARED=None,known_requirements_status='UNKNOWN_REQUIRES_NEW_GRAPH_AND_SEMANTIC_PROOF',
        NEWLY_GENERATED=sorted(n for n in a if a[n]['status']!='GENERATED_REVIEW_REQUIRED' and b[n]['status']=='GENERATED_REVIEW_REQUIRED'),
        GENERATED_DEPENDENCY_CLOSED=sorted(closed(b)-closed(a)),PYTHON2_EXECUTED=[],ENGINE_VERIFIED=[],
        changed_files=changes,counts_before=dict(collections.Counter(r['status'] for r in a.values())),
        counts_after=dict(collections.Counter(r['status'] for r in b.values())))
