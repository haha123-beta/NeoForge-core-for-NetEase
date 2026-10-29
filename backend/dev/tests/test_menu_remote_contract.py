import os,sys,unittest,subprocess
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_container_java_contract import m,b,i,lang,pkg
arrays=pkg.load('java_stdlib.java_arrays')

class Receiver(object):
    def __init__(self):self.remote=[];self.local=[]
    def sendInitialData(self,menu,slots,carried,data):self.remote.append(('all',slots,carried,data))
    def sendSlotChange(self,menu,index,stack):self.remote.append(('slot',index,stack))
    def sendCarriedChange(self,menu,stack):self.remote.append(('carried',stack))
    def sendDataChange(self,menu,index,value):self.remote.append(('data',index,value))
    def slotChanged(self,menu,index,stack):self.local.append(('slot',index,stack))
    def dataChanged(self,menu,index,value):self.local.append(('data',index,value))

class MenuRemoteTests(unittest.TestCase):
    def menu(self):
        menu=m.AbstractContainerMenu();container=b.SimpleContainer(2);item=i.Item()
        for index in range(2):menu.addSlot(m.Slot(container,index))
        data=m.DataSlot.standalone();menu.addDataSlot(data)
        return menu,container,item,data
    def test_suppression_retains_local_notifications_and_flushes_on_later_broadcast(self):
        menu,c,item,data=self.menu();r=Receiver();menu.setSynchronizer(r);menu.addSlotListener(r)
        menu.suppressRemoteUpdates();c.setItem(0,i.ItemStack(item,3));data.set(12);menu.setCarried(i.ItemStack(item,2))
        menu.broadcastChanges();self.assertEqual(len(r.remote),1)
        self.assertEqual([x[0] for x in r.local],['slot','data'])
        menu.resumeRemoteUpdates();self.assertEqual(len(r.remote),1)
        menu.broadcastChanges();self.assertEqual([x[0] for x in r.remote],['all','slot','carried','data'])
        self.assertEqual(len(r.local),2)
    def test_remote_ack_never_overwrites_local_listener_baseline(self):
        menu,c,item,data=self.menu();r=Receiver();menu.setSynchronizer(r);menu.addSlotListener(r)
        stack=i.ItemStack(item,4);c.setItem(0,stack);menu.setRemoteSlot(0,stack)
        menu.broadcastChanges();self.assertEqual(len(r.local),1);self.assertEqual(len(r.remote),1)
        stack.shrink(1);menu.broadcastChanges();self.assertEqual(r.remote[-1][2].getCount(),3)
    def test_remote_copy_and_no_copy_have_distinct_alias_semantics(self):
        menu,c,item,data=self.menu();r=Receiver();menu.setSynchronizer(r)
        stack=i.ItemStack(item,4);c.setItem(0,stack);menu.setRemoteSlotNoCopy(0,stack)
        stack.shrink(1);menu.broadcastChanges();self.assertEqual(len(r.remote),1)
        menu.setRemoteSlot(0,stack);stack.shrink(1);menu.broadcastChanges()
        self.assertEqual(r.remote[-1][2].getCount(),2)
        menu.setRemoteSlotNoCopy(-1,stack);menu.setRemoteSlotNoCopy(99,stack)
        with self.assertRaises(lang.IndexOutOfBoundsException):menu.setRemoteSlot(-1,stack)
    def test_carried_ack_uses_copy_and_only_controls_remote_changes(self):
        menu,c,item,data=self.menu();r=Receiver();menu.setSynchronizer(r)
        stack=i.ItemStack(item,4);menu.setCarried(stack);menu.setRemoteCarried(stack)
        menu.broadcastChanges();self.assertEqual(len(r.remote),1)
        stack.shrink(1);menu.broadcastChanges();self.assertEqual(r.remote[-1][0],'carried')
    def test_setting_synchronizer_does_not_clear_pending_local_updates(self):
        menu,c,item,data=self.menu();c.setItem(0,i.ItemStack(item,2));data.set(7)
        r=Receiver();menu.setSynchronizer(r);menu.addSlotListener(r)
        self.assertEqual([x[0] for x in r.local],['slot','data']);self.assertEqual(len(r.remote),1)
    def test_second_listener_gets_only_actual_changes_not_fake_initial_replay(self):
        menu,c,item,data=self.menu();c.setItem(0,i.ItemStack(item,2));first=Receiver();second=Receiver()
        menu.addSlotListener(first);menu.addSlotListener(second);self.assertFalse(second.local)
        menu.addSlotListener(first);c.getItem(0).shrink(1);menu.broadcastChanges()
        self.assertEqual(len(first.local),2);self.assertEqual(len(second.local),1)
    def test_explicit_full_send_bypasses_suppression_and_uses_java_types(self):
        menu,c,item,data=self.menu();r=Receiver();menu.setSynchronizer(r);menu.suppressRemoteUpdates()
        c.setItem(0,i.ItemStack(item,2));data.set(9);menu.sendAllDataToRemote()
        event=r.remote[-1];self.assertEqual(len(r.remote),2)
        self.assertIsInstance(event[1],b.NonNullList);self.assertIsInstance(event[3],arrays.JavaArray)
        self.assertEqual(list(event[3]),[9]);c.getItem(0).shrink(1);self.assertEqual(event[1].get(0).getCount(),2)
    def test_local_listener_failure_keeps_java_commit_order(self):
        menu,c,item,data=self.menu();r=Receiver();menu.setSynchronizer(r)
        class Bad(Receiver):
            def slotChanged(self,menu,index,stack):
                self.local.append(('slot',index,stack));raise RuntimeError('listener failure')
        bad=Bad();menu.addSlotListener(bad);c.setItem(0,i.ItemStack(item,2))
        with self.assertRaises(RuntimeError):menu.broadcastChanges()
        menu.broadcastChanges();self.assertEqual(len(bad.local),1);self.assertEqual(r.remote[-1][0],'slot')
    def test_data_slot_flags_and_shared_storage_detect_external_changes(self):
        storage=arrays.JavaArrays.initialized('int',1,[0]);data=m.DataSlot.shared(storage,0)
        self.assertFalse(data.checkAndClearUpdateFlag());storage[0]=9
        self.assertTrue(data.checkAndClearUpdateFlag());self.assertFalse(data.checkAndClearUpdateFlag())
        data.set(4);self.assertEqual(storage[0],4);self.assertTrue(data.checkAndClearUpdateFlag())
        with self.assertRaises(lang.ArrayIndexOutOfBoundsException):m.DataSlot.shared(storage,-1).get()
    def test_full_state_updates_local_listeners_before_remote_initial_data(self):
        menu,c,item,data=self.menu();r=Receiver();menu.addSlotListener(r);menu.setSynchronizer(r)
        c.setItem(0,i.ItemStack(item,3));data.set(8);menu.suppressRemoteUpdates();menu.broadcastFullState()
        self.assertEqual([x[0] for x in r.local],['slot','data']);self.assertEqual(r.remote[-1][0],'all')
    def test_original_bytecode_commits_snapshot_before_callback_and_checks_suppression(self):
        dev=Path(__file__).resolve().parents[1]
        result=subprocess.run([r"E:\Java\jdk-21.0.10\bin\javap.exe",'-classpath',str(dev/'references/minecraft-1.21.1/client.jar'),'-c','-p','cpu'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        block=result.stdout.split('private void b(int, cuq, java.util.function.Supplier<cuq>);',1)[1].split('private void',1)[0]
        self.assertLess(block.index('Field y:Z'),block.index('Method jv.set:'))
        self.assertLess(block.index('Method jv.set:'),block.index('InterfaceMethod cqi.a:'))
        sync=result.stdout.split('public void a(cqi);',1)[1].split('public ',1)[0]
        self.assertIn('Method b:()V',sync);self.assertNotIn('Method e:()V',sync)

if __name__=='__main__':unittest.main()
