# -*- coding: utf-8 -*-
"""
β 层自测：neoforge/network.py（自定义包载荷）

真实依据（逐字来自反编译源码）：
    public class ChangeEntityDataPacket implements CustomPacketPayload {
        public static final CustomPacketPayload.Type<ChangeEntityDataPacket> TYPE =
            new CustomPacketPayload.Type(
                ResourceLocation.fromNamespaceAndPath("manaita_plus_legacy",
                                                      "change_entity_data"));
        public static final StreamCodec<ByteBuf, ChangeEntityDataPacket> STREAM_CODEC = ...;
        public final UUID id;
        public final byte flag;

        public static void handle(ChangeEntityDataPacket payload, IPayloadContext context) {
            context.enqueueWork(() -> {
                if (!context.flow().isClientbound()) return;
                ClientPacketHandlers.handler(payload);
            });
        }
        public CustomPacketPayload.Type<? extends CustomPacketPayload> type() {
            return TYPE;
        }
    }

    注册：
        PayloadRegistrar registrar = event.registrar("1.18");
        registrar.playToServer(KeyPressPacket.TYPE, KeyPressPacket.STREAM_CODEC,
                               KeyPressPacket::handle);
        registrar.playToClient(ChangeEntityDataPacket.TYPE, ..., ...);

    发送（Networking.java 里的六个入口）：
        PacketDistributor.sendToServer / sendToPlayer / sendToAllPlayers /
        sendToPlayersInDimension / sendToPlayersTrackingEntityAndSelf /
        sendToPlayersTrackingEntity

验证点：
  1. FriendlyByteBuf 的读写往返（含类型不匹配的报错）
  2. StreamCodec 的编解码与 unit/apply
  3. CustomPacketPayload.Type 的唯一标识与相等语义
  4. IPayloadContext 的 enqueueWork 延迟执行语义（网络线程 → 主线程）
  5. PayloadRegistrar 的 playToServer / playToClient / 重复注册检查
  6. PayloadRegistry 的编码→解码→派发闭环，以及方向过滤
  7. PacketDistributor 的六个投递入口
  8. 端到端：照真实写法定义两个包，注册、发收、处理
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
network = pkg.load("neoforge.network")
event = pkg.load("neoforge.event")
registries = pkg.load("neoforge.registries")


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("FriendlyByteBuf：读写往返")
    # ------------------------------------------------------------
    buf = network.FriendlyByteBuf()
    buf.writeBoolean(True)
    buf.writeInt(42)
    buf.writeUtf(u"hello")
    buf.writeDouble(1.5)
    buf.writeUUID(u"abc-123")
    check(u"写入 5 项后剩余 5", buf.readableBytes() == 5, buf.readableBytes())

    # 注意：读方法会推进游标，所以必须先取出来再断言，
    # 不能在断言标签里再调一次（会多读一项，后面全错位）。
    got_bool = buf.readBoolean()
    got_int = buf.readInt()
    got_utf = buf.readUtf()
    got_double = buf.readDouble()
    got_uuid = buf.readUUID()

    check(u"readBoolean", got_bool is True, got_bool)
    check(u"readInt", got_int == 42, got_int)
    check(u"readUtf", got_utf == u"hello", got_utf)
    check(u"readDouble", got_double == 1.5, got_double)
    check(u"readUUID", got_uuid == u"abc-123", got_uuid)
    check(u"读完剩余 0", buf.readableBytes() == 0)

    check(u"读空缓冲区抛异常", raises(buf.readInt))

    # 类型错配：写字符串却按整数读，应给出清楚的错误
    mismatch = network.FriendlyByteBuf()
    mismatch.writeUtf(u"not_a_number")
    check(u"类型不匹配时 readInt 报错", raises(mismatch.readInt))
    try:
        mismatch.readInt()
    except Exception as error:
        check(u"类型错配的报错信息看得懂",
              u"类型不匹配" in u"{}".format(error), u"{}".format(error)[:60])

    loc_buf = network.FriendlyByteBuf()
    loc_buf.writeResourceLocation(u"mod:thing")
    read_loc = loc_buf.readResourceLocation()
    check(u"ResourceLocation 往返",
          read_loc.toString() == u"mod:thing", read_loc.toString())

    check(u"FriendlyByteBuf 保留 ByteBuf 类型身份",
          issubclass(network.FriendlyByteBuf, network.ByteBuf))
    check(u"RegistryFriendlyByteBuf 也是",
          network.RegistryFriendlyByteBuf is network.FriendlyByteBuf)

    # ------------------------------------------------------------
    section("StreamCodec")
    # ------------------------------------------------------------
    def encode_int(buffer, value):
        buffer.writeInt(value)

    def decode_int(buffer):
        return buffer.readInt()

    codec = network.StreamCodec.of(encode_int, decode_int)
    out = network.FriendlyByteBuf()
    codec.encode(out, 7)
    decoded = codec.decode(out)
    check(u"编码后可解码", decoded == 7, decoded)

    unit_codec = network.StreamCodec.unit(u"singleton")
    empty = network.FriendlyByteBuf()
    check(u"unit 拒绝不同值", raises(unit_codec.encode, empty, u"whatever"))
    unit_codec.encode(empty, u"singleton")
    check(u"unit 编码不写任何数据", empty.readableBytes() == 0,
          empty.readableBytes())
    unit_decoded = unit_codec.decode(empty)
    check(u"unit 解码返回固定实例", unit_decoded == u"singleton", unit_decoded)

    mapped = codec.apply(lambda c: c.map(lambda v: v * 2, lambda v: v // 2))
    out2 = network.FriendlyByteBuf()
    mapped.encode(out2, 10)
    mapped_decoded = mapped.decode(out2)
    check(u"apply 在解码后转换", mapped_decoded == 10, mapped_decoded)

    check(u"没有编码函数时报错",
          raises(network.StreamCodec().encode, network.FriendlyByteBuf(), 1))
    check(u"没有解码函数时报错",
          raises(network.StreamCodec().decode, network.FriendlyByteBuf()))

    # ------------------------------------------------------------
    section("CustomPacketPayload.Type")
    # ------------------------------------------------------------
    type_a = network.CustomPacketPayload_Type(
        registries.ResourceLocation(u"manaita_plus_legacy", u"key_press"))
    type_b = network.CustomPacketPayload_Type(
        registries.ResourceLocation(u"manaita_plus_legacy", u"key_press"))
    type_c = network.CustomPacketPayload_Type(
        registries.ResourceLocation(u"manaita_plus_legacy", u"other"))

    check(u"Type.toString 是完整位置",
          type_a.toString() == u"Type[id=manaita_plus_legacy:key_press]", type_a.toString())
    check(u"同位置相等", type_a == type_b)
    check(u"不同位置不等", type_a != type_c)
    check(u"可作字典键", {type_a: 1}[type_b] == 1)
    check(u"Type 挂在 CustomPacketPayload 上（Java 内部类写法）",
          network.CustomPacketPayload.Type is network.CustomPacketPayload_Type)

    # ------------------------------------------------------------
    section("IPayloadContext：enqueueWork 的延迟语义")
    # ------------------------------------------------------------
    ran = []
    ctx = network.IPayloadContext(network.PacketFlow.CLIENTBOUND, u"player1")

    ctx.enqueueWork(lambda: ran.append(1))
    check(u"enqueueWork 不立即执行", ran == [], ran)
    check(u"任务已排队", ctx.pending() == 1, ctx.pending())

    executed = ctx.drainWork()
    check(u"drainWork 执行了任务", executed == 1, executed)
    check(u"任务确实跑了", ran == [1], ran)
    check(u"队列已清空", ctx.pending() == 0)

    check(u"flow().isClientbound()",
          ctx.flow().isClientbound() is True)
    check(u"flow().isServerbound()",
          ctx.flow().isServerbound() is False)
    check(u"player() 可取", ctx.player() == u"player1")

    # 单个任务出错不影响其它
    ctx2 = network.IPayloadContext(network.PacketFlow.SERVERBOUND)
    order = []

    def boom():
        order.append(u"boom")
        raise RuntimeError(u"故意出错")

    ctx2.enqueueWork(boom)
    ctx2.enqueueWork(lambda: order.append(u"after"))
    done = ctx2.drainWork()
    check(u"出错后仍执行后续任务", order == [u"boom", u"after"], order)
    check(u"只统计成功的", done == 1, done)

    check(u"enqueueWork(None) 报错", raises(ctx2.enqueueWork, None))

    limit_ctx = network.IPayloadContext(network.PacketFlow.SERVERBOUND)
    for _index in range(3):
        limit_ctx.enqueueWork(lambda: None)
    check(u"drainWork 支持 limit",
          limit_ctx.drainWork(limit=2) == 2, limit_ctx.pending())
    check(u"limit 后还剩 1 个", limit_ctx.pending() == 1, limit_ctx.pending())

    # ------------------------------------------------------------
    section("PayloadRegistrar：注册")
    # ------------------------------------------------------------
    registry = network.PayloadRegistry()
    reg_event = network.RegisterPayloadHandlersEvent(registry)
    registrar = reg_event.registrar(u"1.18")
    check(u"registrar 记住版本", registrar.version == u"1.18", registrar.version)

    to_server_type = network.CustomPacketPayload_Type(
        registries.ResourceLocation(u"m", u"to_server"))
    to_client_type = network.CustomPacketPayload_Type(
        registries.ResourceLocation(u"m", u"to_client"))

    registrar.playToServer(to_server_type, network.StreamCodec.unit(u"s"), lambda p, c: None)
    registrar.playToClient(to_client_type, network.StreamCodec.unit(u"c"), lambda p, c: None)

    checks = registrar.getRegistrations()
    check(u"两条注册记录", len(checks) == 2, len(checks))
    check(u"方向正确",
          checks[0].flow is network.PacketFlow.SERVERBOUND
          and checks[1].flow is network.PacketFlow.CLIENTBOUND)
    check(u"注册表收到两条", registry.size() == 2, registry.size())

    check(u"同方向重复注册报错",
          raises(registrar.playToServer, to_server_type,
                 network.StreamCodec.unit(u"x"), lambda p, c: None))
    check(u"TYPE 为空报错",
          raises(registrar.playToServer, None, None, lambda p, c: None))
    check(u"缺处理函数报错",
          raises(registrar.playToServer, to_client_type,
                 network.StreamCodec.unit(u"x"), None))

    # 双向注册
    bidir_registry = network.PayloadRegistry()
    bidir_registrar = network.PayloadRegistrar(u"1", bidir_registry)
    bidir_type = network.CustomPacketPayload_Type(
        registries.ResourceLocation(u"m", u"both"))
    bidir_registrar.playBidirectional(bidir_type, network.StreamCodec.unit(u"b"),
                                      lambda p, c: None)
    check(u"双向注册产生两条记录",
          len(bidir_registrar.getRegistrations()) == 2,
          len(bidir_registrar.getRegistrations()))
    check(u"两个方向各一条",
          bidir_registrar.getRegistrations()[0].flow
          is network.PacketFlow.SERVERBOUND
          and bidir_registrar.getRegistrations()[1].flow
          is network.PacketFlow.CLIENTBOUND)

    check(u"optional() 返回自身可链式",
          network.PayloadRegistrar().optional() is not None)

    # ------------------------------------------------------------
    section("PacketDistributor：六个投递入口")
    # ------------------------------------------------------------
    distributor = network.PacketDistributor()
    payload = u"payload"

    distributor.sendToServer(payload)
    distributor.sendToPlayer(u"player", payload)
    distributor.sendToAllPlayers(payload)
    distributor.sendToPlayersInDimension(u"level", payload)
    distributor.sendToPlayersTrackingEntityAndSelf(u"entity", payload)
    distributor.sendToPlayersTrackingEntity(u"entity", payload)

    check(u"六次投递都被记录", distributor.sentCount() == 6,
          distributor.sentCount())
    descriptions = [item[0] for item in distributor.sent]
    check(u"目标描述齐全",
          descriptions == [u"server", u"player", u"all", u"dimension",
                           u"tracking+self", u"tracking"],
          descriptions)

    captured = []
    distributor.setSender(lambda recipients, payload: captured.append(
        (recipients, payload)))
    distributor.sendToServer(u"with_sender")
    check(u"设置 sender 后真正回调", len(captured) == 1, captured)
    check(u"回调收到目标与载荷",
          captured[0][1] == u"with_sender", captured)

    distributor.clear()
    check(u"clear 清空记录", distributor.sentCount() == 0)
    check(u"模块级单例存在",
          isinstance(network.PACKET_DISTRIBUTOR, network.PacketDistributor))

    # ------------------------------------------------------------
    section("端到端：照真实写法定义两个包并收发")
    # ------------------------------------------------------------
    # 对应 KeyPressPacket（客户端 → 服务端，带一个 byte 字段）
    class KeyPressPacket(network.CustomPacketPayload):
        TYPE = network.CustomPacketPayload_Type(
            registries.ResourceLocation(u"manaita_plus_legacy", u"key_press"))
        STREAM_CODEC = network.StreamCodec.of(
            lambda buffer, value: buffer.writeByte(value.key),
            lambda buffer: KeyPressPacket(buffer.readByte()))

        def __init__(self, key):
            self.key = int(key)

        @staticmethod
        def handle(packet, context):
            handled_keys.append((packet.key, context.flow().name()))

    # 对应 ChangeEntityDataPacket（服务端 → 客户端，带 UUID + byte）
    class ChangeEntityDataPacket(network.CustomPacketPayload):
        TYPE = network.CustomPacketPayload_Type(
            registries.ResourceLocation(u"manaita_plus_legacy",
                                        u"change_entity_data"))
        STREAM_CODEC = network.StreamCodec.of(
            lambda buffer, value: (buffer.writeUUID(value.id),
                                   buffer.writeByte(value.flag)),
            lambda buffer: ChangeEntityDataPacket(buffer.readUUID(),
                                                  buffer.readByte()))

        def __init__(self, entity_id, flag):
            self.id = entity_id
            self.flag = int(flag)

        @staticmethod
        def handle(packet, context):
            handled_packets.append((packet.id, packet.flag))

    handled_keys = []
    handled_packets = []

    # 对应 onRegisterPayloadHandlers
    e2e_registry = network.PayloadRegistry()
    e2e_event = network.RegisterPayloadHandlersEvent(e2e_registry)
    e2e_registrar = e2e_event.registrar(u"1.18")
    e2e_registrar.playToServer(KeyPressPacket.TYPE, KeyPressPacket.STREAM_CODEC,
                               KeyPressPacket.handle)
    e2e_registrar.playToClient(ChangeEntityDataPacket.TYPE,
                               ChangeEntityDataPacket.STREAM_CODEC,
                               ChangeEntityDataPacket.handle)

    check(u"两个包都注册了", e2e_registry.size() == 2, e2e_registry.types())

    # 编码 → 解码往返
    original = KeyPressPacket(3)
    restored = e2e_registry.roundtrip(original)
    check(u"往返后类型正确",
          isinstance(restored, KeyPressPacket), type(restored).__name__)
    check(u"往返后字段一致", restored.key == 3, restored.key)
    check(u"往返后是不同对象（真正走了编解码）",
          restored is not original)

    # 带 UUID 的包
    original2 = ChangeEntityDataPacket(u"uuid-xyz", 1)
    restored2 = e2e_registry.roundtrip(original2)
    check(u"UUID 字段往返正确", restored2.id == u"uuid-xyz", restored2.id)
    check(u"byte 字段往返正确", restored2.flag == 1, restored2.flag)

    # 派发：方向匹配
    sent_ok = e2e_registry.dispatch(KeyPressPacket(5),
                                    network.PacketFlow.SERVERBOUND,
                                    player=u"player1")
    check(u"服务端方向的包被派发", sent_ok is True)
    check(u"处理函数被调用", handled_keys == [(5, u"SERVERBOUND")], handled_keys)

    # 派发：方向不匹配应被拒绝
    handled_keys[:] = []
    wrong_flow = e2e_registry.dispatch(KeyPressPacket(9),
                                       network.PacketFlow.CLIENTBOUND)
    check(u"方向不匹配时不派发", wrong_flow is False)
    check(u"处理函数没被调用", handled_keys == [], handled_keys)

    # 客户端方向的包
    e2e_registry.dispatch(ChangeEntityDataPacket(u"id2", 2),
                          network.PacketFlow.CLIENTBOUND, player=u"player2")
    check(u"客户端方向的包被派发",
          handled_packets == [(u"id2", 2)], handled_packets)

    # 未注册的包
    class Rogue(network.CustomPacketPayload):
        TYPE = network.CustomPacketPayload_Type(
            registries.ResourceLocation(u"m", u"not_registered"))

    check(u"未注册的包不能编码", raises(e2e_registry.encode, Rogue()))
    check(u"未注册的包派发返回 False",
          e2e_registry.dispatch(Rogue(), network.PacketFlow.SERVERBOUND) is False)

    # 与事件系统联动：真实模组用 @SubscribeEvent 接收注册事件
    event.EventBusSubscriber.clear_pending()
    bus = event.IEventBus(u"manaita_plus_legacy")
    linked_registry = network.PayloadRegistry()
    registered_types = []

    def on_register(e):
        reg = e.registrar(u"1.18")
        reg.playToServer(KeyPressPacket.TYPE, KeyPressPacket.STREAM_CODEC,
                         KeyPressPacket.handle)
        registered_types.append(u"key_press")

    bus.subscribe(on_register, network.RegisterPayloadHandlersEvent)
    bus.post(network.RegisterPayloadHandlersEvent(linked_registry))
    check(u"通过事件总线完成注册", registered_types == [u"key_press"],
          registered_types)
    check(u"注册事件里注册的包进了注册表",
          linked_registry.get(KeyPressPacket.TYPE) is not None)

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    for java_name in (
        "net.minecraft.network.protocol.common.custom.CustomPacketPayload",
        "net.minecraft.network.protocol.common.custom.CustomPacketPayload$Type",
        "net.minecraft.network.codec.StreamCodec",
        "net.minecraft.network.FriendlyByteBuf",
        "io.netty.buffer.ByteBuf",
        "net.neoforged.neoforge.network.handling.IPayloadContext",
        "net.neoforged.neoforge.network.registration.PayloadRegistrar",
        "net.neoforged.neoforge.network.registration.PacketFlow",
        "net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent",
        "net.neoforged.neoforge.network.PacketDistributor",
    ):
        check(u"映射 {}".format(java_name), java_name in network.JAVA_MAP)

finally:
    event.EventBusSubscriber.clear_pending()

sys.exit(summary())
