"""Semantic grouping, bytecode evidence, cohorts, cache integrity and task safety."""
from pathlib import Path
import json,shutil,subprocess,sys,tempfile,unittest,zipfile,hashlib
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.compat_mining098.engine import scan,profile,save,load,compare,digest
from tools.compat_mining098.capabilities import aggregate,identify
from tools.compat_mining098.patches import validate

class Mining098(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);src=cls.root/'Run.java'
  src.write_text('''package fixture;import java.util.Optional;public class Run extends java.util.ArrayList<String> {
 public Object f(String s,java.sql.Connection c) throws Exception {c.close();return Optional.ofNullable(s);}
 public record Nested<T>(T value){} }''',encoding='utf-8')
  cls.classes=cls.root/'classes';cls.classes.mkdir()
  p=subprocess.run([r'E:\Java\jdk-21.0.10\bin\javac.exe','-proc:none','-d',str(cls.classes),str(src)],capture_output=True)
  if p.returncode:raise RuntimeError(p.stderr)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def jar(self,root,name,id='alpha',version='1',mixin=False):
  p=root/name
  with zipfile.ZipFile(p,'w') as z:
   z.writestr('META-INF/neoforge.mods.toml',f'modLoader="javafml"\nloaderVersion="[4,)"\nlicense="MIT"\n[[mods]]\nmodId="{id}"\nversion="{version}"\n')
   for c in self.classes.rglob('*.class'):z.write(c,c.relative_to(self.classes).as_posix())
   if mixin:z.writestr('example.mixins.json','{"required":true}')
  return p
 def test_raw_duplicates_and_mod_versions_do_not_inflate_reach(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);inputs=r/'inputs';inputs.mkdir();a=self.jar(inputs,'a.jar');shutil.copyfile(a,inputs/'copy.jar')
   self.jar(inputs,'a-v2.jar',version='2');self.jar(inputs,'b.jar',id='beta',mixin=True)
   run=scan([inputs],r/'out',r/'cache')
   self.assertEqual(run['status'],'PASSED');self.assertEqual(run['summary']['mod_artifacts'],3)
   self.assertEqual(run['summary']['logical_mods'],2);self.assertEqual(run['summary']['duplicate_paths'],1)
   sql=next(g for g in run['groups'] if g['key']=='api.member:java.sql.Connection#close')
   self.assertEqual((sql['affected_mods'],sql['affected_logical_files']),(2,2))
   self.assertTrue(any(g['key']=='java.nested_record' for g in run['groups']))
   self.assertTrue(any(g['key']=='java.generic_superclass_substitution' for g in run['groups']))
   again=scan([inputs],r/'again',r/'cache');self.assertEqual(again['summary']['cache_hits'],3)
   cache=next((r/'cache').rglob('*.json'));d=load(cache);d['result']['status']='TAMPERED';save(cache,d)
   third=scan([inputs],r/'third',r/'cache');self.assertEqual(third['summary']['cache_hits'],2)
   self.assertFalse(any(a['status']=='TAMPERED' for a in third['artifacts']))
 def test_semantic_nodes_merge_paths_and_preserve_unknowns(self):
  rows=[]
  for i in range(8):rows.append(dict(file=f'view/F{i}.java',logical_mod='neo:one',artifact_sha256='a',evidence='OBSERVED_BLOCKER',reason='parent varies '+str(i),details={'category':'generic_superclass','owner':'foo.Parent'+str(i)}))
  for i in range(7):rows.append(dict(file=f'functional/F{i}.java',logical_mod='neo:two',artifact_sha256='b',evidence='OBSERVED_BLOCKER',reason='Functional target interface unresolved: api.F'+str(i),details={'category':'source_lowering'}))
  groups=aggregate(rows,[])
  self.assertEqual(len(groups),2);self.assertEqual(sorted(g['affected_logical_files'] for g in groups),[7,8])
  self.assertNotEqual(identify({'reason':'opaque A'})['key'],identify({'reason':'opaque B'})['key'])
  self.assertEqual(identify({'details':{'owner':'org.spongepowered.asm.mixin.Mixin'}})['key'],'jvm.mixin')
  self.assertEqual(identify({'details':{'owner':'org.spongepowered.asm.mixin.injection.Inject'}})['key'],'jvm.mixin')
 def test_partial_reads_and_missing_inputs_remain_visible(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);p=self.jar(r,'broken.jar')
   with zipfile.ZipFile(p,'a') as z:z.writestr('bad/Bad.class',b'bad')
   invalid=r/'invalid-metadata.jar'
   with zipfile.ZipFile(invalid,'w') as z:z.writestr('fabric.mod.json','{"id":"bad\nname"}')
   run=scan([p,r/'missing.jar',invalid],r/'out')
   self.assertEqual(run['status'],'PARTIAL');self.assertEqual(run['summary']['unknown_classes'],1)
   self.assertTrue(run['errors']);self.assertTrue(run['artifacts'][0]['unknown_classes'])
   page=(r/'out/report.html').read_text(encoding='utf-8');self.assertIn('PARTIAL',page);self.assertIn('missing.jar',page)
   with zipfile.ZipFile(r/'out/能力任务包.zip') as z:
    summary=json.loads(z.read('run_summary.json'));self.assertEqual(summary['status'],'PARTIAL');self.assertEqual(len(summary['unread_classes']),1)
   from tools.compat_mining098.web import Controller
   view=Controller.__new__(Controller);state=view.finished(r/'out',load(r/'out/summary.json'))
   self.assertEqual(state['status'],'PARTIAL');self.assertEqual(len(state['errors']),3)
 def test_source_archives_do_not_count_as_binary_mods(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);p=r/'library-sources.jar'
   with zipfile.ZipFile(p,'w') as z:
    z.writestr('META-INF/neoforge.mods.toml','[[mods]]\nmodId="neoforge"\nversion="1"')
    z.writestr('a/Source.java','class Source {}')
   run=scan([p],r/'out');self.assertEqual(run['summary']['mod_artifacts'],0)
   self.assertEqual(run['artifacts'][0]['status'],'EXCLUDED_SOURCE_ARCHIVE')
 def test_report_observations_require_matching_input_and_current_profile(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);p=self.jar(r,'a.jar');h=digest(p);prof=profile();report=r/'one_report.json'
   self.assertIn('profiles/netease_pc_3_9_items.json',prof['source_files'])
   save(report,dict(result=dict(input_sha256=h,backend_source_sha256=prof['source_files'],translation=dict(files=2,generated_for_review=1,manual_review=1,failed=0)),source_reports=[dict(results=[dict(file='fixture/Run.java',status='MANUAL_REVIEW',reason='opaque',details={'category':'unicode_prelexing'})])]))
   run=scan([p],r/'out',reports=[report]);self.assertEqual(run['summary']['observed_current_reports'],1)
   self.assertEqual(run['summary']['observed_first_blockers'],1)
   report2=r/'two_report.json';d=load(report);d['result']['backend_source_sha256']={'old':'mismatch'};save(report2,d)
   historical=scan([p],r/'old',reports=[report2]);self.assertEqual(historical['summary']['observed_current_reports'],0)
   g=next(g for g in historical['groups'] if g['key']=='java.unicode_prelexing');self.assertEqual(g['historical_blocked_mods'],1);self.assertEqual(g['observed_blocked_mods'],0)
   self.assertEqual(g['priority'],0);self.assertEqual(g['affected_mods'],0)
 def test_acquisition_checks_publisher_hash_and_records_origin(self):
  from tools.compat_mining098.corpus import fetch
  raw=b'not-executed-bytecode';file=dict(filename='a.jar',url='https://cdn.modrinth.com/data/a/a.jar',size=len(raw),primary=True,hashes={'sha512':hashlib.sha512(raw).hexdigest()})
  hit=dict(project_id='abc',slug='example',title='Example')
  def response(url):
   if '/search?' in url:return json.dumps(dict(hits=[hit],total_hits=1)).encode()
   if '/version?' in url:return json.dumps([dict(id='v1',version_number='1',date_published='2026-01-01',loaders=['neoforge'],game_versions=['1.21.1'],files=[file])]).encode()
   return raw
  with tempfile.TemporaryDirectory() as t,patch('tools.compat_mining098.corpus.request',side_effect=response):
   r=Path(t);result=fetch(r/'ok',count=1,progress=lambda s:None)
   self.assertEqual(result['status'],'FETCHED');d=load(r/'ok/corpus.json')
   self.assertEqual(d['artifacts'][0]['sha256'],hashlib.sha256(raw).hexdigest())
   self.assertEqual(d['artifacts'][0]['project_url'],'https://modrinth.com/mod/example')
   file['hashes']['sha512']='0'*128
   bad=fetch(r/'bad',count=1,progress=lambda s:None)
   self.assertEqual(bad['status'],'PARTIAL');self.assertFalse(list((r/'bad/jars').glob('*.jar')))
 def test_diff_uses_same_artifacts_and_measured_denominators(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);a=r/'a';b=r/'b';a.mkdir();b.mkdir()
   base=dict(profile_sha256='a',artifacts=[dict(sha256='same',metadata={'logical_mod':'one'})],groups=[],observations=[dict(artifact_sha256='same',translation=dict(files=3,generated_for_review=1))])
   save(a/'run.json',base);new=json.loads(json.dumps(base));new['profile_sha256']='b';new['artifacts'].append(dict(sha256='new',metadata={'logical_mod':'two'}));new['observations'][0]['translation']['generated_for_review']=2
   save(b/'run.json',new);d=compare(a,b)
   self.assertEqual(d['matched_artifacts'],1);self.assertEqual(d['measured_translation'][0]['generated_delta'],1)
   self.assertEqual(d['added_artifacts'],['new']);self.assertTrue(d['static_cleared_is_not_compilation_gain'])
   new['observations'][0]['translation']['files']=4;save(b/'run.json',new)
   self.assertNotIn('generated_delta',compare(a,b)['measured_translation'][0])
   new['status']='PARTIAL';save(b/'run.json',new)
   partial=compare(a,b);self.assertEqual(partial['status'],'INCOMPLETE_RUN_NO_GAIN_CLAIM');self.assertEqual(partial['measured_translation'],[])
   new['status']='PASSED';new['analysis_profile_sha256']='new-normalizer';save(b/'run.json',new)
   self.assertEqual(compare(a,b)['status'],'ANALYSIS_RULES_CHANGED_NO_GAIN_CLAIM')
 def test_patch_target_injection_is_rejected_without_source_mutation(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);save(p/'proposal.json',dict(recipe='optional_ofNullable_reference_v1',files=[{'file':'../outside.py'}]))
   with self.assertRaisesRegex(ValueError,'Unexpected patch targets'):validate(p,True)
 def test_report_escapes_untrusted_evidence_and_task_paths(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);p=self.jar(r,'a.jar',id='<script>alert(1)</script>')
   run=scan([p],r/'out');text=(r/'out/report.html').read_text(encoding='utf-8')
   self.assertNotIn('<script>alert(1)</script>',text)
   with zipfile.ZipFile(r/'out/能力任务包.zip') as z:
    self.assertFalse(any('..' in Path(n).parts for n in z.namelist()))
    self.assertTrue(any(n.startswith('tasks/C/') for n in z.namelist()))
    index=json.loads(z.read('tasks/index.json'))
    for row in index['tasks']:
     stream=z.read('tasks/'+row['file']);task=json.loads(stream[row['offset']:row['offset']+row['bytes']])
     self.assertEqual(task['capability'],row['capability']);self.assertTrue(task['artifact_inputs'])

if __name__=='__main__':unittest.main()
