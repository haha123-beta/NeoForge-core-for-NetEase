# -*- coding: utf-8 -*-
# neoforge/network.py
# β 层：NeoForge 网络系统（自定义包载荷）
#
# 真实用法（从反编译源码逐字提取）：
#
#   // 1. 定义一个包
#   public class ChangeEntityDataPacket implements CustomPacketPayload {
#       public static final CustomPacketPayload.Type<ChangeEntityDataPacket> TYPE =
#           new CustomPacketPayload.Type(
#               ResourceLocation.fromNamespaceAndPath("manaita_plus_legacy",
#                                                     "change_entity_data"));
#       public static final StreamCodec<ByteBuf, ChangeEntityDataPacket> STREAM_CODEC =
#           new ...;                       // 匿名的编解码器
#       public final UUID id;
#       public final byte flag;
#
#       public static void handle(ChangeEntityDataPacket payload, IPayloadContext context) {
#           context.enqueueWork(() -> {
#               if (!context.flow().isClientbound()) return;
#               ClientPacketHandlers.handler(payload);
#           });
#       }
#
#       public CustomPacketPayload.Type<? extends CustomPacketPayload> type() {
#           return TYPE;
#       }
#   }
#
#   // 2. 注册
#   @SubscribeEvent
#   public static void onRegisterPayloadHandlers(RegisterPayloadHandlersEvent event) {
#       PayloadRegistrar registrar = event.registrar("1.18");
#       registrar.playToServer(KeyPressPacket.TYPE, KeyPressPacket.STREAM_CODEC,
#                              KeyPressPacket::handle);
#       registrar.playToClient(ChangeEntityDataPacket.TYPE,
#                              ChangeEntityDataPacket.STREAM_CODEC,
#                              ChangeEntityDataPacket::handle);
#   }
#
#   // 3. 发送
#   PacketDistributor.sendToServer(payload);
#   PacketDistributor.sendToPlayer(serverPlayer, payload);
#   PacketDistributor.sendToPlayersInDimension(serverLevel, payload);
#   PacketDistributor.sendToAllPlayers(payload);
#   PacketDistributor.sendToPlayersTrackingEntityAndSelf(entity, payload);
#
# 真实模组一共注册了 4 个 playToServer + 6 个 playToClient，全部走这套 API。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        IllegalStateException,
    )
    from java_stdlib.lang import java_to_string
    from neoforge.event import Event
    from neoforge.registries import ResourceLocation
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        IllegalStateException,
    )
    from lang import java_to_string  # type: ignore
    # 注意**不能**写成 `from event import Event` ——
    # `neoforge/` 在 sys.path 上，`event` 会命中 `neoforge/event/` 那个包，
    # 而包里的 `event.base` 又不在 sys.path 上，于是报
    # 「模块文件不存在: event.base」（实测踩到）。
    # 一律用点分全名。
    from neoforge.event.base import Event  # type: ignore
    from registries import ResourceLocation  # type: ignore


# ============================================================
# 网络方向
# ============================================================

class _Flow(object):
    """
    对应 NeoForge 的 PacketFlow。

    包的方向决定它由哪一端处理：
      SERVERBOUND —— 客户端发给服务端（playToServer 注册的）
      CLIENTBOUND —— 服务端发给客户端（playToClient 注册的）
    真实代码用 `context.flow().isClientbound()` 判断自己该不该处理。
    """

    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name

    def isClientbound(self):
        return self._name == u"CLIENTBOUND"

    def isServerbound(self):
        return self._name == u"SERVERBOUND"

    def toString(self):
        return self._name

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    def __hash__(self):
        return id(self)

    def __str__(self):
        return self._name

    def __repr__(self):
        return u"<PacketFlow.{}>".format(self._name)


class PacketFlow(object):
    """对应 net.neoforged.neoforge.network.registration.PacketFlow。"""

    SERVERBOUND = _Flow(u"SERVERBOUND")
    CLIENTBOUND = _Flow(u"CLIENTBOUND")


# ============================================================
# 缓冲区与编解码器
# ============================================================

from java_stdlib.byte_buffer import ByteBuf


