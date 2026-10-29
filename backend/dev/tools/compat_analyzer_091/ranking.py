"""Set-cover scenarios over observed requirements, never measured conversions."""
import collections

def closure(files,resolved,include_static=False):
    ready=set();pending=set(files)
    while True:
        changed=False
        for name in sorted(pending):
            row=files[name]
            requirements=set(row['measured_blockers'])
            if include_static and row['baseline_status']=='MANUAL_REVIEW':requirements.update(row['static_requirements'])
            if requirements-resolved:continue
            if not set(row['dependencies'])<=ready:continue
            ready.add(name);pending.remove(name);changed=True
        if not changed:break
    return ready

def scenario(files,resolved):
    initial=closure(files,set());diagnostic=closure(files,resolved);conservative=closure(files,resolved,True)
    manuals=sorted(n for n in diagnostic-initial if files[n]['baseline_status']=='MANUAL_REVIEW')
    peers=sorted(n for n in diagnostic-initial if files[n]['baseline_status']=='GENERATED_REVIEW_REQUIRED')
    all_clear=sorted(n for n in conservative-initial if files[n]['baseline_status']=='MANUAL_REVIEW')
    return {'measured_new_generated':None,'measurement_performed':False,'scenario_generation_range':[0,len(manuals)],
        'range_is_not_a_guaranteed_bound':True,'diagnostic_only_manual_constraints_cleared':manuals,
        'all_observed_manual_requirements_cleared':all_clear,'generated_dependency_closure_scenario':peers,
        'unknown_frontier_files':manuals,'assumptions':['All nodes in repair set are correctly fixed, including behavior and integration',
            'Diagnostic-only scenario ignores additional static requirements; real subsequent compiler failures remain unknown',
            'No guarantee of generation, dependency loadability, engine compatibility or playability']}

def rank(graph,steps=5):
    files=graph['files'];nodes=graph['blocker_nodes'];groups=collections.defaultdict(list)
    for key,row in nodes.items():groups[row['repair_group']].append(key)
    candidates=[]
    for id,keys in sorted(groups.items()):
        cats=sorted(set(nodes[k]['category'] for k in keys));affected=sorted(set(f for k in keys for f in nodes[k]['files']))
        measured=sorted(f for f in affected if set(keys)&set(files[f]['measured_blockers']))
        cost=12 if 'JVM_ASM_LIMIT' in cats else 5 if 'THIRD_PARTY_DEPENDENCY' in cats else 4 if 'COMPILER_SEMANTICS' in cats else 3
        owner=id.partition(':')[2] or id
        required=sorted(set(r['owner']+'#'+r['name']+r['descriptor'] for r in graph.get('member_resolutions',[])
                            if r['owner'].replace('$','.')==owner or r['resolution'].get('declaring_type','').replace('$','.')==owner))
        cost+=min(12,len(required)//4)
        optional=all(files[f].get('conditions') and all(c['baseline_skip'] for c in files[f]['conditions']) for f in affected)
        s=scenario(files,set(keys));coverage=len(measured)*2+len(affected)*(.2 if optional else 1)
        score=round((20*len(s['diagnostic_only_manual_constraints_cleared'])+coverage+len(keys)*.05)/cost,6)
        candidates.append({'id':id,'repair_nodes':sorted(keys),'categories':cats,'affected_files':affected,
            'measured_diagnostic_files':measured,'required_member_symbols':required,'heuristic_cost_units':cost,'cost_is_estimated':True,'score':score,
            'optional_only':optional,'eligible_for_092_core_repair':not set(cats)&{'JVM_ASM_LIMIT','THIRD_PARTY_DEPENDENCY'} and not optional,
            'dependency_work_must_remain_external':'THIRD_PARTY_DEPENDENCY' in cats,
            'scenario':s,'scope':'Candidate repair must implement actual semantics; metadata-only shims cannot discharge behavior nodes'})
    candidates.sort(key=lambda r:(-r['score'],r['id']))
    selected=[];resolved=set();available=list(candidates);batches=[]
    for step in range(min(steps,len(available))):
        def gain(row):
            new=set(row['repair_nodes'])-resolved
            if not row['eligible_for_092_core_repair']:return -1
            before=scenario(files,resolved);after=scenario(files,resolved|new)
            cleared=len(after['diagnostic_only_manual_constraints_cleared'])-len(before['diagnostic_only_manual_constraints_cleared'])
            coverage=sum(len(set(files[f]['measured_blockers']+files[f]['static_requirements'])&new) for f in row['affected_files'])
            return (20*cleared+len(row['affected_files'])+coverage*.05)/row['heuristic_cost_units']
        available.sort(key=lambda r:(-gain(r),r['id']));choice=available.pop(0)
        if gain(choice)<0:break
        selected.append(choice['id']);resolved.update(choice['repair_nodes'])
        batches.append({'step':step+1,'candidate_set':list(selected),'resolved_node_set':sorted(resolved),
            'affected_files':sorted(set(f for c in candidates if c['id'] in selected for f in c['affected_files'])),
            'scenario':scenario(files,resolved)})
    return {'algorithm':'deterministic weighted requirement coverage + dependency closure; greedy sets are not globally optimal',
        'cost_model':'heuristic units, not measured effort','objective':'decision support; generation is not the release metric',
        'candidates':candidates,'greedy_sets':batches,'actual_new_generated':0,
        'limits':['Unseen subsequent compiler blockers remain UNKNOWN','Potential bytecode references may be guarded/unreachable',
                  'Cycles are never solved merely by iterating closure; remaining cyclic dependencies stay blocked']}
