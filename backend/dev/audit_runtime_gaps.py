from workspace_paths import SCRIPTS_ROOT as _PROJECT_SCRIPTS
"""Inventory empty runtime modules and explicit unsupported boundaries; no compatibility claims."""
import ast
import json
from pathlib import Path
import sys
from py2to3lite import adapt_source


def audit(root):
    root = Path(root)
    empty, unsupported, errors = [], [], []
    for path in sorted(root.rglob('*.py')):
        source = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(adapt_source(source, relative))
        except Exception as error:
            errors.append({'file': relative, 'error': str(error)})
            continue
        meaningful = [node for node in tree.body if not isinstance(node, ast.Expr)
                      or not isinstance(node.value, ast.Constant)
                      or not isinstance(node.value.value, str)]
        if not meaningful and path.name != '__init__.py':
            empty.append(relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                function = node.exc.func
                if isinstance(function, ast.Name) and function.id in ('NotImplementedError', 'UnsupportedOperationException'):
                    message = node.exc.args[0] if node.exc.args else None
                    abstract = isinstance(message, ast.Constant) and isinstance(message.value, str) and message.value.startswith('Implement ')
                    unsupported.append({'category': 'abstract_contract' if abstract else 'unsupported_or_unclassified', 'file': relative, 'line': node.lineno,
                        'reason': ast.get_source_segment(adapt_source(source, relative), node)})
    return {'empty_modules': empty, 'explicit_unsupported': unsupported,
            'parse_errors': errors,
            'category_counts': {category: sum(row['category'] == category for row in unsupported)
                for category in ('abstract_contract', 'unsupported_or_unclassified')},
            'limits': ['Nonempty modules and methods are not proof of full implementation.',
                       'Abstract methods and intentionally unsupported operations also appear.',
                       'Category is a message-based hint, not proof that an interface or behavior is implemented.']}


if __name__ == '__main__':
    scripts = Path(_PROJECT_SCRIPTS)
    result = audit(scripts)
    target = Path(__file__).with_name('runtime_gap_inventory.json')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'empty_modules': result['empty_modules'],
        'explicit_unsupported_count': len(result['explicit_unsupported']),
        'parse_errors': result['parse_errors']}, ensure_ascii=False))
    sys.exit(bool(result['parse_errors']))