class FriendlyByteBuf(ByteBuf):
    """
    对应 net.minecraft.network.FriendlyByteBuf / RegistryFriendlyByteBuf。

    真实的它建在 Netty 的 ByteBuf 上；基岩版没有 Netty，
    所以这里做一个**纯 Python 的读写缓冲**，接口保持一致。
    这样编解码器的翻译代码（writeInt / readUtf / ...）不用改写法。
    """

    def __init__(self, data=None):
        self._read_index = 0
        self._write_buffer = []
        if data is not None:
            # 传入已编码的数据（列表），便于自测里模拟「收到一段字节」
            self._write_buffer = list(data)

    # ---------------- 写 ----------------

    def _write(self, tag, value):
        self._write_buffer.append((tag, value))
        return self

    def writeBoolean(self, value):
        return self._write(u"bool", bool(value))

    def writeByte(self, value):
        return self._write(u"int", int(value))

    def writeShort(self, value):
        return self._write(u"int", int(value))

    def writeInt(self, value):
        return self._write(u"int", int(value))

    def writeLong(self, value):
        return self._write(u"long", int(value))

    def writeFloat(self, value):
        return self._write(u"float", float(value))

    def writeDouble(self, value):
        return self._write(u"double", float(value))

    def writeUtf(self, value):
        return self._write(u"utf", java_to_string(value))

    def writeUUID(self, value):
        return self._write(u"uuid", java_to_string(value))

    def writeResourceLocation(self, value):
        return self._write(u"location", java_to_string(value))

    def writeBlockPos(self, value):
        """BlockPos 写成 (x, y, z) 三元组。"""
        return self._write(u"blockpos", value)

    def writeNbt(self, value):
        return self._write(u"nbt", value)

    def writeVarInt(self, value):
        return self._write(u"varint", int(value))

    def writeEnum(self, value):
        return self._write(u"enum", java_to_string(value))

    # ---------------- 读 ----------------

    def _read(self, expected_tag=None):
        if self._read_index >= len(self._write_buffer):
            raise IllegalStateException(
                u"缓冲区已读完（需要 {}）".format(expected_tag or u"更多数据"))
        entry = self._write_buffer[self._read_index]
        self._read_index += 1
        if expected_tag is not None and entry[0] != expected_tag:
            raise IllegalStateException(
                u"缓冲区类型不匹配: 期望 {}，实际 {}".format(expected_tag,
                                                            entry[0]))
        return entry[1]

    def readBoolean(self):
        return bool(self._read(u"bool"))

    def readByte(self):
        return int(self._read_any((u"int", u"varint", u"long")))

    def readShort(self):
        return int(self._read_any((u"int", u"varint", u"long")))

    def readInt(self):
        return int(self._read_any((u"int", u"varint", u"long")))

    def readLong(self):
        return int(self._read_any((u"int", u"varint", u"long")))

    def readFloat(self):
        return float(self._read_any((u"float", u"double")))

    def readDouble(self):
        return float(self._read_any((u"float", u"double")))

    def readUtf(self):
        return java_to_string(self._read(u"utf"))

    def readUUID(self):
        return self._read_any((u"uuid", u"utf"))

    def readResourceLocation(self):
        return ResourceLocation(self._read_any((u"location", u"utf")))

    def readBlockPos(self):
        return self._read(u"blockpos")

    def readNbt(self):
        return self._read(u"nbt")

    def readVarInt(self):
        return int(self._read_any((u"varint", u"int", u"long")))

    def _read_any(self, tags):
        """
        读取指定标签集合里的任意一种。

        为什么要按标签集合读而不是直接取下一个：
          写入端可能用 writeByte 而读取端用 readInt（数值类型之间本来就互通），
          但**不该**把字符串当数字读出来。按标签集合校验能在类型错配时
          给出清楚的错误，而不是等到 int(u'hello') 抛一个看不懂的 ValueError。
        """
        if self._read_index >= len(self._write_buffer):
            raise IllegalStateException(
                u"缓冲区已读完（需要 {}）".format(u" 或 ".join(tags)))
        entry = self._write_buffer[self._read_index]
        if entry[0] not in tags:
            raise IllegalStateException(
                u"缓冲区类型不匹配: 期望 {}，实际 {}".format(
                    u" 或 ".join(tags), entry[0]))
        self._read_index += 1
        return entry[1]

    # ---------------- 状态 ----------------

    def readableBytes(self):
        return len(self._write_buffer) - self._read_index

    def toList(self):
        """导出底层序列（自测用；真实场景应交给引擎发送）。"""
        return list(self._write_buffer)

    def __repr__(self):
        return u"<FriendlyByteBuf 剩余 {} 项>".format(self.readableBytes())


