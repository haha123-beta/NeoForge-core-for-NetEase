# -*- coding: utf-8 -*-
"""Native SDK validation content. Python demo, not a translated Java mod."""
from net.minecraft.network.protocol.common.custom import CustomPacketPayload
from net.minecraft.network.codec import StreamCodec
from net.minecraft.resources import ResourceLocation
from net.neoforged.neoforge.network.event import RegisterPayloadHandlersEvent
from net.neoforged.neoforge.network import PacketDistributor
from net.neoforged.neoforge.event.tick import ServerTickEvent
from net.neoforged.neoforge.client.event import ClientTickEvent


class CounterPacket(CustomPacketPayload):
    TYPE = CustomPacketPayload.Type(ResourceLocation('network_roundtrip:counter'))
    def __init__(self, value): self.value = value


CODEC = StreamCodec.of(lambda b, p: b.writeInt(p.value), lambda b: CounterPacket(b.readInt()))


def start(context):
    state = {'ticks': 0, 'sent': 0, 'received': 0, 'total': 0, 'closed': False}
    server = context.side == 'SERVER'
    def handle(packet, payload_context):
        def work():
            state['received'] += 1
            if server:
                state['total'] += packet.value
                PacketDistributor.sendToPlayer(payload_context.player(), CounterPacket(state['total']))
            else:
                state['total'] = packet.value
            print('[NeoCore network r50]', context.side, state)
        payload_context.enqueueWork(work)
    def register(event):
        event.registrar('45').playBidirectional(CounterPacket.TYPE, CODEC, handle)
    def tick(event):
        state['ticks'] += 1
        if not server and state['ticks'] % 20 == 0 and state['ticks'] <= 100:
            PacketDistributor.sendToServer(CounterPacket(1))
            state['sent'] += 1
    def close(): state['closed'] = True
    context.mod_bus.addListener(RegisterPayloadHandlersEvent, register)
    context.game_bus.addListener(ServerTickEvent.Post if server else ClientTickEvent.Post, tick)
    context.on_close(close)
    return state
