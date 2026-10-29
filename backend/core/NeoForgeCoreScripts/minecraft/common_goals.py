# -*- coding: utf-8 -*-
"""Common goal lifecycles for translated mobs; targeting uses managed entities."""
from __future__ import absolute_import
from minecraft.goals import Goal


class MeleeAttackGoal(Goal):
    def __init__(self, mob, speed, following_target_even_if_not_seen=False):
        Goal.__init__(self)
        self.mob, self.speed = mob, float(speed)
        self._cooldown = 0
        self._repath = 0
        self.setFlags([Goal.Flag.MOVE, Goal.Flag.LOOK])

    def canUse(self):
        target = self.mob.getTarget()
        return target is not None and target.isAlive()

    def start(self):
        self._repath = 0

    def stop(self):
        self.mob.getNavigation().stop()

    def tick(self):
        target = self.mob.getTarget()
        if target is None or not target.isAlive():
            return
        self._cooldown = max(0, self._cooldown - 1)
        self.mob.getLookControl().setLookAt(target, 30, 30)
        reach = self.mob.getWidth() * 2.0 + target.getWidth()
        if self.mob.distanceToSqr(target) <= reach * reach:
            self.mob.getNavigation().stop()
            if self._cooldown == 0:
                self._cooldown = 20
                self.mob.doHurtTarget(target)
        else:
            self._repath -= 1
            if self._repath <= 0:
                self._repath = 10
                self.mob.getNavigation().moveTo(target, self.speed)


class HurtByTargetGoal(Goal):
    def __init__(self, mob, *ignored_classes):
        Goal.__init__(self)
        self.mob = mob
        self.ignored = ignored_classes
        self._seen = None
        self._attacker = None
        self.setFlags([Goal.Flag.TARGET])

    def canUse(self):
        attacker = self.mob.getLastHurtByMob()
        stamp = len(self.mob.damage_taken)
        if attacker is None or not attacker.isAlive() or stamp == self._seen:
            return False
        if any(isinstance(attacker, kind) for kind in self.ignored):
            return False
        self._attacker, self._seen = attacker, stamp
        return True

    def start(self):
        self.mob.setTarget(self._attacker)

    def canContinueToUse(self):
        return False


class RandomStrollGoal(Goal):
    def __init__(self, mob, speed, interval=120):
        Goal.__init__(self)
        self.mob, self.speed = mob, float(speed)
        self.interval = max(1, int(interval))
        self._destination = None
        self.setFlags([Goal.Flag.MOVE])

    def canUse(self):
        if self.mob.getTarget() is not None:
            return False
        random = self.mob.getRandom()
        if random.nextInt(self.interval) != 0:
            return False
        self._destination = (self.mob.getX() + random.nextInt(21) - 10,
                             self.mob.getY(),
                             self.mob.getZ() + random.nextInt(21) - 10)
        return True

    def start(self):
        self.mob.getNavigation().moveTo(*(self._destination + (self.speed,)))

    def canContinueToUse(self):
        return self.mob.getTarget() is None and not self.mob.getNavigation().isDone()

    def stop(self):
        self.mob.getNavigation().stop()


JAVA_MAP = {
    "net.minecraft.world.entity.ai.goal.MeleeAttackGoal": MeleeAttackGoal,
    "net.minecraft.world.entity.ai.goal.target.HurtByTargetGoal": HurtByTargetGoal,
    "net.minecraft.world.entity.ai.goal.RandomStrollGoal": RandomStrollGoal,
}