# 兼容别名：真实代码里两种类型名都出现过
from java_stdlib.byte_buffer import ByteBuf
RegistryFriendlyByteBuf = FriendlyByteBuf


from minecraft.official_interfaces import StreamEncoder, StreamDecoder

class StreamCodec(StreamEncoder, StreamDecoder):
    """
    对应 net.minecraft.network.codec.StreamCodec。

    它负责「包对象 ↔ 字节」的互转。真实代码里是匿名的内部类，
    Python 里用这个类 + 编解码函数构造：

        STREAM_CODEC = StreamCodec.of(encode_fn, decode_fn)
        STREAM_CODEC = StreamCodec.unit(instance)      # 无字段的包

    也可以挂到包类上，让 PayloadRegistrar 直接取用。
    """

    def __init__(self, encoder=None, decoder=None):
        self._encoder = encoder
        self._decoder = decoder

    # ---------------- 构造 ----------------

    @staticmethod
    def of(encoder, decoder):
        return StreamCodec(encoder, decoder)

    @staticmethod
    def unit(instance):
        """无字段的包：编解码都返回同一个实例。"""
        def encode(buffer,value):
            from java_stdlib.lang import NullPointerException
            if value is None:raise NullPointerException()
            equals=getattr(value,'equals',None)
            equal=equals(instance) if equals else (value==instance if isinstance(value,(str,type(u''),int,bool)) else value is instance)
            if not equal:raise IllegalStateException('Unit codec value differs from constant')
        return StreamCodec(encode,lambda buffer:instance)

    # ---------------- 编解码 ----------------

    def encode(self, buffer, value):
        if self._encoder is None:
            from java_stdlib.lang import NullPointerException
            raise NullPointerException()
        return self._encoder.encode(buffer,value) if hasattr(self._encoder,'encode') else self._encoder(buffer,value)

    def decode(self, buffer):
        if self._decoder is None:
            from java_stdlib.lang import NullPointerException
            raise NullPointerException()
        return self._decoder.decode(buffer) if hasattr(self._decoder,'decode') else self._decoder(buffer)

    # ---------------- 组合 ----------------

    def apply(self,operation):
        if operation is None:
            from java_stdlib.lang import NullPointerException
            raise NullPointerException()
        return operation.apply(self) if hasattr(operation,'apply') else operation(self)
    def map(self,forward,backward):
        original=self
        def call(fn,value):
            if fn is None:
                from java_stdlib.lang import NullPointerException
                raise NullPointerException()
            return fn.apply(value) if hasattr(fn,'apply') else fn(value)
        return StreamCodec(lambda buffer,value:original.encode(buffer,call(backward,value)),lambda buffer:call(forward,original.decode(buffer)))
    def mapStream(self,mapping):
        original=self
        def target(buffer):
            if mapping is None:
                from java_stdlib.lang import NullPointerException
                raise NullPointerException()
            return mapping.apply(buffer) if hasattr(mapping,'apply') else mapping(buffer)
        return StreamCodec(lambda buffer,value:original.encode(target(buffer),value),lambda buffer:original.decode(target(buffer)))
    def cast(self):return self

    def __repr__(self):
        return u"<StreamCodec>"


# ============================================================
# 包载荷
# ============================================================

class CustomPacketPayload(object):
    """
    对应 net.minecraft.network.protocol.common.custom.CustomPacketPayload。

    模组的每个包都实现它：定义 TYPE（唯一标识）与 STREAM_CODEC（编解码），
    再提供一个静态 handle(payload, context)，最后由 registrar 注册。

    这个基类在 Python 侧主要起两个作用：
      1. 让 isinstance 判断成立（真实代码里有 `packet instanceof CustomPacketPayload`）；
      2. 提供默认的 type() —— 子类应覆盖为返回自己的 TYPE。
    """

    # 子类应覆盖：TYPE = CustomPacketPayload.Type(...)
    TYPE = None
    # 子类应覆盖：STREAM_CODEC = StreamCodec.of(...)
    STREAM_CODEC = None

    def type(self):
        if self.TYPE is None:
            raise IllegalStateException(
                u"{} 没有定义 TYPE".format(type(self).__name__))
        return self.TYPE

    # ---------------- 便捷工具 ----------------

    @staticmethod
    def make_type(namespace, path):
        return CustomPacketPayload_Type(ResourceLocation(namespace, path))

    def __repr__(self):
        payload_type = self.TYPE
        return u"<{} type={}>".format(type(self).__name__,
                                      payload_type if payload_type else u"未定义")


