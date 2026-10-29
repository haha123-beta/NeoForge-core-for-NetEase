import json,os,re,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_interface_oracle import verify
from java_official_probe import native,run_original
from harness import Package
import test_official_interfaces086 as execution

SOURCE='public class Run implements GuiEventListener {boolean focused;public void setFocused(boolean v){focused=v;}public boolean isFocused(){return focused;}public int run(){if(getCurrentFocusPath()!=null)return 99;setFocused(true);ComponentPath p=getCurrentFocusPath();if(p.component()!=this)return 98;p.applyFocus(false);return isFocused()?97:7;}}'

class GuiInput087(unittest.TestCase):
    def test_original_input_and_path_contracts(self):
        c=Package().load('minecraft.gui_input_contracts').INTERFACE_CONTRACTS
        self.assertEqual(len(c),2)
        result=verify(c)
        (Path(__file__).parents[1]/'builds/gui_input087_official_evidence.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

    def test_focus_leaf_roundtrip_original_and_real_python2(self):
        source=SOURCE.replace('public class Run','class Run')
        listener=native('net.minecraft.client.gui.components.events.GuiEventListener')
        for name,full in [('GuiEventListener','net.minecraft.client.gui.components.events.GuiEventListener'),('ComponentPath','net.minecraft.client.gui.ComponentPath')]:source=source.replace(name,native(full))
        for name,obf in [('setFocused','a'),('isFocused','aO_'),('getCurrentFocusPath','aP_'),('component','a'),('applyFocus','a')]:source=re.sub(r'\b'+name+r'\(',obf+'(',source)
        expected=run_original(source+'public class Probe {public static void main(String[] a){System.out.print(new Run().run()+","+'+listener+'.t);}}')
        self.assertEqual(expected,'7,250')
        execution.OfficialInterfaces086().execute('import net.minecraft.client.gui.components.events.GuiEventListener;import net.minecraft.client.gui.ComponentPath;'+SOURCE,'7')

    def test_original_default_input_results_and_zero_rectangle(self):
        p=Package();module=p.load('minecraft.gui_input_contracts')
        class Widget(module.GuiEventListener):
            def __init__(self):self.focused=False
            def setFocused(self,v):self.focused=v
            def isFocused(self):return self.focused
        w=Widget()
        self.assertIsNone(w.mouseMoved(1.0,2.0))
        for name,args in [('mouseClicked',(1.0,2.0,0)),('mouseReleased',(1.0,2.0,0)),('mouseDragged',(1.0,2.0,0,1.0,2.0)),('mouseScrolled',(1.0,2.0,3.0,4.0)),('keyPressed',(1,2,3)),('keyReleased',(1,2,3)),('charTyped',('a',0)),('isMouseOver',(1.0,2.0))]:
            self.assertFalse(getattr(w,name)(*args))
        self.assertIsNone(w.nextFocusPath(None));self.assertEqual(w.getRectangle().width(),0);self.assertEqual(w.getRectangle().height(),0)
        w.setFocused(True);path=w.getCurrentFocusPath();self.assertIs(path.component(),w)
        self.assertTrue(path.equals(module.ComponentPath.leaf(w)));path.applyFocus(False);self.assertFalse(w.isFocused())
        with self.assertRaises(AttributeError):path._nc_component=None
        with self.assertRaises(p.load('java_stdlib.lang').NullPointerException):module.ComponentPath.leaf(None).applyFocus(True)

if __name__=='__main__':unittest.main()
