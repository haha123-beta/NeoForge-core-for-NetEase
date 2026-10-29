# -*- coding: utf-8 -*-
"""Explicit reviewed runtime injection sites; content owns every registration."""
from __future__ import absolute_import
from neoforge.mixin_callbacks import CallbackInfo

MENU_TAIL = 'net.minecraft.world.inventory.AbstractContainerMenu.<init>(Lnet/minecraft/world/inventory/MenuType;I)V:TAIL'
TRADE_STAT = 'net.minecraft.world.inventory.MerchantResultSlot.onTake(Lnet/minecraft/world/entity/player/Player;Lnet/minecraft/world/item/ItemStack;)V:INVOKE:Lnet/minecraft/world/entity/player/Player;awardStat(Lnet/minecraft/resources/ResourceLocation;)V:0'
_SITES = {MENU_TAIL: ('callback', 2), TRADE_STAT: ('modify_arg', 1)}
_ROWS = []
_NEXT = [0]


class _Registration(object):
    def __init__(self, row):
        self._row = row
        self._closed = False
    def close(self):
        if self._closed:
            return None
        self._closed = True
        self._row['active'] = False
        for index,row in enumerate(_ROWS):
            if row is self._row:
                del _ROWS[index]
                break
        self._row['callback'] = None
        self._row['owner'] = None
        return None


class HookScope(object):
    def __init__(self, owner):
        if owner is None:
            raise ValueError('Runtime Mixin requires an explicit content owner')
        self.owner = owner
        self._handles = []
        self._closed = False
    def register(self, site, callback, priority=1000):
        if self._closed:
            raise RuntimeError('Runtime Mixin scope closed')
        if site not in _SITES or not callable(callback) or type(priority) is not int:
            raise ValueError('Unreviewed runtime Mixin site/callback/priority')
        _NEXT[0] += 1
        row = dict(site=site, callback=callback, priority=priority, serial=_NEXT[0], owner=self.owner, active=True)
        handle = _Registration(row)
        _ROWS.append(row)
        self._handles.append(handle)
        return handle
    def size(self):
        return sum(not handle._closed for handle in self._handles)
    def close(self):
        if self._closed:
            return None
        self._closed = True
        for handle in reversed(self._handles):
            handle.close()
        self._handles = []
        self.owner = None
        return None


def dispatch_tail(site, receiver, arguments):
    contract = _SITES.get(site)
    if contract is None or contract[0] != 'callback' or len(arguments) != contract[1]:
        raise ValueError('Unreviewed runtime Mixin dispatch')
    rows = sorted((r for r in _ROWS if r['site'] == site), key=lambda r: (-r['priority'], r['serial']))
    for row in rows:
        # Closing another owner while dispatching must prevent stale snapshot invocation.
        if row['active']:
            row['callback'](receiver, tuple(arguments), CallbackInfo('<init>', False))


def modify_argument(site, receiver, argument):
    contract = _SITES.get(site)
    if contract != ('modify_arg', 1):
        raise ValueError('Unreviewed runtime ModifyArg dispatch')
    rows = sorted((r for r in _ROWS if r['site'] == site), key=lambda r: (-r['priority'], r['serial']))
    for row in rows:
        if row['active']:
            argument = row['callback'](receiver, argument)
    return argument


class MixinHooks(object):
    ABI_VERSION = 2
    @staticmethod
    def openScope(owner):
        return HookScope(owner)
    @staticmethod
    def count():
        return sum(row['active'] for row in _ROWS)


JAVA_MAP = {'neocore.runtime.MixinHooks': MixinHooks}