class CustomPacketPayload_Type(object):
    """
    对应 CustomPacketPayload.Type。

    它就是「包的唯一标识」：一个 ResourceLocation。
    registrar 用它把「收到的字节」对应回「该用哪个包类解码」。
    """

    def __init__(self,location):object.__setattr__(self,'location',location)
    def __setattr__(self,name,value):raise AttributeError('Payload Type record is immutable')
    def __delattr__(self,name):raise AttributeError('Payload Type record is immutable')
    def id(self):return self.location
    def toString(self):
        from java_stdlib.lang import JavaString
        return JavaString(u'Type[id='+java_to_string(self.location)+u']')

    def equals(self, other):
        if not isinstance(other, CustomPacketPayload_Type):
            return False
        return self.location == other.location

    def hashCode(self):
        return 0 if self.location is None else self.location.hashCode()

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<Type {}>".format(self.toString())


# Java 里的内部类写法是 CustomPacketPayload.Type
CustomPacketPayload.Type = CustomPacketPayload_Type


# ============================================================
# 处理上下文
# ============================================================

def _error_text(error):
    """Diagnostics must not raise while handling another exception on Python 2."""
    text_type = type(u'')
    try:
        return text_type(error)
    except Exception:
        try:
            value = repr(error)
            return value if isinstance(value, text_type) else value.decode('utf-8', 'replace')
        except Exception:
            return u'<unprintable exception>'


class IPayloadContext(object):
    """
    对应 net.neoforged.neoforge.network.handling.IPayloadContext。

    真实代码用到三件事：
      context.enqueueWork(() -> {...})   把处理逻辑排进主线程
      context.flow().isClientbound()     判断方向
      context.player()                   拿到相关玩家

    enqueueWork 的语义很重要：网络线程**不能**直接碰游戏世界，
    必须排到主线程执行。这里用队列实现，由引擎在 tick 时排空（见 drainWork）。
    """

    def __init__(self, flow, player=None, connection=None):
        self._flow = flow
        self._player = player
        self._connection = connection
        self._queue = []
        self._executed = []
        self._closed = False
        self.attempted = 0
        self._work_owner = None

    # ---------------- 查询 ----------------

    def flow(self):
        return self._flow

    def player(self):
        return self._player

    def connection(self):
        return self._connection

    # ---------------- 排队执行 ----------------

    def enqueueWork(self, work):
        """
        对应 enqueueWork(Runnable)。

        不立即执行 —— 与 Java 一致：网络线程上做的事要等主线程。
        自测与引擎都可以用 drainWork() 把它跑掉。
        """
        if self._closed or getattr(self._connection, 'active', True) is False:
            raise IllegalStateException("Payload context is closed")
        if not callable(work):
            raise IllegalArgumentException(u"enqueueWork 收到 None")
        if self._work_owner is None:
            self._queue.append(work)
        else:
            owner = self._work_owner()
            if owner is None:
                raise IllegalStateException("Payload work owner is no longer available")
            owner._enqueue_context(self, work)
        return None

    def pending(self):
        return len(self._queue)

    def drainWork(self, limit=None):
        """
        执行排队的任务（引擎 tick 里调用）。

        单个任务抛异常**不中断**后续任务 —— 一个包处理失败不该让整条队列停摆，
        但错误必须打印出来。
        返回成功执行的数量。
        """
        done = 0
        count = 0
        while self._queue and not self._closed:
            if limit is not None and count >= int(limit):
                break
            work = self._queue.pop(0)
            count += 1
            self.attempted += 1
            # Work may close its own context (and clear _work_owner) before it
            # raises. Keep only this invocation's owner for failure accounting.
            owner = self._work_owner() if self._work_owner is not None else None
            try:
                work()
                done += 1
                self._executed.append(True)
                if len(self._executed) > 128:
                    del self._executed[0]
            except Exception as error:
                if owner is not None:
                    owner._work_failed(error)
                # SDK/Python 2 output streams may have no Unicode encoding.
                message = _error_text(error).encode('ascii', 'backslashreplace').decode('ascii')
                print("[NeoCore network] queued work failed: " + message)
        return done

    def close(self):
        reference = self._work_owner
        self._work_owner = None
        self._closed = True
        self._queue = []
        self._player = self._connection = None
        owner = reference() if reference is not None else None
        if owner is not None:
            owner._forget_context(self)

    def __repr__(self):
        return u"<IPayloadContext flow={} 待处理={}>".format(self._flow,
                                                             len(self._queue))


