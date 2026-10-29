# -*- coding: utf-8 -*-
"""Host-driven config data lifecycle. Parsing and persistence belong to the host."""
from __future__ import absolute_import
from neoforge.event.fml.config import ModConfigEvent


class ConfigSession(object):
    def __init__(self, container, bus):
        self.container = container
        self.bus = bus
        self._loaded = []
        self._closed = False

    def apply(self, config, mapping):
        if self._closed:
            raise ValueError("Configuration session is closed")
        if not any(item is config for item in self.container.getConfigs()):
            raise ValueError("Configuration belongs to another container")
        if not isinstance(mapping, dict):
            raise ValueError("Configuration input must be a decoded mapping")
        reloading = any(item is config for item in self._loaded)
        config.getSpec().loadFrom(mapping)
        if not reloading:
            self._loaded.append(config)
        event_type = ModConfigEvent.Reloading if reloading else ModConfigEvent.Loading
        # The data is already applied when listeners run, as in FML setConfig.
        self.bus.post(event_type(config), strict=True)

    def close(self):
        if self._closed:
            return
        self._closed = True
        errors = []
        for config in reversed(self._loaded):
            try:
                config.getSpec()._loaded = False
                self.bus.post(ModConfigEvent.Unloading(config), strict=True)
            except Exception as error:
                errors.append(str(error))
        self._loaded = []
        if errors:
            raise RuntimeError("; ".join(errors))
