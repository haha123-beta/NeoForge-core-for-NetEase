"""Development-only verification of complete reviewed instance signatures in original jar."""
import re,subprocess
from java_official_probe import REF,JDK,mapping,native

def verify(contracts):
    mappings=(REF/'client_mappings.txt').read_text(encoding='utf-8')
    names=re.findall(r'^(\S+) -> (\S+):$',mappings,re.M)
    forward={a.replace('$','.'):b for a,b in names}
    originals={a.replace('$','.'):a for a,b in names}
    def descriptor(kind,bounds):
        kind=re.sub(r'<.*>','',kind)
        if kind.endswith('[]'):return '['+descriptor(kind[:-2],bounds)
        primitive={'void':'V','int':'I','long':'J','double':'D','float':'F','boolean':'Z','byte':'B','short':'S','char':'C'}
        if kind in primitive:return primitive[kind]
        visited=set()
        while kind in bounds and kind not in visited:
            visited.add(kind);kind=bounds[kind]
        if kind in ('T','B','V','I','O'):kind='java.lang.Object'
        return 'L'+forward.get(kind,kind).replace('.','/')+';'
    evidence=[]
    for identity,contract in sorted(contracts.items()):
        available={}
        for owner in [identity]+contract.get('superinterfaces',[]):
            original=originals[owner];text=mapping(original)
            p=subprocess.run([str(JDK/'javap.exe'),'-p','-s','-classpath',str(REF/'client.jar'),native(original)],capture_output=True,text=True)
            assert p.returncode==0,p.stderr
            assert re.search(r'public interface ',p.stdout),owner
            for line in text.splitlines():
                match=re.search(r'([\w.$\[\]]+) (\w+)\(([^)]*)\) -> (\w+)$',line)
                if not match:continue
                result,name,args,obf=match.groups()
                desc='('+''.join(descriptor(a.replace('$','.'),{}) for a in args.split(',') if a)+')'+descriptor(result.replace('$','.'),{})
                hit=re.search(r'^  public (?!static)([^\n]+) '+re.escape(obf)+r'\([^\n]*\)(?: throws [^;\n]+)?;\r?\n\s+descriptor: '+re.escape(desc)+r'\s*$',p.stdout,re.M)
                if hit:available[(name,desc)]='abstract' in hit[1].split()
            evidence.append({'java_name':owner,'mapping':text,'javap':p.stdout})
        for row in contract['methods']:
            bounds=contract.get('type_bounds',{})
            desc='('+''.join(descriptor(a,bounds) for a in row['parameters'])+')'+descriptor(row['return_type'],bounds)
            key=(row['name'],desc)
            assert key in available,(identity,key,available)
            assert row['abstract']==available[key],(identity,key,'abstract/default mismatch')
    return evidence