# ============================================================
# 注册
# ============================================================

class _Registration(object):
    """一条包注册记录。"""

    def __init__(self, payload_type, codec, handler, flow, optional=False, version=u"1"):
        self.payload_type = payload_type
        self.codec = codec
        self.handler = handler
        self.flow = flow
        self.optional = optional
        self.version = version

    def __repr__(self):
        return u"<注册 {} {}>".format(self.flow.name(), self.payload_type)


class PayloadRegistrar(object):
    """
    对应 net.neoforged.neoforge.network.registration.PayloadRegistrar。

    真实用法：
        PayloadRegistrar registrar = event.registrar("1.18");
        registrar.playToServer(TYPE, STREAM_CODEC, Packet::handle);
        registrar.playToClient(TYPE, STREAM_CODEC, Packet::handle);
    """

    def __init__(self, version=u"1", registry=None):
        if version is None or not java_to_string(version):
            raise IllegalArgumentException("Payload registration version must not be empty")
        self.version = java_to_string(version)
        self._registry = registry
        self._registrations = []
        self._optional = False

    # ---------------- 链式开关 ----------------

    def optional(self):
        """
        对应 registrar.optional()：标记后续注册为「对端没有也不报错」。

        返回自身以便链式调用（与 Java 的 builder 风格一致）。
        """
        value = PayloadRegistrar(self.version, self._registry)
        value._optional = True
        return value

    def versioned(self, version):
        """对应 registrar.versioned(version)：指定协议版本。"""
        value = PayloadRegistrar(version, self._registry)
        value._optional = self._optional
        return value

    # ---------------- 注册 ----------------

    def _record(self, payload_type, codec, handler, flow):
        """构造一条注册记录，并做参数校验（不写入登记表）。"""
        if payload_type is None:
            raise IllegalArgumentException(u"注册时 payload TYPE 不能为空")
        if codec is None or not callable(handler):
            raise IllegalArgumentException(
                u"注册 {} 时没有提供处理函数".format(payload_type))
        return _Registration(payload_type, codec, handler, flow,
                             optional=self._optional, version=self.version)

    def _commit(self, records):
        """把记录写入登记表（含 TYPE 唯一性检查）。"""
        identities = set((r.payload_type.id().toString(), r.flow) for r in self._registrations)
        for record in records:
            identity = (record.payload_type.id().toString(), record.flow)
            if identity in identities:
                raise IllegalArgumentException("Duplicate payload registration")
            identities.add(identity)
        if self._registry is not None:
            self._registry._add_all(records)
        self._registrations.extend(records)
        return self

    def playToServer(self, payload_type, codec, handler):
        """注册客户端 → 服务端的包。"""
        return self._commit([self._record(payload_type, codec, handler,
                                          PacketFlow.SERVERBOUND)])

    def playToClient(self, payload_type, codec, handler):
        """注册服务端 → 客户端的包。"""
        return self._commit([self._record(payload_type, codec, handler,
                                          PacketFlow.CLIENTBOUND)])

    def playBidirectional(self, payload_type, codec, handler):
        """
        双向都能发。

        Java 里 playToServer / playToClient 有多个重载，
        Python 没有重载，所以双向用独立名字（同 register_event_bus 的处理思路）。
        这里一次登记两个方向 —— 同 TYPE 在两个方向各一条是允许的。
        """
        return self._commit([
            self._record(payload_type, codec, handler, PacketFlow.SERVERBOUND),
            self._record(payload_type, codec, handler, PacketFlow.CLIENTBOUND),
        ])

    def getRegistrations(self):
        return list(self._registrations)

    def __repr__(self):
        return u"<PayloadRegistrar v{} {} 条>".format(self.version,
                                                      len(self._registrations))


