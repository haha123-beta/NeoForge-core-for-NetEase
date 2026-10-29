# -*- coding: utf-8 -*-
"""
θ 层自测：level_access.py + level.py + entity.py

真实依据（引用次数来自 dev/scan_neoforge_api.py）：
    Level 36、Player 36、Entity 31、ServerPlayer 20、LivingEntity 20
    getBlockState 40、isShiftKeyDown 15、playSound 14、getInventory 14、
    setBlock 13、gameEvent 11、getUUID 10、hurt 8、getBlockEntity 7、
    getAbilities 7、setHealth 6、getFluidState 5

验证点：
  1. LevelAccess 的「不支持」会被记录而不是崩掉（缺口可检测）
  2. InMemoryLevelAccess 的方块读写与变更记录
  3. Level 的方块/实体/音效转发，以及 Level.wrap 的身份对应
  4. ServerLevel.of 的 instanceof 等价语义
  5. Entity 的位置/坐标换算（负数向下取整）
  6. LivingEntity 的生命值夹取与受伤语义
  7. Player 的背包 add 合并、潜行、能力、经验、统计
  8. Inventory 的槽位边界与副手
  9. 端到端：建世界 → 放方块 → 生成实体 → 玩家交互，全程无引擎
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
mc = pkg.load("minecraft.core")
item_mod = pkg.load("minecraft.item")
block_mod = pkg.load("minecraft.block")
access_mod = pkg.load("minecraft.level_access")
level_mod = pkg.load("minecraft.level")
entity_mod = pkg.load("minecraft.entity")

ILevelAccess = access_mod.ILevelAccess
InMemory = access_mod.InMemoryLevelAccess
Level = level_mod.Level
ServerLevel = level_mod.ServerLevel
Entity = entity_mod.Entity
LivingEntity = entity_mod.LivingEntity
Player = entity_mod.Player
ServerPlayer = entity_mod.ServerPlayer


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("ILevelAccess：未适配的操作会被记录")
    # ------------------------------------------------------------
    # 这一条很重要：一个没接上的引擎方法不该让整个模组崩掉，
    # 但缺口必须留痕，否则「看起来接好了」其实什么都没做。
    abstract = ILevelAccess()
    check(u"抽象实现默认未适配", abstract.getBlockState(mc.BlockPos(0, 0, 0)) is None)
    check(u"缺口被记录", len(abstract.unsupported) == 1,
          len(abstract.unsupported))
    check(u"缺口记录了方法名",
          abstract.unsupported[0][0] == u"getBlockState",
          abstract.unsupported[0])
    check(u"assert_no_gaps 能发现缺口",
          raises(abstract.assert_no_gaps))

    clean = InMemory()
    clean.getBlockState(mc.BlockPos(0, 0, 0))
    check(u"内存实现没有缺口", clean.assert_no_gaps() is True)

    # ------------------------------------------------------------
    section("InMemoryLevelAccess：方块读写")
    # ------------------------------------------------------------
    access = InMemory()
    pos = mc.BlockPos(1, 2, 3)

    check(u"初始位置没有方块", access.getBlockState(pos) is None)
    check(u"初始是空方块", access.isEmptyBlock(pos) is True)

    stone = block_mod.Block(block_mod.BlockProperties()) \
        .setRegistryName(u"minecraft:stone")
    stone_state = stone.defaultBlockState()

    changed = access.setBlock(pos, stone_state)
    check(u"放置方块返回 True（发生了改变）", changed is True, changed)
    check(u"读取到刚放的方块",
          access.getBlockState(pos) is stone_state)
    check(u"不再是空方块", access.isEmptyBlock(pos) is False)
    check(u"方块数增加", access.blockCount() == 1, access.blockCount())

    check(u"放同样的方块返回 False（无改变）",
          access.setBlock(pos, stone_state) is False)
    check(u"移除方块", access.setBlock(pos, None) is True
          or access.getBlockState(pos) is None)

    access.clear()
    check(u"clear 清空世界", access.blockCount() == 0)

    # 方块位置用元组做键，与坐标对象解耦
    access.setBlock((5, 6, 7), stone_state)
    check(u"元组坐标也能用",
          access.getBlockState(mc.BlockPos(5, 6, 7)) is stone_state)

    check(u"非法位置报错", raises(access.getBlockState, u"not_a_pos"))

    # 变更记录
    access.clear()
    access.setBlock(pos, stone_state)
    access.setBlock(pos, None)
    check(u"变更被记录", len(access.block_updates) == 2,
          len(access.block_updates))

    # ------------------------------------------------------------
    section("InMemoryLevelAccess：实体与事件")
    # ------------------------------------------------------------
    access.clear()
    new_player = Player(access, mc.Vec3(0.0, 0.0, 0.0), name=u"张三")
    entity_id = access.addEntity(new_player)
    check(u"实体得到数字 id", entity_id is not None and new_player.getId()
          == entity_id, (entity_id, new_player.getId()))
    check(u"世界实体数为 1", access.entityCount() == 1)
    check(u"按 id 取回实体", access.getEntity(entity_id) is new_player)

    access.removeEntity(new_player)
    check(u"移除后实体数为 0", access.entityCount() == 0)
    check(u"移除不存在的实体返回 False",
          access.removeEntity(new_player) is False)

    access.playSound(new_player, u"minecraft:block.anvil.use", 1.0, 1.0)
    check(u"音效被记录", len(access.sounds_played) == 1)

    access.levelEvent(2001, pos, 0)
    check(u"世界事件被记录", len(access.level_events) == 1)
    check(u"事件记录含 id 与位置",
          access.level_events[0][0] == 2001, access.level_events[0])

    access.gameEvent(u"minecraft:block_place", pos)
    check(u"游戏事件被记录", len(access.game_events) == 1)

    check(u"客户端侧标记", InMemory(client_side=True).isClientSide() is True)
    check(u"服务端侧默认", InMemory().isClientSide() is False)

    # ------------------------------------------------------------
    section("Level：转发与身份对应")
    # ------------------------------------------------------------
    Level.resetWrappers()
    access2 = InMemory()
    world = Level.wrap(access2)

    check(u"wrap 得到 Level", isinstance(world, Level))
    check(u"同一个 access 对应同一个 Level（身份判断才成立）",
          Level.wrap(access2) is world)
    check(u"不同 access 是不同 Level",
          Level.wrap(InMemory()) is not world)
    check(u"getAccess 取回适配器", world.getAccess() is access2)
    check(u"服务端侧", world.isClientSide() is False)
    check(u"isServerSide 相反", world.isServerSide() is True)

    client_world = Level.wrap(InMemory(client_side=True))
    check(u"客户端侧", client_world.isClientSide() is True)

    check(u"wrap(None) 报错", raises(Level.wrap, None))
    check(u"直接构造 None 报错", raises(Level, None))

    # 方块转发
    world.setBlock(pos, stone_state)
    check(u"Level.setBlock 转发到适配器",
          access2.getBlockState(pos) is stone_state)
    check(u"Level.getBlockState 转发",
          world.getBlockState(pos) is stone_state)
    check(u"Level.isEmptyBlock 转发",
          world.isEmptyBlock(mc.BlockPos(9, 9, 9)) is True)
    check(u"位置元组也能传", world.getBlockState((1, 2, 3)) is stone_state)
    check(u"非法位置报错", raises(world.getBlockState, u"nope"))

    # 破坏方块
    check(u"destroyBlock 返回 True", world.destroyBlock(pos) is True)
    check(u"破坏后方块没了", world.getBlockState(pos) is None)
    check(u"破坏空气返回 False",
          world.destroyBlock(mc.BlockPos(0, 0, 0)) is False)

    # 音效与事件
    world.playSound(None, u"minecraft:block.anvil.place")
    world.levelEvent(2001, pos, 0)
    world.gameEvent(u"minecraft:block_place", pos)
    check(u"音效转发", len(access2.sounds_played) == 1)
    check(u"世界事件转发", len(access2.level_events) == 1)
    check(u"游戏事件转发", len(access2.game_events) == 1)

    # 维度
    check(u"默认维度是主世界",
          world.dimension() == u"minecraft:overworld", world.dimension())
    check(u"可设置维度",
          world.setDimension(u"minecraft:the_nether").dimension()
          == u"minecraft:the_nether")

    # 随机源
    check(u"getRandom 稳定",
          world.getRandom() is world.getRandom())

    # ------------------------------------------------------------
    section("ServerLevel：instanceof 等价语义")
    # ------------------------------------------------------------
    # 真实代码到处是 `if (level instanceof ServerLevel)`
    server_access = InMemory()
    server_level = ServerLevel(server_access)
    check(u"ServerLevel 是 Level 的子类",
          isinstance(server_level, Level))
    check(u"客户端侧不能建 ServerLevel",
          raises(ServerLevel, InMemory(client_side=True)))

    plain = Level.wrap(InMemory())
    promoted = ServerLevel.of(plain)
    check(u"of(服务端 Level) 得到 ServerLevel",
          isinstance(promoted, ServerLevel), type(promoted).__name__)
    check(u"已是 ServerLevel 时原样返回",
          ServerLevel.of(server_level) is server_level)
    check(u"of(客户端 Level) 返回 None（等价 instanceof 为假）",
          ServerLevel.of(client_world) is None)
    check(u"of(None) 返回 None", ServerLevel.of(None) is None)

    # ------------------------------------------------------------
    section("Entity：位置与坐标换算")
    # ------------------------------------------------------------
    ent_access = InMemory()
    entity = Entity(ent_access, mc.Vec3(1.5, 2.5, 3.5), u"test:thing")

    check(u"position 保留浮点", entity.position().toString() == u"(1.5, 2.5, 3.5)",
          entity.position().toString())
    check(u"getX/getY/getZ", (entity.getX(), entity.getY(), entity.getZ())
          == (1.5, 2.5, 3.5))

    bp = entity.blockPosition()
    check(u"blockPosition 向下取整",
          (bp.getX(), bp.getY(), bp.getZ()) == (1, 2, 3), tuple(bp))

    negative = Entity(ent_access, mc.Vec3(-0.5, -1.2, -3.9))
    neg_bp = negative.blockPosition()
    check(u"负数坐标向下取整（-0.5 -> -1）",
          (neg_bp.getX(), neg_bp.getY(), neg_bp.getZ()) == (-1, -2, -4),
          tuple(neg_bp))

    check(u"setPos 三个数", entity.setPos(4.0, 5.0, 6.0).getY() == 5.0)
    check(u"setPos 传 Vec3",
          entity.setPos(mc.Vec3(7.0, 8.0, 9.0)).getX() == 7.0)
    check(u"setPos 传元组", entity.setPos((1.0, 2.0, 3.0)).getZ() == 3.0)

    check(u"位置是拷贝不是引用（防止调用方改坏实体坐标）",
          entity.position() is not entity.position())

    # 改返回的向量不应影响实体本身
    tampered = entity.position()
    tampered.x = 999.0
    check(u"改动返回的坐标不影响实体", entity.getX() != 999.0,
          entity.getX())

    # 朝向
    check(u"默认 yaw 为 0", entity.getYRot() == 0.0)
    facing_south = entity.getViewVector()
    check(u"yaw=0 朝 +Z（南）", abs(facing_south.z - 1.0) < 1e-9,
          facing_south.toString())
    entity.setYRot(90.0)
    facing_west = entity.getViewVector()
    check(u"yaw=90 朝 -X（西）", abs(facing_west.x + 1.0) < 1e-9,
          facing_west.toString())
    entity.setYRot(0.0)

    # 身份
    check(u"getUUID 稳定", entity.getUUID() == entity.getUUID())
    check(u"不同实体 UUID 不同",
          entity.getUUID() != Entity(ent_access).getUUID())
    check(u"原本不是同一个实体", entity != Entity(ent_access))

    # 同 UUID 就是同一个实体（Minecraft 就是这么判的）
    twin = Entity(ent_access).setUUID(entity.getUUID())
    check(u"同 UUID 是同一个实体", entity == twin)
    check(u"可作字典键", {entity: u"v"}[twin] == u"v")

    check(u"getType 同名同对象",
          entity.getType() is entity.getType())
    check(u"getType 反映 identifier",
          entity.getType().toString() == u"test:thing",
          entity.getType().toString())

    # 碰撞箱
    box = entity.getBoundingBox()
    check(u"碰撞箱宽度为 0.6", abs(box.getXSize() - 0.6) < 1e-9,
          box.getXSize())
    check(u"碰撞箱高度为 1.8", abs(box.getYSize() - 1.8) < 1e-9,
          box.getYSize())

    # 世界连接
    check(u"level() 返回 Level", isinstance(entity.level(), Level))
    check(u"同一世界的实体拿到同一个 Level",
          entity.level() is Entity(ent_access).level())
    disconnected = Entity()
    check(u"未连接世界时 level() 报错", raises(disconnected.level))
    check(u"未连接世界时 remove() 不崩",
          disconnected.remove() is None)

    # ------------------------------------------------------------
    section("LivingEntity：生命值与受伤")
    # ------------------------------------------------------------
    living = LivingEntity(ent_access, mc.Vec3(0.0, 0.0, 0.0), u"test:mob",
                          max_health=20.0)
    check(u"初始满血", living.getHealth() == 20.0)
    check(u"getMaxHealth", living.getMaxHealth() == 20.0)
    check(u"活着", living.isAlive() is True)

    # setHealth 的夹取
    living.setHealth(999.0)
    check(u"setHealth 超上限被夹到 maxHealth（否则打不死）",
          living.getHealth() == 20.0, living.getHealth())
    living.setHealth(-5.0)
    check(u"setHealth 负数被夹到 0", living.getHealth() == 0.0,
          living.getHealth())
    living.setHealth(15.0)

    check(u"heal 加血", (living.heal(3.0), living.getHealth())[1] == 18.0)
    living.heal(100.0)
    check(u"heal 不会超过上限", living.getHealth() == 20.0)

    # 受伤
    check(u"hurt 返回 True", living.hurt(u"fall", 5.0) is True)
    check(u"生命值减少", living.getHealth() == 15.0, living.getHealth())
    check(u"伤害被记录", len(living.damage_taken) == 1)

    check(u"零伤害返回 False", living.hurt(u"none", 0.0) is False)
    check(u"负伤害返回 False", living.hurt(u"none", -1.0) is False)
    check(u"被拒绝的伤害不记录", len(living.damage_taken) == 1,
          len(living.damage_taken))

    living.setLastHurtByPlayer(u"某玩家")
    check(u"setLastHurtByPlayer", living.getLastHurtByPlayer() == u"某玩家")

    # 致死
    killed = LivingEntity(ent_access, max_health=10.0)
    killed.hurt(u"void", 100.0)
    check(u"致死后生命归零", killed.getHealth() == 0.0)
    check(u"致死后 isAlive 为假", killed.isAlive() is False)
    check(u"已死实体再受伤返回 False", killed.hurt(u"void", 1.0) is False)

    # setMaxHealth 会夹住当前血
    squeezed = LivingEntity(ent_access, max_health=20.0)
    squeezed.setMaxHealth(5.0)
    check(u"降低上限会夹住当前生命值", squeezed.getHealth() == 5.0,
          squeezed.getHealth())

    # ------------------------------------------------------------
    section("Inventory：槽位与合并")
    # ------------------------------------------------------------
    inventory = entity_mod.Inventory()
    check(u"默认 36 格", inventory.size == 36, inventory.size)
    check(u"护甲 4 格", len(inventory.armor) == 4)
    check(u"初始为空", inventory.isEmpty() is True)

    item_mod.ITEMS.clear()
    diamond = item_mod.ITEMS.DIAMOND
    dirt = item_mod.ITEMS.DIRT

    inventory.setItem(0, item_mod.ItemStack(diamond, 5))
    check(u"setItem/getItem",
          inventory.getItem(0).getCount() == 5)
    check(u"不再为空", inventory.isEmpty() is False)
    check(u"count 统计非空槽位", inventory.count() == 1, inventory.count())

    check(u"副手用 -1", inventory.getItem(-1) is inventory.offhand)
    inventory.setItem(-1, item_mod.ItemStack(dirt, 1))
    check(u"副手可设置", inventory.offhand.getCount() == 1)
    check(u"副手算进 count", inventory.count() == 2, inventory.count())

    check(u"越界报错", raises(inventory.getItem, 99))
    check(u"负槽位报错（除 -1）", raises(inventory.getItem, -2))
    check(u"setItem 越界报错", raises(inventory.setItem, 99, None))

    # 快捷栏
    check(u"默认选中第 0 格", inventory.getSelected() == 0)
    inventory.setSelected(3)
    check(u"切换快捷栏", inventory.getSelected() == 3)
    check(u"越界报错", raises(inventory.setSelected, 9))
    inventory.setSelected(0)

    # findSlot
    check(u"findSlot 命中", inventory.findSlot(diamond) == 0)
    check(u"findSlot 未命中返回 -1", inventory.findSlot(
        item_mod.ITEMS.EMERALD) == -1)

    # add：先合并再找空格
    merge_inv = entity_mod.Inventory()
    merge_inv.setItem(0, item_mod.ItemStack(diamond, 10))
    leftover = item_mod.ItemStack(diamond, 5)
    check(u"add 成功", merge_inv.add(leftover) is True)
    check(u"合并到已有栈", merge_inv.getItem(0).getCount() == 15,
          merge_inv.getItem(0).getCount())
    check(u"传入的栈被清空", leftover.isEmpty() is True,
          leftover.getCount())

    # add：新物品用空格
    fresh_inv = entity_mod.Inventory()
    fresh_inv.add(item_mod.ItemStack(dirt, 3))
    check(u"新物品占一个格子", fresh_inv.count() == 1)
    check(u"数量正确", fresh_inv.getItem(0).getCount() == 3)

    # add：满了返回 False
    full_inv = entity_mod.Inventory(size=1)
    full_inv.setItem(0, item_mod.ItemStack(diamond, 64))
    overflow = item_mod.ItemStack(dirt, 1)
    check(u"满了返回 False", full_inv.add(overflow) is False)

    check(u"add 空栈返回 True",
          fresh_inv.add(item_mod.ItemStack()) is True)

    # ------------------------------------------------------------
    section("Player：背包 / 潜行 / 能力 / 经验")
    # ------------------------------------------------------------
    player = Player(ent_access, mc.Vec3(0.0, 64.0, 0.0), name=u"测试玩家")

    check(u"getName", player.getName() == u"测试玩家")
    check(u"未命名时用 UUID 回退",
          Player(ent_access).getName().startswith(u"player_"))
    check(u"getGameProfile 含名字",
          player.getGameProfile()[u"name"] == u"测试玩家")

    # 手持
    player.getInventory().setItem(0, item_mod.ItemStack(diamond, 1))
    check(u"getMainHandItem", player.getMainHandItem().getItem() is diamond)
    check(u"getItemInHand(主手)",
          player.getItemInHand(mc.InteractionHand.MAIN_HAND).getItem()
          is diamond)

    player.setItemInHand(mc.InteractionHand.OFF_HAND,
                         item_mod.ItemStack(dirt, 1))
    check(u"setItemInHand 副手",
          player.getItemInHand(mc.InteractionHand.OFF_HAND).getItem() is dirt)
    check(u"取副手不影响主手",
          player.getMainHandItem().getItem() is diamond)

    # 潜行
    check(u"默认不潜行", player.isShiftKeyDown() is False)
    player.setShiftKeyDown(True)
    check(u"设置潜行后 isShiftKeyDown 为真",
          player.isShiftKeyDown() is True)
    check(u"isCrouching 一致", player.isCrouching() is True)
    player.setShiftKeyDown(False)

    # 能力
    abilities = player.getAbilities()
    check(u"默认不是创造模式", abilities.instabuild is False)
    check(u"默认不能飞", abilities.mayfly is False)
    abilities.setCreative(True)
    check(u"setCreative 后 instabuild 为真", abilities.instabuild is True)
    check(u"setCreative 后 mayfly 为真", abilities.mayfly is True)
    abilities.setCreative(False)

    # 经验
    check(u"初始 0 级", player.getExperienceLevel() == 0)
    player.giveExperiencePoints(5)
    check(u"5 点还不够升级", player.getExperienceLevel() == 0,
          player.getExperienceLevel())
    check(u"点数记录", player.getExperiencePoints() == 5)
    player.giveExperiencePoints(5)
    check(u"累计 10 点升到 1 级（阈值 7）",
          player.getExperienceLevel() == 1, player.getExperienceLevel())
    check(u"升级后剩余 3 点", player.getExperiencePoints() == 3,
          player.getExperiencePoints())
    check(u"负数被忽略",
          (player.giveExperiencePoints(-5),
           player.getExperiencePoints())[1] == 3)

    # 统计
    player.awardStat(u"minecraft:craft_item")
    player.awardStat(u"minecraft:craft_item")
    player.awardStat(u"minecraft:mine_block", 3)
    check(u"统计累加", player.getStat(u"minecraft:craft_item") == 2,
          player.getStat(u"minecraft:craft_item"))
    check(u"统计带数量", player.getStat(u"minecraft:mine_block") == 3)
    check(u"未统计的返回 0", player.getStat(u"nope") == 0)

    check(u"玩家眼睛高度 1.62", player.getEyeHeight() == 1.62)
    check(u"玩家是 LivingEntity 的子类",
          isinstance(player, LivingEntity))

    # ------------------------------------------------------------
    section("ServerPlayer")
    # ------------------------------------------------------------
    server_player = ServerPlayer(InMemory(), mc.Vec3(0.0, 64.0, 0.0),
                                 name=u"管理员")
    check(u"是 Player 的子类", isinstance(server_player, Player))
    check(u"名字正确", server_player.getName() == u"管理员")

    server_player.sendSystemMessage(mc.Component.literal(u"你好"))
    check(u"消息被记录", len(server_player.sent_messages) == 1)
    check(u"消息内容正确",
          server_player.sent_messages[0].getString() == u"你好")

    server_player.openMenu(u"某界面")
    check(u"开界面被记录", len(server_player.opened_menus) == 1)

    # ------------------------------------------------------------
    section("端到端：建世界 → 放方块 → 生成实体 → 玩家交互")
    # ------------------------------------------------------------
    # 整条链路不碰引擎，全靠 LevelAccess。
    Level.resetWrappers()
    e2e_access = InMemory()
    e2e_world = Level.wrap(e2e_access).setDimension(u"minecraft:overworld")

    crafting_block = block_mod.Block(block_mod.BlockProperties()
                                     .strength(3.0)) \
        .setRegistryName(u"manaita:crafting_manaita")
    crafting_state = crafting_block.defaultBlockState()

    target = mc.BlockPos(10, 64, 10)
    e2e_world.setBlock(target, crafting_state)
    check(u"方块放进世界",
          e2e_world.getBlockState(target) is crafting_state)
    check(u"方块实体不存在", e2e_world.getBlockEntity(target) is None)

    e2e_world.setBlockEntity(target, {u"kind": u"crafting"})
    check(u"方块实体可登记",
          e2e_world.getBlockEntity(target)[u"kind"] == u"crafting")

    # 生成玩家与生物
    player_e2e = Player(e2e_access, mc.Vec3(10.5, 64.0, 10.5), name=u"工人")
    e2e_world.addFreshEntity(player_e2e)
    check(u"玩家进入世界", e2e_access.entityCount() == 1)
    check(u"addFreshEntity 顺手连上了世界",
          player_e2e.level() is e2e_world,
          player_e2e.level())

    mob = LivingEntity(e2e_access, mc.Vec3(20.0, 64.0, 20.0), u"minecraft:pig",
                       max_health=10.0)
    e2e_world.addFreshEntity(mob)
    check(u"生物进入世界", e2e_access.entityCount() == 2)
    check(u"getPlayers 只返回玩家",
          len(e2e_world.getPlayers()) == 1, len(e2e_world.getPlayers()))

    # 最近的玩家
    nearest = e2e_world.getNearestPlayer(mc.BlockPos(11, 64, 10), 10.0)
    check(u"找到附近的玩家", nearest is player_e2e)
    check(u"超出距离时找不到",
          e2e_world.getNearestPlayer(mc.BlockPos(100, 64, 100), 5.0) is None)

    # 玩家破坏方块
    player_e2e.setShiftKeyDown(True)
    check(u"玩家正在潜行", player_e2e.isShiftKeyDown() is True)
    check(u"破坏方块成功", e2e_world.destroyBlock(target) is True)
    check(u"方块已消失", e2e_world.getBlockState(target) is None)

    # 生物受伤
    mob.setLastHurtByPlayer(player_e2e)
    mob.hurt(player_e2e, 4.0)
    check(u"生物掉血", mob.getHealth() == 6.0, mob.getHealth())
    check(u"记录了凶手", mob.getLastHurtByPlayer() is player_e2e)

    # 音效与统计
    e2e_world.playSound(player_e2e, u"minecraft:block.anvil.land", 1.0, 1.0)
    player_e2e.awardStat(u"minecraft:mine_block")
    check(u"音效已记录", len(e2e_access.sounds_played) == 1)
    check(u"统计已记录", player_e2e.getStat(u"minecraft:mine_block") == 1)

    # 全程没有「未适配」的调用
    check(u"端到端流程没有未适配的世界操作",
          e2e_access.assert_no_gaps() is True,
          e2e_access.unsupported)

    # ------------------------------------------------------------
    section("LoggingLevelAccess：记录并打印")
    # ------------------------------------------------------------
    logging_access = access_mod.LoggingLevelAccess(
        client_side=False, logger=lambda text: None)
    logging_world = Level.wrap(logging_access)
    logging_world.setBlock(target, crafting_state)
    logging_world.playSound(None, u"minecraft:block.anvil.place")
    logging_world.levelEvent(2001, target, 0)
    check(u"日志记录了 3 条操作", len(logging_access.log) == 3,
          len(logging_access.log))
    check(u"日志内容含方法名",
          u"setBlock" in logging_access.log[0], logging_access.log[0])
    check(u"行为与内存实现一致（真放了方块）",
          logging_access.getBlockState(target) is crafting_state)

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    for java_name in ("net.minecraft.world.level.Level",
                      "net.minecraft.server.level.ServerLevel"):
        check(u"level 映射 {}".format(java_name), java_name in level_mod.JAVA_MAP)
    for java_name in ("net.minecraft.world.entity.Entity",
                      "net.minecraft.world.entity.LivingEntity",
                      "net.minecraft.world.entity.player.Player",
                      "net.minecraft.server.level.ServerPlayer",
                      "net.minecraft.world.entity.player.Inventory",
                      "net.minecraft.world.entity.player.Abilities"):
        check(u"entity 映射 {}".format(java_name),
              java_name in entity_mod.JAVA_MAP)

    # 映射目标都能构造（冒烟）
    smoke_args = {
        entity_mod.Entity: (InMemory(),),
        entity_mod.LivingEntity: (InMemory(),),
        entity_mod.Player: (InMemory(),),
        entity_mod.ServerPlayer: (InMemory(),),
        entity_mod.Inventory: (),
        entity_mod.Abilities: (),
        entity_mod.EntityType.Builder: (entity_mod.Entity, entity_mod.MobCategory.MISC),
    }
    failures = []
    for java_name, impl in entity_mod.JAVA_MAP.items():
        # These Java enum/SAM types have no public zero-argument constructor.
        if impl in (entity_mod.MobCategory, entity_mod.EntityType.EntityFactory):
            try:
                impl()
                failures.append(u"{}: private/interface construction accepted".format(java_name))
            except Exception:
                pass
            continue
        if not isinstance(impl, type) and not hasattr(impl, "__getattr__"):
            failures.append(u"{}: 映射目标不可用".format(java_name))
            continue
        if not isinstance(impl, type):
            continue
        try:
            impl(*smoke_args.get(impl, ()))
        except Exception as error:
            failures.append(u"{}: {}".format(java_name, error))
    check(u"entity 映射的类都能构造", failures == [], failures)

finally:
    mc.Component.clearTranslations()
    item_mod.ITEMS.clear()
    block_mod.BLOCKS.clear()
    entity_mod.EntityType.clear()
    level_mod.Level.resetWrappers()
    access_mod.InMemoryLevelAccess.clear(InMemory())

sys.exit(summary())
