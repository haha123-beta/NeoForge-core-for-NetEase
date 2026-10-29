"""Export implemented public Java type identities for frontend import triage."""
import hashlib
import json
from pathlib import Path
from harness import Package, SCRIPTS_ROOT


def export(output):
    package = Package()
    names = package.load('core.java_api').collect_java_api()
    root = Path(SCRIPTS_ROOT)
    enum_base = package.load('java_stdlib.lang').Enum
    enum_types = {name.replace('$', '.'): {'constants': [item.name() for item in cls._values]}
        for name, cls in names.items() if isinstance(cls, type) and issubclass(cls, enum_base) and cls is not enum_base}
    report = {'schema_version': 1, 'java_types': sorted(names),
        'runtime_enum_types': enum_types,
        'runtime_superclasses': package.load('minecraft.runtime_classes').RuntimeClasses.contracts(),
        'runtime_generic_interfaces':package.load('minecraft.runtime_classes').RuntimeClasses.genericInterfaces(),
        'runtime_interface_contracts': package.load('minecraft.runtime_classes').RuntimeClasses.interfaceContracts(),
        'limits': ['A mapped type does not prove all its methods are implemented.'],
        'runtime_sha256': {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob('*.py'))}}
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    report = export(Path(__file__).with_name('java_import_index.json'))
    print('Exported Java identities:', len(report['java_types']))
