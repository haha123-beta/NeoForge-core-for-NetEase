# -*- coding: utf-8 -*-
"""Navigation/control adapters; engine pathfinding remains owned by LevelAccess."""
from __future__ import absolute_import
import math
import heapq
from java_stdlib._base import IllegalArgumentException
from minecraft.core import BlockPos
from minecraft.attributes import Attributes


class PathNavigation(object):
    def __init__(self, mob, level=None):
        self.mob = mob
        self._done = True
        self._generation = 0
        self._result = None
        self._target = None
        self._speed = 1.0

    def moveTo(self, *args):
        if len(args) == 2:
            target, speed = args
            pos = (target.getX(), target.getY(), target.getZ())
        elif len(args) == 4:
            pos, speed = tuple(args[:3]), args[3]
        else:
            raise IllegalArgumentException("moveTo expects (entity,speed) or (x,y,z,speed)")
        speed = float(speed)
        if speed <= 0 or any(math.isnan(float(v)) or math.isinf(float(v))
                             for v in pos + (speed,)):
            raise IllegalArgumentException("Invalid navigation target/speed")
        self._generation += 1
        generation = self._generation
        self._target, self._speed = pos, speed
        self._done, self._result = False, None

        def completed(result):
            if generation == self._generation:
                self._done, self._result = True, int(result)

        try:
            accepted = self.mob.getLevelAccess().moveEntityTo(self.mob, pos, speed, completed)
        except Exception:
            self._done = True
            raise
        if not accepted:
            self._done, self._result = True, -1
        return bool(accepted)

    def stop(self):
        was_running = not self._done
        self._generation += 1
        self._done = True
        self._target = None
        if was_running:
            self.mob.getLevelAccess().stopEntityNavigation(self.mob)

    def isDone(self):
        return self._done

    def isInProgress(self):
        return not self._done

    def getLastResult(self):
        return self._result

    def tick(self):
        if not self._done:
            self.mob.getLevelAccess().tickEntityNavigation(self.mob)

    def getTargetPos(self):
        if self._target is None:
            return None
        return BlockPos.containing(*self._target)


class GroundPathNavigation(PathNavigation):
    pass


class FlyingPathNavigation(PathNavigation):
    # Supported only when the engine definition supplies navigation.fly.
    pass


class WaterBoundPathNavigation(PathNavigation):
    # Supported only when the engine definition supplies navigation.generic.
    pass


class LookControl(object):
    def __init__(self, mob):
        self.mob = mob
        self._wanted = None

    def setLookAt(self, *args):
        if len(args) in (1, 3) and hasattr(args[0], "getEyePosition"):
            pos = args[0].getEyePosition()
            yaw, pitch = (args[1], args[2]) if len(args) == 3 else (10, 40)
            target = (pos.x, pos.y, pos.z)
        elif len(args) in (3, 5):
            target = tuple(args[:3])
            yaw, pitch = args[3:] if len(args) == 5 else (10, 40)
        else:
            raise IllegalArgumentException("Unsupported setLookAt arguments")
        self._wanted = (target, abs(float(yaw)), abs(float(pitch)))

    @staticmethod
    def _approach(current, target, maximum):
        delta = (target - current + 180.0) % 360.0 - 180.0
        return current + max(-maximum, min(maximum, delta))

    def tick(self):
        if self._wanted is None:
            return
        target, yaw_limit, pitch_limit = self._wanted
        eye = self.mob.getEyePosition()
        dx, dy, dz = target[0] - eye.x, target[1] - eye.y, target[2] - eye.z
        horizontal = math.sqrt(dx * dx + dz * dz)
        if horizontal > 0.000001:
            yaw = math.degrees(math.atan2(-dx, dz))
            self.mob.setYRot(self._approach(self.mob.getYRot(), yaw, yaw_limit))
        if horizontal > 0.000001 or abs(dy) > 0.000001:
            pitch = -math.degrees(math.atan2(dy, horizontal))
            self.mob.setXRot(self._approach(self.mob.getXRot(), pitch, pitch_limit))
        self._wanted = None


def find_flat_path(access, mob, target, limit=512):
    """Bounded 4-neighbor A* for tests: fixed height, no stairs/gravity simulation."""
    start = (int(math.floor(mob.getX())), int(math.floor(mob.getZ())))
    end = (int(math.floor(target[0])), int(math.floor(target[2])))
    y = int(math.floor(mob.getY()))
    if int(math.floor(target[1])) != y:
        return None
    def clear(node):
        x, z = node
        for height in range(int(math.ceil(mob.getHeight()))):
            state = access.getBlockState(BlockPos(x, y + height, z))
            if state is not None and not state.isAir():
                return False
        return True
    if not clear(end):
        return None
    frontier = [(0, 0, start)]
    previous, costs = {}, {start: 0}
    visited = 0
    while frontier and visited < limit:
        unused, cost, current = heapq.heappop(frontier)
        if cost != costs[current]:
            continue
        visited += 1
        if current == end:
            nodes = []
            while current != start:
                nodes.append((current[0] + 0.5, float(target[1]), current[1] + 0.5))
                current = previous[current]
            nodes.reverse()
            nodes.append(tuple(target))
            return nodes
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (current[0] + dx, current[1] + dz)
            new_cost = cost + 1
            if new_cost >= costs.get(neighbor, limit + 1) or not clear(neighbor):
                continue
            costs[neighbor], previous[neighbor] = new_cost, current
            distance = abs(neighbor[0] - end[0]) + abs(neighbor[1] - end[1])
            heapq.heappush(frontier, (new_cost + distance, new_cost, neighbor))
    return None


JAVA_MAP = {
    "net.minecraft.world.entity.ai.navigation.PathNavigation": PathNavigation,
    "net.minecraft.world.entity.ai.navigation.GroundPathNavigation": GroundPathNavigation,
    "net.minecraft.world.entity.ai.navigation.FlyingPathNavigation": FlyingPathNavigation,
    "net.minecraft.world.entity.ai.navigation.WaterBoundPathNavigation": WaterBoundPathNavigation,
    "net.minecraft.world.entity.ai.control.LookControl": LookControl,
}
