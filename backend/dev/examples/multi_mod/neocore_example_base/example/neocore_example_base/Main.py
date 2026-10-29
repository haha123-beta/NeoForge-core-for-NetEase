# -*- coding: utf-8 -*-
from net.neoforged.neoforge.registries import DeferredRegister
from net.neoforged.neoforge.event.tick import ServerTickEvent


def start(context):
    state = {"ticks": 0, "closed": False}
    entries = DeferredRegister.create("neocore:example", context.mod_id)
    entries.register("counter", lambda: state)
    entries.register(context.mod_bus)
    def tick(event):
        state["ticks"] += 1
    def close():
        state["closed"] = True
    context.game_bus.addListener(ServerTickEvent.Post, tick)
    context.on_close(close)
    return state
