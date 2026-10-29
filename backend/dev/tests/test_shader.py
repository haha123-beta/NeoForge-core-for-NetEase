# -*- coding: utf-8 -*-
"""
ζ 层自测：shader/（着色器处理）

真实依据（逐字来自反编译源码）：

    // CosmicShaderEventHandler.java:82-92
    event.registerShader(
        ShaderInstance(event.getResourceProvider(),
                                ManaitaPlusLegacy.rl("cosmic_neo_no_mask"),
                                DefaultVertexFormat.BLOCK),
        e -> {
            cosmicShader = (CCShaderInstance) e;
            cosmicTime = Objects.requireNonNull(cosmicShader.getUniform("time"));
            cosmicYaw  = Objects.requireNonNull(cosmicShader.getUniform("yaw"));
            cosmicTime.set((float)renderTime + renderFrame);
            cosmicShader.onApply(() -> cosmicTime.set(...));
        });

    // CCShaderInstance.java:75-155 —— 从着色器 JSON 解析 uniform
    parseUniformNode(json):
        name = GsonHelper.getAsString(obj, "name")
        type = UniformType.parse(typeStr)   // null 就抛
        count = GsonHelper.getAsInt(obj, "count")
        ... 按 count 细化类型 ...
        values = GsonHelper.getAsJsonArray(obj, "values")
        if (values.size() != count && values.size() > 1) throw
        if (count > 1 && values.size() == 1) Arrays.fill(...)

关键约束：`getUniform` 返回 None 会让 `Objects.requireNonNull` 抛异常，
**注册回调直接崩**。所以这不是观感问题，是功能性失败。

验证点：
  1. UniformType 解析与分量数
  2. UniformData 的存值语义（set / glUniform* / setSafe / 越界）
  3. ShaderInstance 从 JSON 解析 uniform（含真实代码的全部校验）
  4. getUniform 必须能取到 —— 否则真实代码会崩
  5. onApply 回调真的执行（时间推进逻辑依赖它）
  6. RegisterShadersEvent  立即调用回调（否则静态字段永远是 null）
  7. RenderStateShard 的身份稳定性
  8. 端到端：照真实写法注册宇宙着色器
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
uniform = pkg.load("shader.uniform")
opengl = pkg.load("shader.opengl")
material = pkg.load("shader.material")

UniformType = uniform.UniformType
UniformData = uniform.UniformData
UniformList = uniform.UniformList
RenderStateShard = opengl.RenderStateShard
ShaderInstance = material.ShaderInstance
RegisterShadersEvent = material.RegisterShadersEvent
ResourceProvider = material.ResourceProvider
DefaultVertexFormat = material.DefaultVertexFormat


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("UniformType")
    # ------------------------------------------------------------
    check(u"parse 命中 float", UniformType.parse(u"float") == UniformType.FLOAT)
    check(u"parse 大小写不敏感",
          UniformType.parse(u"VEC3") == UniformType.VEC3)
    check(u"parse 未命中返回 None（真实代码就是判 None）",
          UniformType.parse(u"not_a_type") is None)
    check(u"parse(None) 返回 None", UniformType.parse(None) is None)

    check(u"标量分量数为 1", UniformType.sizeOf(UniformType.FLOAT) == 1)
    check(u"vec3 分量数为 3", UniformType.sizeOf(UniformType.VEC3) == 3)
    check(u"mat4 分量数为 16", UniformType.sizeOf(UniformType.MAT4) == 16)
    check(u"未知类型分量数默认 1", UniformType.sizeOf(u"nope") == 1)

    check(u"整数类型判定", UniformType.isInteger(UniformType.INT) is True
          and UniformType.isInteger(UniformType.I_VEC3) is True)
    check(u"浮点类型判定", UniformType.isInteger(UniformType.VEC3) is False)
    check(u"values 覆盖常见类型", len(UniformType.values()) >= 14)

    # ------------------------------------------------------------
    section("UniformData：存值语义")
    # ------------------------------------------------------------
    u_time = UniformData(u"time", UniformType.FLOAT, 1)
    check(u"初始值为 0", u_time.getFloat() == 0.0, u_time.getFloat())

    u_time.set(12.5)
    check(u"set 生效", u_time.getFloat() == 12.5, u_time.getFloat())
    check(u"写入次数被记录", u_time.write_count == 1)

    u_time.set(1, 2, 3)     # 分量数不匹配也接受（真实代码不会这么用）
    check(u"set 多值被记录", len(u_time.getValues()) == 3, u_time.getValues())
    u_time.set([7.0])
    check(u"set 接受序列", u_time.getFloat() == 7.0)
    check(u"set 无参数报错", raises(u_time.set))

    # glUniform* 三个入口
    u_time.glUniformF(False, 3.5)
    check(u"glUniformF 生效", u_time.getFloat() == 3.5)
    u_time.glUniformD(False, 4.5)
    check(u"glUniformD 生效", u_time.getFloat() == 4.5)

    u_yaw = UniformData(u"yaw", UniformType.FLOAT, 1)
    u_yaw.glUniformI(9)
    check(u"glUniformI 生效（整数写入）", u_yaw.getFloat() == 9.0)

    # 整数类型拒绝非整数
    u_int = UniformData(u"count", UniformType.INT, 1)
    check(u"整数 uniform 接受整数", (u_int.set(5), u_int.getInt())[1] == 5)
    check(u"整数 uniform 拒绝字符串", raises(u_int.set, u"abc"))
    check(u"浮点 uniform 拒绝字符串", raises(u_time.set, u"abc"))

    # setSafe：真实代码用它「安全地写四个分量」
    u_scale = UniformData(u"externalScale", UniformType.FLOAT, 1)
    u_scale.setSafe(1.0, 2.0, 3.0, 4.0)
    check(u"setSafe 对标量只取第一个分量",
          len(u_scale.getValues()) == 1 and u_scale.getFloat() == 1.0,
          u_scale.getValues())

    u_vec3 = UniformData(u"pos", UniformType.VEC3, 3)
    u_vec3.setSafe(1.0, 2.0, 3.0, 4.0)
    check(u"setSafe 对 vec3 取前三个",
          len(u_vec3.getValues()) == 3, u_vec3.getValues())
    check(u"setSafe 值正确",
          u_vec3.getValues() == [1.0, 2.0, 3.0], u_vec3.getValues())

    # 越界
    check(u"getFloat 越界报错", raises(u_time.getFloat, 5))
    check(u"getInt 越界报错", raises(u_time.getInt, 5))

    # 位置
    check(u"默认 GL 位置是 -1（没有 GL）", u_time.getLocation() == -1)
    u_time.setLocation(3)
    check(u"setLocation 生效", u_time.getLocation() == 3)
    check(u"close 不报错", u_time.close() is None)
    check(u"getName/getType", u_time.getName() == u"time"
          and u_time.getType() == UniformType.FLOAT)
    check(u"toString 可读", u"time" in u_time.toString(), u_time.toString())

    # ------------------------------------------------------------
    section("UniformData.makeUniform：按 count 细化类型")
    # ------------------------------------------------------------
    check(u"float+count=1 仍是 float",
          UniformData.makeUniform(u"a", UniformType.FLOAT, 1).getType()
          == UniformType.FLOAT)
    check(u"float+count=2 变 vec2",
          UniformData.makeUniform(u"b", UniformType.FLOAT, 2).getType()
          == UniformType.VEC2)
    check(u"float+count=3 变 vec3",
          UniformData.makeUniform(u"c", UniformType.FLOAT, 3).getType()
          == UniformType.VEC3)
    check(u"float+count=4 变 vec4",
          UniformData.makeUniform(u"d", UniformType.FLOAT, 4).getType()
          == UniformType.VEC4)
    check(u"int+count=3 变 ivec3",
          UniformData.makeUniform(u"e", UniformType.INT, 3).getType()
          == UniformType.I_VEC3)
    check(u"vec3 不再细化",
          UniformData.makeUniform(u"f", UniformType.VEC3, 3).getType()
          == UniformType.VEC3)

    # ------------------------------------------------------------
    section("UniformList")
    # ------------------------------------------------------------
    ulist = UniformList()
    check(u"初始为空", ulist.size() == 0)
    ulist.add(UniformData(u"time", UniformType.FLOAT, 1))
    ulist.add(UniformData(u"yaw", UniformType.FLOAT, 1))
    check(u"add 后有两个", ulist.size() == 2)
    check(u"按名字取", ulist.get(u"time") is not None)
    check(u"未命中返回 None（真实代码 requireNonNull 兜）",
          ulist.get(u"nope") is None)
    check(u"names 排序", ulist.names() == [u"time", u"yaw"], ulist.names())
    check(u"可迭代", len(list(ulist)) == 2)
    check(u"len", len(ulist) == 2)
    check(u"add(None) 报错", raises(ulist.add, None))
    check(u"clear 清空", (ulist.clear(), ulist.size())[1] == 0)

    # ------------------------------------------------------------
    section("ShaderInstance：从 JSON 解析 uniform")
    # ------------------------------------------------------------
    # 对应真实着色器 JSON 的结构
    provider = ResourceProvider()
    provider.add(u"manaita_plus_legacy:cosmic_neo_no_mask", {
        u"blend": {u"enable": False},
        u"uniforms": [
            {u"name": u"time", u"type": u"float", u"count": 1,
             u"values": [0.0]},
            {u"name": u"yaw", u"type": u"float", u"count": 1, u"values": [0.0]},
            {u"name": u"pitch", u"type": u"float", u"count": 1,
             u"values": [0.0]},
            {u"name": u"externalScale", u"type": u"float", u"count": 1,
             u"values": [1.0]},
            {u"name": u"opacity", u"type": u"float", u"count": 1,
             u"values": [1.0]},
            {u"name": u"cosmicuvs", u"type": u"float", u"count": 40,
             u"values": [0.0]},
        ],
    })

    shader = ShaderInstance(provider, u"manaita_plus_legacy:cosmic_neo_no_mask",
                            DefaultVertexFormat.BLOCK)
    check(u"构造后 uniform 全部解析出来",
          shader.getUniformNames() == [u"cosmicuvs", u"externalScale",
                                       u"opacity", u"pitch", u"time", u"yaw"],
          shader.getUniformNames())
    check(u"getUniform 能取到 time", shader.getUniform(u"time") is not None)
    check(u"取到的是 UniformData",
          isinstance(shader.getUniform(u"time"), UniformData))
    check(u"取不到的返回 None", shader.getUniform(u"nope") is None)
    check(u"hasUniform 正确",
          shader.hasUniform(u"time") is True
          and shader.hasUniform(u"nope") is False)

    # 单个值铺满所有分量（对应真实代码的 Arrays.fill）
    uvs = shader.getUniform(u"cosmicuvs")
    check(u"count=40 生成 40 个分量",
          len(uvs.getValues()) == 40, len(uvs.getValues()))
    check(u"单值被铺满",
          uvs.getValues() == [0.0] * 40, uvs.getValues()[:3])

    check(u"记录位置与顶点格式",
          shader.getLocation() == u"manaita_plus_legacy:cosmic_neo_no_mask"
          and shader.getVertexFormat() is DefaultVertexFormat.BLOCK)

    # ------------------------------------------------------------
    section("ShaderInstance：解析校验（照抄真实代码）")
    # ------------------------------------------------------------
    def shader_with(node, location=u"t:test"):
        local = ResourceProvider()
        local.add(location, {u"uniforms": node})
        return ShaderInstance(local, location)

    check(u"缺少 name 报错",
          raises(shader_with, [{u"type": u"float", u"count": 1}]))
    check(u"缺少 type 报错",
          raises(shader_with, [{u"name": u"a", u"count": 1}]))
    check(u"未知类型报错",
          raises(shader_with,
                 [{u"name": u"a", u"type": u"nonsense", u"count": 1}]))
    check(u"values 个数不符报错",
          raises(shader_with,
                 [{u"name": u"a", u"type": u"vec3", u"count": 3,
                   u"values": [1.0, 2.0]}]))
    check(u"uniform 节点不是对象报错",
          raises(shader_with, [u"not_an_object"]))
    check(u"uniforms 不是数组报错",
          raises(lambda: shader_with(u"not_an_array")))

    # 没有 uniforms 节点是合法的（着色器可以没有 uniform）
    no_uniform = shader_with([])
    check(u"没有 uniform 也能构造", no_uniform.getUniformNames() == [])

    # 资源不存在要报错（真实代码抛 IOException）
    empty_provider = ResourceProvider()
    check(u"找不到着色器资源时构造失败",
          raises(ShaderInstance, empty_provider, u"missing:shader"))
    check(u"provider 记录了未命中",
          empty_provider.missingCount() == 1, empty_provider.missing)

    check(u"ResourceProvider 需要参数",
          raises(ShaderInstance, None, u"x"))
    check(u"JSON 非法时报错",
          raises(ResourceProvider().add, u"t:bad", u"{not valid json"))

    # ------------------------------------------------------------
    section("ShaderInstance：onApply 回调真的执行")
    # ------------------------------------------------------------
    # 真实代码靠它推进时间：cosmicShader.onApply(() -> cosmicTime.set(...))
    shader2 = ShaderInstance(provider, u"manaita_plus_legacy:cosmic_neo_no_mask",
                             DefaultVertexFormat.BLOCK)
    render_time = [100]
    render_frame = [0.5]
    cosmic_time = shader2.getUniform(u"time")

    def advance():
        cosmic_time.set(render_time[0] + render_frame[0])

    shader2.onApply(advance)
    check(u"回调已登记", shader2.callbackCount() == 1)
    check(u"apply 之前 uniform 未变", cosmic_time.getFloat() == 0.0)

    shader2.apply()
    check(u"apply 后回调执行了",
          cosmic_time.getFloat() == 100.5, cosmic_time.getFloat())
    check(u"apply 次数被记录", shader2.getApplyCount() == 1)

    render_time[0] = 200
    shader2.apply()
    check(u"再次 apply 回调再执行",
          cosmic_time.getFloat() == 200.5, cosmic_time.getFloat())

    check(u"onApply(None) 报错", raises(shader2.onApply, None))

    # 关闭后不能再 apply —— 否则会静默用到已释放的资源
    shader2.close()
    check(u"close 后可查状态", shader2.isClosed() is True)
    check(u"关闭后 apply 报错", raises(shader2.apply))

    # ------------------------------------------------------------
    section("CCShaderInstance")
    # ------------------------------------------------------------
    cc = ShaderInstance(provider,
                                 u"manaita_plus_legacy:cosmic_neo_no_mask",
                                 DefaultVertexFormat.BLOCK)
    check(u"create 得到 CCShaderInstance",
          isinstance(cc, ShaderInstance))
    check(u"是 ShaderInstance 的子类", isinstance(cc, ShaderInstance))
    check(u"create 后 uniform 可用", cc.getUniform(u"time") is not None)
    check(u"create 失败时抛 RuntimeException",
          raises(ShaderInstance, ResourceProvider(), u"missing:x"))
    try:
        ShaderInstance(ResourceProvider(), u"missing:x")
    except Exception as error:
        check(u"失败信息含着色器位置",
              u"missing:x" in u"{}".format(error), u"{}".format(error)[:80])

    # ------------------------------------------------------------
    section("RegisterShadersEvent")
    # ------------------------------------------------------------
    event = RegisterShadersEvent(provider)
    check(u"getResourceProvider 返回传入的 provider",
          event.getResourceProvider() is provider)
    check(u"默认也会造一个 provider",
          isinstance(RegisterShadersEvent().getResourceProvider(),
                     ResourceProvider))

    captured = []

    def on_registered(shader):
        captured.append(shader)

    event.registerShader(cc, on_registered)
    check(u"注册记录了一条", event.size() == 1)
    # 关键：回调**立即执行**。Java 里它等 GLSL 编译完才调；
    # 这边没有那个阶段，不立即调的话 cosmicShader 这些静态字段永远是 null。
    check(u"回调立即执行（否则静态字段永远是 null）",
          captured == [cc], captured)
    check(u"compiled 列表有记录", event.getCompiledShaders() == [cc])
    check(u"注册信息含位置",
          event.getRegisteredShaders()[0][0]
          == u"manaita_plus_legacy:cosmic_neo_no_mask",
          event.getRegisteredShaders())

    check(u"registerShader 不带回调也可以",
          RegisterShadersEvent(provider).registerShader(cc) is None)
    check(u"registerShader(None) 报错",
          raises(event.registerShader, None))

    # ------------------------------------------------------------
    section("RenderStateShard：身份稳定性")
    # ------------------------------------------------------------
    access = opengl.RenderStateShardAccess
    # 真实代码会把常量塞进链式 builder，身份必须稳定
    check(u"常量是稳定对象",
          access.EQUAL_DEPTH_TEST is access.EQUAL_DEPTH_TEST)
    check(u"不同常量不相等",
          access.EQUAL_DEPTH_TEST != access.LIGHT_MAP)
    check(u"同名状态相等",
          RenderStateShard(u"X") == RenderStateShard(u"X"))
    check(u"可作字典键",
          {access.LIGHT_MAP: 1}[access.LIGHT_MAP] == 1)
    check(u"toString 是名字",
          access.TRANSLUCENT_TRANSPARENCY.toString()
          == u"TRANSLUCENT_TRANSPARENCY")

    check(u"setupRenderState 记数",
          (access.CULL.setupRenderState(),
           access.CULL.setup_count)[1] == 1)
    check(u"clearRenderState 记数",
          (access.CULL.clearRenderState(),
           access.CULL.clear_count)[1] == 1)

    # ShaderStateShard 用 Supplier，因为着色器要等注册回调才有值
    holder = [None]
    shard = opengl.ShaderStateShard(lambda: holder[0])
    check(u"Supplier 未就绪时返回 None", shard.getShader() is None)
    holder[0] = cc
    check(u"Supplier 就绪后返回着色器", shard.getShader() is cc)
    check(u"ShaderStateShard 是 RenderStateShard",
          isinstance(shard, RenderStateShard))
    check(u"EmptyTextureStateShard 存在",
          isinstance(opengl.EmptyTextureStateShard(), RenderStateShard))
    check(u"RenderStateShard.ShaderStateShard 内部类写法",
          RenderStateShard.ShaderStateShard is opengl.ShaderStateShard)

    # ------------------------------------------------------------
    section("顶点格式")
    # ------------------------------------------------------------
    check(u"DefaultVertexFormat.BLOCK 是稳定对象",
          DefaultVertexFormat.BLOCK is DefaultVertexFormat.BLOCK)
    check(u"BLOCK 与 POSITION 不等",
          DefaultVertexFormat.BLOCK != DefaultVertexFormat.POSITION)
    check(u"真实BLOCK布局大小", DefaultVertexFormat.BLOCK.getVertexSize() == 32)
    check(u"Mode.QUADS 存在", material.VertexFormat.Mode.QUADS.name() == u"QUADS")

    # ------------------------------------------------------------
    section("端到端：照真实写法注册宇宙着色器")
    # ------------------------------------------------------------
    # 对应 CosmicShaderEventHandler 的静态字段
    state = {u"cosmicShader": None, u"cosmicTime": None, u"cosmicYaw": None}

    e2e_provider = ResourceProvider()
    e2e_provider.add(u"manaita_plus_legacy:cosmic_neo_no_mask", {
        u"uniforms": [
            {u"name": u"time", u"type": u"float", u"count": 1,
             u"values": [0.0]},
            {u"name": u"yaw", u"type": u"float", u"count": 1, u"values": [0.0]},
        ],
    })

    e2e_event = RegisterShadersEvent(e2e_provider)
    render_time = [0]
    render_frame = [0.0]

    # 对应 onRegisterShaders(RegisterShadersEvent event)
    def on_register_shaders(event):
        created = ShaderInstance(
            event.getResourceProvider(),
            u"manaita_plus_legacy:cosmic_neo_no_mask",
            DefaultVertexFormat.BLOCK)

        def on_ready(shader):
            state[u"cosmicShader"] = shader
            # 对应 Objects.requireNonNull(shader.getUniform("time"))
            for uniform_name in (u"time", u"yaw"):
                found = shader.getUniform(uniform_name)
                if found is None:
                    raise AssertionError(
                        u"getUniform({!r}) 返回 None —— "
                        u"真实代码的 requireNonNull 会在这里崩".format(
                            uniform_name))
            state[u"cosmicTime"] = shader.getUniform(u"time")
            state[u"cosmicYaw"] = shader.getUniform(u"yaw")
            state[u"cosmicTime"].set(render_time[0] + render_frame[0])
            shader.onApply(lambda: state[u"cosmicTime"].set(
                render_time[0] + render_frame[0]))

        event.registerShader(created, on_ready)

    on_register_shaders(e2e_event)

    check(u"着色器已建立", state[u"cosmicShader"] is not None)
    check(u"uniform 都取到了（没有走 requireNonNull 崩溃路径）",
          state[u"cosmicTime"] is not None and state[u"cosmicYaw"] is not None)
    check(u"初始时间写入", state[u"cosmicTime"].getFloat() == 0.0)

    # 模拟 tick 推进
    render_time[0] = 42
    render_frame[0] = 0.25
    state[u"cosmicShader"].apply()
    check(u"apply 后时间推进到 42.25",
          state[u"cosmicTime"].getFloat() == 42.25,
          state[u"cosmicTime"].getFloat())

    # ------------------------------------------------------------
    section("与 δ 层的分工")
    # ------------------------------------------------------------
    # δ 层决定「这个事件要不要派发」→ 跳过；
    # ζ 层保证「这个类存在且接口完整」→ 必须有。
    # 两者不矛盾，都要成立。
    rules = pkg.load("launcher_skip.rules")
    decision = rules.decide(
        u"net.neoforged.neoforge.client.event.RegisterShadersEvent")
    check(u"δ 层跳过 RegisterShadersEvent 的派发", decision.isSkip(),
          decision.toString())
    check(u"但 ζ 层仍然提供这个类",
          material.RegisterShadersEvent is not None)
    check(u"类在映射表里",
          u"net.neoforged.neoforge.client.event.RegisterShadersEvent"
          in material.JAVA_MAP)

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    for java_name in (
        "net.minecraft.client.renderer.ShaderInstance",
        "net.minecraft.client.renderer.RenderStateShard",
        "net.neoforged.neoforge.client.event.RegisterShadersEvent",
        "com.mojang.blaze3d.vertex.VertexFormat",
        "com.mojang.blaze3d.vertex.DefaultVertexFormat",
        "net.minecraft.server.packs.resources.ResourceProvider",
    ):
        check(u"映射 {}".format(java_name), java_name in material.JAVA_MAP)

finally:
    material.DefaultVertexFormat.clear()

sys.exit(summary())
