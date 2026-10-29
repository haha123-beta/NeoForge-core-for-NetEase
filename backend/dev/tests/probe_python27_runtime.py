# -*- coding: utf-8 -*-
from __future__ import print_function
import io
import json
import sys
import types

with io.open(sys.argv[1], "r", encoding="utf-8") as stream:
    data = json.load(stream)
namespace = {"__name__":"probe_source_loader"}
eval(compile(data["loader_source"].encode("utf-8"), "source_modules.py", "exec"), namespace)
SourceModuleLoader = namespace["SourceModuleLoader"]
raw_unicode_rejected = False
try:
    types.ModuleType(u"example.unicode_name")
except TypeError:
    raw_unicode_rejected = True
results = []
for side in ("SERVER", "CLIENT"):
    runtime = SourceModuleLoader(data["core"]["sources"])
    session_type = runtime.load("core.bundled_mods").BundledModSession
    session = session_type(data["core"]["sources"], data["contents"], side=side, runtime=runtime)
    session.loader.activate()
    for name in ("neocore_example_base", "neocore_example_addon"):
        assert session.loader.results[name].get("ready"), repr(session.loader.results)
    states = [session.loader.contexts[name].instance for name in
              ("neocore_example_base", "neocore_example_addon")]
    driver = runtime.load("core.content_events").ContentTickDriver(session.loader, side)
    for unused in range(150):
        driver.on_tick()
    assert driver.ticks == 100
    counters = [state["ticks"] for state in states]
    assert counters == ([100, 100] if side == "SERVER" else [0, 0]), repr(counters)
    session.close()
    assert all(state["closed"] for state in states)
    assert all(row["state"] == "unloaded" for row in session.loader.results.values())
    results.append({"side":side, "driver_ticks":driver.ticks,
                    "business_ticks":counters, "closed":True})
    runtime.close()
print(json.dumps({"python":sys.version, "raw_unicode_ModuleType_rejected":raw_unicode_rejected,
                  "results":results}, sort_keys=True))
