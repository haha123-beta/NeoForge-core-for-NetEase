# -*- coding: utf-8 -*-
"""Versioned, JSON-safe entity snapshots. Engine IDs are deliberately not persisted."""
from __future__ import absolute_import
import json
from java_stdlib._base import IllegalArgumentException
from minecraft.nbt import CompoundTag, ListTag, TagValue, TagType, IntTag
from minecraft.attributes import AttributeModifier
from minecraft.core import Component


def encode_tag(value):
    if isinstance(value, Component):
        return {"kind": "component", "component_kind": value.kind, "text": value.text,
                "args": encode_tag(value.args), "style": encode_tag(value.style)}
    if isinstance(value, CompoundTag):
        return {"kind": "compound", "entries": [
            [key, value.getTagType(key), encode_tag(value.get(key))]
            for key in value.getAllKeys()]}
    if isinstance(value, ListTag):
        return {"kind": "list_tag", "items": [encode_tag(v) for v in value]}
    if isinstance(value, TagValue):
        return {"kind": "value", "type": value.tag_type, "value": encode_tag(value.value)}
    if isinstance(value, dict):
        return {"kind": "mapping", "entries": [[key, encode_tag(item)] for key, item in value.items()]}
    if isinstance(value, (tuple, list)):
        return {"kind": "list", "items": [encode_tag(v) for v in value]}
    return value


def decode_tag(value):
    if not isinstance(value, dict):
        return value
    kind = value.get("kind")
    if kind == "component":
        return Component(value["component_kind"], value["text"], decode_tag(value["args"]), decode_tag(value["style"]))
    if kind == "mapping":
        return dict((key, decode_tag(item)) for key, item in value["entries"])
    if kind is None:
        return dict((key, decode_tag(item)) for key, item in value.items())
    if kind == "compound":
        tag = CompoundTag()
        for key, tag_type, item in value["entries"]:
            tag.putTyped(key, decode_tag(item), tag_type)
        return tag
    if kind in ("list", "list_tag"):
        items = [decode_tag(item) for item in value["items"]]
        return ListTag(items) if kind == "list_tag" else items
    if kind == "value":
        decoded = decode_tag(value["value"])
        if value["type"] == TagType.INT:
            return IntTag.valueOf(decoded)
        return TagValue(decoded, value["type"])
    raise IllegalArgumentException("Unknown saved NBT representation")


def save_entity(entity, tag, include_id=True):
    if include_id:
        tag.putString("id", entity.getIdentifier())
    tag.putString("UUID", entity.getUUID())
    tag.putList("Pos", [entity.getX(), entity.getY(), entity.getZ()])
    tag.putList("Rotation", [entity.getYRot(), entity.getXRot()])
    tag.putInt("TickCount", entity.tickCount)
    tag.putCompound("NeoForgeData", entity.getPersistentData().copy())
    if hasattr(entity, "getAttributes"):
        rows = []
        for attribute, instance in entity.getAttributes()._instances.items():
            row = CompoundTag()
            row.putString("Name", attribute.getDescriptionId())
            row.putDouble("Base", instance.getBaseValue())
            modifiers = []
            for modifier in instance.getPermanentModifiers():
                entry = CompoundTag()
                entry.putString("Id", modifier.id())
                entry.putDouble("Amount", modifier.amount())
                entry.putInt("Operation", modifier.operation())
                modifiers.append(entry)
            row.putList("Modifiers", modifiers)
            rows.append(row)
        tag.putList("Attributes", rows)
        tag.putFloat("Health", entity.getHealth())
    if hasattr(entity, "isNoAi"):
        tag.putBoolean("NoAI", entity.isNoAi())
    attachments = entity.serializeAttachments(getattr(entity, "_registry_provider", None))
    if attachments is not None:
        tag.putCompound(entity.ATTACHMENTS_NBT_KEY, attachments)
    else:
        tag.remove(entity.ATTACHMENTS_NBT_KEY)
    entity._invoke_entity_hook('addAdditionalSaveData', tag)
    return tag


def load_entity(entity, tag):
    if tag.contains("id") and tag.getString("id") != entity.getIdentifier():
        raise IllegalArgumentException("Saved entity type does not match factory")
    if tag.contains("UUID"):
        entity._uuid = tag.getString("UUID")
    if tag.contains("Pos"):
        pos = tag.get("Pos")
        if len(pos) != 3:
            raise IllegalArgumentException("Invalid saved position")
        entity.setPos(*pos)
    if tag.contains("Rotation"):
        rotation = tag.get("Rotation")
        entity.setYRot(rotation[0])
        entity.setXRot(rotation[1])
    entity.tickCount = tag.getInt("TickCount")
    if tag.contains("NeoForgeData"):
        entity._persistent_data = tag.getCompound("NeoForgeData").copy()
    if hasattr(entity, "getAttributes"):
        instances = dict((attribute.getDescriptionId(), instance)
                         for attribute, instance in entity.getAttributes()._instances.items())
        for row in tag.get("Attributes") or []:
            instance = instances.get(row.getString("Name"))
            if instance is None:
                continue
            instance.setBaseValue(row.getDouble("Base"))
            instance.removeModifiers()
            for modifier in row.get("Modifiers") or []:
                instance.addPermanentModifier(AttributeModifier(
                    modifier.getString("Id"), modifier.getDouble("Amount"),
                    modifier.getInt("Operation")))
        if tag.contains("Health"):
            entity.setHealth(tag.getFloat("Health"))
    if hasattr(entity, "setNoAi") and tag.contains("NoAI"):
        entity.setNoAi(tag.getBoolean("NoAI"))
    if tag.contains(entity.ATTACHMENTS_NBT_KEY):
        entity.deserializeAttachments(getattr(entity, "_registry_provider", None),
            tag.getCompound(entity.ATTACHMENTS_NBT_KEY))
    entity._invoke_entity_hook('readAdditionalSaveData', tag)


def dumps(entity):
    tag = CompoundTag()
    if not entity.save(tag):
        raise IllegalArgumentException("Cannot save a removed entity")
    payload = {"version": 1, "nbt": encode_tag(tag)}
    return json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True)


def loads(text):
    payload = json.loads(text)
    if payload.get("version") != 1:
        raise IllegalArgumentException("Unsupported entity save version")
    tag = decode_tag(payload["nbt"])
    if not isinstance(tag, CompoundTag):
        raise IllegalArgumentException("Entity snapshot must contain a compound")
    return tag
