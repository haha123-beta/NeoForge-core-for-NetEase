"""Development parser backend with a versioned, source-preserving qualified-record fix."""
import ctypes
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

DEV = Path(__file__).resolve().parent
sys.path.insert(0, str(DEV / 'vendor/java_parser'))
from tree_sitter import Language
import tree_sitter_java

_LANGUAGE = None
_LIBRARY = None
_METADATA = None
_CAPSULE_NAME = b'tree_sitter.Language'


def language():
    global _LANGUAGE, _LIBRARY, _METADATA
    if _LANGUAGE is not None:
        return _LANGUAGE, dict(_METADATA)
    root = DEV / 'vendor/java_grammar_src'
    library = root / 'tree_sitter_java_qualified.dll'
    _METADATA = {'tree_sitter_python': importlib.metadata.version('tree-sitter'),
        'grammar': importlib.metadata.version('tree-sitter-java'), 'qualified_record_fix': False}
    if library.exists():
        manifest = json.loads((root / 'neocore_patch.json').read_text(encoding='utf-8'))
        digest = hashlib.sha256(library.read_bytes()).hexdigest()
        if digest != manifest['library_sha256']:
            raise ValueError('Java parser library differs from its build manifest')
        _LIBRARY = ctypes.CDLL(str(library.resolve()))
        entry = _LIBRARY.tree_sitter_java
        entry.restype = ctypes.c_void_p
        entry.argtypes = ()
        capsule = ctypes.pythonapi.PyCapsule_New
        capsule.restype = ctypes.py_object
        capsule.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p)
        _LANGUAGE = Language(capsule(entry(), _CAPSULE_NAME, None))
        if _LANGUAGE.abi_version != manifest['abi']:
            raise ValueError('Unexpected Java parser ABI')
        _METADATA.update(grammar=manifest['revision'], qualified_record_fix=True,
            library_sha256=digest)
    else:
        _LANGUAGE = Language(tree_sitter_java.language())
    return _LANGUAGE, dict(_METADATA)