class RegisterPayloadHandlersEvent(Event):
    """
    对应 net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent。

    模组在 @SubscribeEvent 里订阅它，用 event.registrar(version) 取到注册器。
    """

    def __init__(self, registry=None):
        Event.__init__(self)
        self._registry = registry if registry is not None else PayloadRegistry()
        self._registrar = None

    def registrar(self, version=u"1"):
        self._registrar = PayloadRegistrar(version, self._registry)
        return self._registrar

    def getRegistry(self):
        return self._registry


# ============================================================
# 包注册表（运行时按方向派发）
# ============================================================

class PayloadRegistry(object):
    """
    已注册包的集合，运行时用它把「收到的字节」还原成包对象并调用处理函数。

    这不是 NeoForge 的某个具体类名，而是 Python 侧必需的一环：
    真实实现里这段逻辑在引擎内部，这里把它显式化，便于自测与诊断。
    """

    def __init__(self):
        self._by_type = {}
        self._frozen = False

    def _add(self, record):
        self._add_all([record])

    def _add_all(self, records):
        if self._frozen:
            raise IllegalStateException("Payload registration is frozen")
        identities = set((key, flow) for key, flows in self._by_type.items() for flow in flows)
        for record in records:
            identity = (record.payload_type.id().toString(), record.flow)
            if identity in identities:
                raise IllegalArgumentException("Duplicate payload type/direction")
            identities.add(identity)
        for record in records:
            self._by_type.setdefault(record.payload_type.id().toString(), {})[record.flow] = record

    def freeze(self):
        self._frozen = True

    def size(self):
        return len(self._by_type)

    def get(self, payload_type, flow=None):
        key = (payload_type.id().toString() if isinstance(payload_type, CustomPacketPayload_Type)
               else java_to_string(payload_type))
        records = self._by_type.get(key, {})
        if flow is not None:
            return records.get(flow)
        if len(records) > 1:
            raise IllegalStateException("Bidirectional payload requires an explicit flow")
        return next(iter(records.values())) if records else None

    def types(self):
        return sorted(self._by_type.keys())

    # ---------------- 收发 ----------------

    def encode(self, payload, flow=None):
        """把一个包对象编码成 FriendlyByteBuf。"""
        payload_type = payload.type()
        record = self.get(payload_type, flow)
        if record is None:
            raise IllegalStateException(
                u"包 {} 没有注册，无法编码".format(payload_type))

        buffer = FriendlyByteBuf()
        if record.codec is not None:
            record.codec.encode(buffer, payload)
        return buffer

    def decode(self, payload_type, buffer, flow=None):
        """按类型把缓冲区解码成包对象。"""
        record = self.get(payload_type, flow)
        if record is None:
            raise IllegalStateException(
                u"包 {} 没有注册，无法解码".format(payload_type))
        if record.codec is None:
            raise IllegalStateException(
                u"包 {} 没有编解码器".format(payload_type))
        return record.codec.decode(buffer)

    def dispatch(self, payload, flow, player=None):
        """
        按方向调用对应的处理函数。

        方向不匹配时**不调用**（等价于 Java 里 playToServer 的包不会走
        playToClient 的处理函数），返回 False。
        """
        payload_type = payload.type()
        record = self.get(payload_type, flow)
        if record is None:
            return False
        if record.flow is not flow:
            return False

        context = IPayloadContext(flow, player)
        record.handler(payload, context)
        return True

    def roundtrip(self, payload, flow=None):
        """编码再解码，返回还原出来的包对象（自测与诊断用）。"""
        return self.decode(payload.type(), self.encode(payload, flow), flow)

    def clear(self):
        self._by_type = {}

    def __repr__(self):
        return u"<PayloadRegistry {} 个包>".format(len(self._by_type))


# ============================================================
# 发送
# ============================================================

