# -*- coding: utf-8 -*-
"""Read-only source triage for unpacked mods. Findings are evidence, not compatibility proof."""
import argparse
import collections
import json
import re
from pathlib import Path

TOKEN = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27')
ANNOTATION = re.compile(r'@\s*(?:[\w$]+\.)*(Mixin|Inject|Redirect|Overwrite|ModifyArg|ModifyArgs|ModifyVariable|ModifyConstant|Accessor|Invoker|Shadow|WrapOperation|ModifyExpressionValue)\b')
IMPORT = re.compile(r'\bimport\s+(?:static\s+)?([\w$.*]+)\s*;')
COLLISION = re.compile(r'\.\s*(is|pass|or|and|not|in|from|print|exec|lambda|global|del)\s*\(')


def masked_java(text):
    return TOKEN.sub(lambda match: re.sub(r'[^\n]', ' ', match.group()), text)


def audit(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("Expected an unpacked mod directory")
    findings = []
    counts = collections.Counter()
    def add(path, line, kind, detail):
        findings.append({"file": path.relative_to(root).as_posix(),
                         "line": line, "kind": kind, "detail": detail})
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix == ".class":
            counts["class_files"] += 1
        elif path.suffix == ".py":
            counts["python_files"] += 1
        elif path.suffix == ".java":
            counts["java_files"] += 1
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            code = masked_java(text)
            for match in ANNOTATION.finditer(code):
                add(path, code.count("\n", 0, match.start()) + 1,
                    "mixin_annotation", match.group(1))
            for match in IMPORT.finditer(code):
                name = match.group(1)
                kind = None
                if name.startswith(("org.objectweb.asm.", "cpw.mods.modlauncher.")):
                    kind = "jvm_transformer"
                elif name.startswith("org.spongepowered.asm."):
                    kind = "mixin_dependency"
                elif name.startswith(("java.lang.reflect.", "sun.misc.", "jdk.internal.")):
                    kind = "reflection_or_jvm_internal"
                if kind:
                    add(path, code.count("\n", 0, match.start()) + 1, kind, name)
            for match in COLLISION.finditer(code):
                add(path, code.count("\n", 0, match.start()) + 1,
                    "python_keyword_call", match.group(1))
            for match in re.finditer(r'\b(native|synchronized)\b', code):
                add(path, code.count("\n", 0, match.start()) + 1,
                    "java_semantics", match.group(1))
        if path.suffix == ".json" and re.search(r'mixins?(?:[._-]|$)',path.stem.lower()):
            try:
                config = json.loads(path.read_text(encoding="utf-8-sig"))
                if not isinstance(config, dict):
                    raise ValueError("Configuration is not an object")
                add(path, 1, "mixin_config", "plugin=" + str(config.get("plugin")) +
                    "; required=" + str(config.get("required", False)))
            except (ValueError, OSError) as error:
                add(path, 1, "invalid_mixin_config", str(error))
    kinds = collections.Counter(row["kind"] for row in findings)
    return {"root": str(root), "complete_analysis": False,
            "status": "review_required" if findings else "no_known_markers",
            "files": dict(counts), "finding_counts": dict(kinds), "findings": findings,
            "limits": ["Lexical triage, not a Java parser or bytecode analyzer.",
                       "No findings does not prove the mod can run.",
                       "Mixin configuration and source declarations require semantic review.",
                       "No original source files were changed."]}


def markdown(report):
    lines = ["# 模组迁移风险扫描", "", "输入：" + report["root"], "",
             "这是静态初筛，不是兼容性认证；未修改输入代码。", "",
             "文件统计：" + json.dumps(report["files"], ensure_ascii=False), "",
             "风险分类：" + json.dumps(report["finding_counts"], ensure_ascii=False), "",
             "| 文件 | 行 | 类型 | 证据 |", "|---|---:|---|---|"]
    for row in report["findings"]:
        values = [str(row[key]).replace("|", "\\|").replace("\n", " ")
                  for key in ("file", "line", "kind", "detail")]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("--json", dest="json_output")
    parser.add_argument("--markdown", dest="markdown_output")
    args = parser.parse_args()
    report = audit(args.root)
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_output:
        Path(args.markdown_output).write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"files": report["files"], "findings": report["finding_counts"],
                      "status": report["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
