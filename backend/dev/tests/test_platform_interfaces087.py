import hashlib,json,os,re,sys,unittest,zipfile
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_frontend import parse_source
from java_symbols import declarations
from java_method_overloads import canonical_return
import test_official_interfaces086 as execution

class PlatformInterfaces087(unittest.TestCase):
    def test_all_contracts_match_pinned_original_neoforge_source_declarations(self):
        source=Path(__file__).parents[1]/'references/neoforge-21.1.233-sources.jar'
        module=Package().load('neoforge.interface_contracts')
        contracts=dict(module.INTERFACE_CONTRACTS,**module.GENERIC_INTERFACES)
        self.assertEqual(len(contracts),11);evidence=[]
        with zipfile.ZipFile(source) as archive:
            for identity,contract in contracts.items():
                with self.subTest(interface=identity):
                    available={}
                    for owner in [identity]+contract.get('superinterfaces',[]):
                        filename=owner.replace('.','/')+'.java';raw=archive.read(filename);ir=parse_source(raw,filename)
                        rows=declarations(ir)['classes'];row=next(c for c in rows if c['java_name']==owner)
                        context=dict(row,external=True,package=ir['package'],imports=ir['imports'])
                        unit=dict(ir,_classes=rows)
                        variables=contract.get('type_parameters',[])
                        def normalize(kind):
                            for name in variables:kind=re.sub(r'\b'+re.escape(name)+r'\b','neocore.typevars.'+name,kind)
                            value=canonical_return(kind,context,unit)
                            for name in variables:value=value.replace('neocore.typevars.'+name,name)
                            return value
                        for method in row['methods']:
                            if method['static']:continue
                            key=(method['name'],tuple(normalize(p['declared_type']) for p in method['parameters']),normalize(method['return_type']))
                            available[key]=method['body'] is None
                        evidence.append({'java_name':owner,'source_file':filename,'sha256':hashlib.sha256(raw).hexdigest(),'source':raw.decode('utf-8')})
                    actual={(m['name'],tuple(m['parameters']),m['return_type']):m['abstract'] for m in contract['methods']}
                    self.assertEqual(actual,available)
        result={'version':'21.1.233','source_jar_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'interfaces':evidence,'limits':['Declarations and selected default behavior, not a full platform implementation.']}
        (Path(__file__).parents[1]/'builds/platform_interfaces087_official_evidence.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

    def test_typed_handler_calls_on_existing_native_objects_actual_python2(self):
        execution.OfficialInterfaces086().execute('import net.neoforged.neoforge.items.IItemHandler;import net.neoforged.neoforge.items.ItemStackHandler;public class Run {public int run(){IItemHandler h=new ItemStackHandler(3);return h.getSlots();}}','3')
        execution.OfficialInterfaces086().execute('import net.neoforged.neoforge.energy.IEnergyStorage;import net.neoforged.neoforge.energy.EnergyStorage;public class Run {public int run(){IEnergyStorage e=new EnergyStorage(100);e.receiveEnergy(20,false);e.extractEnergy(3,true);return e.getEnergyStored();}}','20')
        execution.OfficialInterfaces086().execute('import net.neoforged.neoforge.fluids.capability.IFluidHandler;import net.neoforged.neoforge.fluids.capability.templates.FluidTank;public class Run {public int run(){IFluidHandler t=new FluidTank(1000);return t.getTanks()+t.getTankCapacity(0);}}','1001')

    def test_generic_nbt_source_implementation_roundtrip_actual_python2(self):
        execution.OfficialInterfaces086().execute('import net.neoforged.neoforge.common.util.INBTSerializable;import net.minecraft.core.HolderLookup;import net.minecraft.nbt.CompoundTag;public class Run implements INBTSerializable<CompoundTag> {int count=7;public CompoundTag serializeNBT(HolderLookup.Provider p){CompoundTag t=new CompoundTag();t.putInt("value",count);return t;}public void deserializeNBT(HolderLookup.Provider p,CompoundTag t){count=t.getInt("value");}public int run(){INBTSerializable<CompoundTag> x=this;CompoundTag t=x.serializeNBT(null);count=0;x.deserializeNBT(null,t);return count;}}','7')

if __name__=='__main__':unittest.main()
