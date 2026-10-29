# -*- coding: utf-8 -*-
"""Original GUI input defaults and focus-leaf data. No input driver or rendering."""
from __future__ import absolute_import
from minecraft.official_interfaces import _declare,method,_invoke
from minecraft.gui_navigation import ScreenRectangle
from java_stdlib.records import RecordBase,JavaRecords

INTERFACE_CONTRACTS={}
INTERFACE_TYPES={}
_REGISTRY=(INTERFACE_CONTRACTS,INTERFACE_TYPES)
LISTENER='net.minecraft.client.gui.components.events.GuiEventListener'
PATH='net.minecraft.client.gui.ComponentPath'


def _ignore(self,*args,**kwargs):return None
def _false(self,*args,**kwargs):return False
def _rectangle(self,_nc_java_signature=None):return ScreenRectangle(0,0,0,0)
def _focus_path(self,_nc_java_signature=None):
    return ComponentPath.leaf(self) if _invoke(self,'isFocused') else None


_METHODS=[method('setFocused',['boolean'],'void'),method('isFocused',[],'boolean')]
_DEFAULT_ROWS=[('mouseMoved',['double','double'],'void',_ignore),
    ('mouseClicked',['double','double','int'],'boolean',_false),
    ('mouseReleased',['double','double','int'],'boolean',_false),
    ('mouseDragged',['double','double','int','double','double'],'boolean',_false),
    ('mouseScrolled',['double','double','double','double'],'boolean',_false),
    ('keyPressed',['int','int','int'],'boolean',_false),('keyReleased',['int','int','int'],'boolean',_false),
    ('charTyped',['char','int'],'boolean',_false),
    ('nextFocusPath',['net.minecraft.client.gui.navigation.FocusNavigationEvent'],PATH,_ignore),
    ('isMouseOver',['double','double'],'boolean',_false),
    ('getCurrentFocusPath',[],PATH,_focus_path),
    ('getRectangle',[],'net.minecraft.client.gui.navigation.ScreenRectangle',_rectangle)]
GuiEventListener=_declare(LISTENER,_METHODS+[method(n,args,result,True) for n,args,result,fn in _DEFAULT_ROWS],
    defaults={n:fn for n,args,result,fn in _DEFAULT_ROWS},registry=_REGISTRY)
GuiEventListener.DOUBLE_CLICK_THRESHOLD_MS=250
INTERFACE_CONTRACTS[LISTENER]['fields']=[dict(name='DOUBLE_CLICK_THRESHOLD_MS',declared_type='long',static=True,final=True,modifiers=['public','static','final'],line=1)]
ComponentPath=_declare(PATH,[method('component',[],LISTENER),method('applyFocus',['boolean'],'void')],registry=_REGISTRY)


class _Leaf(RecordBase,ComponentPath):
    _nc_JavaName=PATH+'.Leaf'
    _nc_RecordComponents=(('component',LISTENER,'_nc_component'),)
    def __init__(self,component):
        object.__setattr__(self,'_nc_component',component)
        object.__setattr__(self,'_nc_record_sealed',True)
    def component(self):return self._nc_component
    def applyFocus(self,focused):
        from java_stdlib.lang import NullPointerException
        if self._nc_component is None:raise NullPointerException()
        _invoke(self._nc_component,'setFocused',(focused,),('boolean',))
    def equals(self,other):return JavaRecords.equals(self,other)
    def hashCode(self):return JavaRecords.hashCode(self)
    def toString(self):return JavaRecords.toString(self)


ComponentPath.leaf=staticmethod(lambda component:_Leaf(component))
for _contract in INTERFACE_CONTRACTS.values():_contract['helper_abi']=7
JAVA_MAP=dict(INTERFACE_TYPES)