class PacketDistributor(object):
    """
    对应 net.neoforged.neoforge.network.PacketDistributor。

    真实代码用到的六个投递方式（从 Networking.java 逐条提取）：

        sendToServer(payload)
        sendToPlayer(serverPlayer, payload)
        sendToAllPlayers(payload)
        sendToPlayersInDimension(serverLevel, payload)
        sendToPlayersTrackingEntityAndSelf(entity, payload)
        sendToPlayersTrackingEntity(entity, payload)

    这里不真的发包（基岩版没有 Netty 通道），而是把「发往谁、发了什么」
    记录下来交给引擎适配器。这样上层逻辑可测，落地方式等接入引擎再定 ——
    与 γ 层 injector 的处理思路一致。
    """

    def __init__(self):
        self.sent = []          # [(目标描述, payload)]
        self._sender = None
        self._transport = None

    def setSender(self, sender):
        """
        设置真正的发送实现（由引擎适配器提供）。

        sender(recipients, payload, registry) —— recipients 是目标列表，
        语义由适配器解释。不设置时只记录，不报错。
        """
        self._sender = sender
        return None

    def setTransport(self, transport):
        if transport is not None and self._transport is not None and self._transport is not transport:
            raise IllegalStateException("A network transport already owns this distributor")
        self._transport = transport

    def _send(self, recipients, payload, description):
        self.sent.append((description, payload))
        # Native traffic is continuous; diagnostic history must not retain every
        # payload (and its mod objects) for the entire world session.
        if len(self.sent) > 128:
            del self.sent[0]
        if self._transport is not None:
            self._transport.send(recipients, payload, description)
        elif self._sender is not None:
            self._sender(recipients, payload)
        return len(recipients) if isinstance(recipients, (list, tuple)) else 1

    # ---------------- 六个投递入口 ----------------

    def sendToServer(self, payload):
        return self._send([u"server"], payload, u"server")

    def sendToPlayer(self, player, payload):
        return self._send([player], payload, u"player")

    def sendToAllPlayers(self, payload):
        return self._send([u"*"], payload, u"all")

    def sendToPlayersInDimension(self, level, payload):
        return self._send([level], payload, u"dimension")

    def sendToPlayersTrackingEntityAndSelf(self, entity, payload):
        return self._send([entity], payload, u"tracking+self")

    def sendToPlayersTrackingEntity(self, entity, payload):
        return self._send([entity], payload, u"tracking")

    # ---------------- 诊断 ----------------

    def sentCount(self):
        """Retained diagnostic history length (max 128), not a delivery count."""
        return len(self.sent)

    def clear(self):
        self.sent = []
        return None

    def __repr__(self):
        return "<PacketDistributor retained_history={}/128 (not delivery acknowledgements)>".format(len(self.sent))


# 全局单例：Java 里 PacketDistributor 的方法是静态的
PACKET_DISTRIBUTOR = PacketDistributor()


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.network.protocol.common.custom.CustomPacketPayload":
        CustomPacketPayload,
    "net.minecraft.network.protocol.common.custom.CustomPacketPayload$Type":
        CustomPacketPayload_Type,
    "net.minecraft.network.codec.StreamCodec": StreamCodec,
    "net.minecraft.network.FriendlyByteBuf": FriendlyByteBuf,
    "net.minecraft.network.RegistryFriendlyByteBuf": RegistryFriendlyByteBuf,
    "io.netty.buffer.ByteBuf": ByteBuf,
    "net.neoforged.neoforge.network.handling.IPayloadContext": IPayloadContext,
    "net.neoforged.neoforge.network.registration.PayloadRegistrar":
        PayloadRegistrar,
    "net.neoforged.neoforge.network.registration.PacketFlow": PacketFlow,
    "net.minecraft.network.protocol.PacketFlow": PacketFlow,
    "net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent":
        RegisterPayloadHandlersEvent,
    "net.neoforged.neoforge.network.PacketDistributor": PACKET_DISTRIBUTOR,
}


__all__ = [
    "PacketFlow",
    "FriendlyByteBuf", "ByteBuf", "RegistryFriendlyByteBuf", "StreamCodec",
    "CustomPacketPayload", "CustomPacketPayload_Type",
    "IPayloadContext",
    "PayloadRegistrar", "RegisterPayloadHandlersEvent", "PayloadRegistry",
    "PacketDistributor", "PACKET_DISTRIBUTOR",
    "JAVA_MAP",
]
