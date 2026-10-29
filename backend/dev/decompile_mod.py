# -*- coding: utf-8 -*-
"""
decompile_mod: CFR decompilation without executing input mod bytecode.
Configure NEOCORE_JAVA or JAVA_HOME for JDK 21; set NEOCORE_CFR_JAR to a JAR
containing org.benf.cfr.reader.Main. Original game/mod JARs are user inputs.
CFR: https://www.benf.org/other/cfr/
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile

DEV_ROOT = os.path.dirname(os.path.abspath(__file__))
from workspace_paths import PACK_ROOT as _PACK_ROOT
PACK_ROOT = str(_PACK_ROOT)

# 目录层级（实测确认，别少退或多退一层）：
#   <AddOn>/                                    ← WORKSPACE_ROOT
#   ├── 6b3fe067…/                              ← dirname(PACK_ROOT)
#   │   └── behavior_pack_7k1k1i4l/             ← PACK_ROOT（本文件在它的 dev/ 下）
#   └── 801edd61…/behavior_pack_aRJYws6C/       ← 测试包，真实模组在其 resources/ 下
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(PACK_ROOT))

# CFR 打包在 Bytecode Viewer 里；这两个路径都在本机已验证可用
_JAVA_HOME = os.environ.get('NEOCORE_JAVA_HOME') or os.environ.get('JAVA_HOME')
JAVA_EXE = os.environ.get('NEOCORE_JAVA') or (os.path.join(_JAVA_HOME, 'bin', 'java.exe' if os.name == 'nt' else 'java') if _JAVA_HOME else shutil.which('java')) or 'java'
BYTECODE_VIEWER_JAR = os.environ.get('NEOCORE_CFR_JAR', os.path.join(DEV_ROOT, 'vendor', 'cfr', 'cfr.jar'))
CFR_MAIN = "org.benf.cfr.reader.Main"

# 默认目标：兄弟附加包里的真实模组（砧板传承 / ManaitaPlus Legacy）
DEFAULT_MOD_DIR = os.path.join(
    WORKSPACE_ROOT,
    u"801edd61a8a74ed8b67f24bc355f6ecc",
    "behavior_pack_aRJYws6C",
    "resources",
    u"【砧板传承】[NeoForge]ManaitaPlus Legacy-0.1.0",
)

OUTPUT_ROOT = os.path.join(WORKSPACE_ROOT, "refs", "decompiled")


def find_class_dir(mod_dir):
    """模组里存 .class 的目录通常叫 sen/，找不到就退回整个模组目录。"""
    for candidate in ("sen", "classes", "bin"):
        path = os.path.join(mod_dir, candidate)
        if os.path.isdir(path):
            return path
    return mod_dir


def count_classes(path):
    total = 0
    for _root, _dirs, files in os.walk(path):
        for name in files:
            if name.endswith(".class"):
                total += 1
    return total


def build_command(class_dir, output_dir):
    return [
        JAVA_EXE,
        "-cp", BYTECODE_VIEWER_JAR,
        CFR_MAIN,
        class_dir,
        "--outputdir", output_dir,
        "--silent", "true",
    ]


def make_ascii_workspace(class_dir):
    """
    把 .class 复制到纯 ASCII 路径并打成 jar，返回 (临时根目录, jar 路径)。

    为什么必须搬到 ASCII 路径（实测踩到的坑）：
      真实模组目录名是「【砧板传承】[NeoForge]ManaitaPlus Legacy-0.1.0」，
      Java 按**系统默认编码**（中文 Windows 上是 GBK）解析命令行参数，
      中文路径直接变乱码，CFR 报 CannotLoadClassException / 拒绝访问。
      把输入搬到 ASCII 路径后中文完全不参与 Java 的解析。

    为什么打 jar 而不是直接给目录：
      **CFR 不接受目录** —— 实测传目录会抛
          CannotLoadClassException: <dir> - java.io.FileNotFoundException: (拒绝访问)
      改成传单个 .class 文件是好的，而传 jar 同样可以。
      打成一个 jar 只调一次 Java，比逐个文件调用快得多
      （184 个类逐个起 JVM 要几分钟）。真实模组本来也是 jar，形态一致。

    顺带印证了官方那条经验「mod 内不得使用中文文件名」——中文路径在工具链里到处是坑。
    """
    import zipfile

    temp_root = tempfile.mkdtemp(prefix="neocore_decompile_")
    jar_path = os.path.join(temp_root, "classes.jar")

    with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as jar:
        for root, dirs, files in os.walk(class_dir):
            dirs[:] = sorted(dirs)
            relative = os.path.relpath(root, class_dir)
            for name in sorted(files):
                if not name.endswith(".class"):
                    continue
                # jar 内部路径必须是 ASCII；class 目录名本身是英文包名，安全
                if relative == ".":
                    arcname = name
                else:
                    arcname = "{}/{}".format(relative.replace(os.sep, "/"), name)
                jar.write(os.path.join(root, name), arcname)

    return temp_root, jar_path


def main():
    mod_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MOD_DIR

    print(u"反编译器：CFR（打包在 Bytecode Viewer 内）")
    print(u"JAVA    : {}".format(JAVA_EXE))
    print(u"模组目录: {}".format(mod_dir))

    if not os.path.isdir(mod_dir):
        print(u"[错误] 模组目录不存在")
        return 1
    if not os.path.isfile(JAVA_EXE):
        print(u"[错误] 找不到 java: {}".format(JAVA_EXE))
        return 1
    if not os.path.isfile(BYTECODE_VIEWER_JAR):
        print(u"[错误] 找不到 Bytecode Viewer: {}".format(BYTECODE_VIEWER_JAR))
        return 1

    class_dir = find_class_dir(mod_dir)
    total = count_classes(class_dir)
    print(u".class 目录: {}".format(class_dir))
    print(u".class 数量: {}".format(total))

    if total == 0:
        print(u"[错误] 没找到任何 .class 文件")
        return 1

    module_name = os.path.basename(mod_dir.rstrip(u"\\/"))
    output_dir = os.path.join(OUTPUT_ROOT, module_name)
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    print(u"输出目录: {}".format(output_dir))
    print(u"")
    print(u"开始反编译（{} 个类，可能需要一两分钟）...".format(total))

    # 输入与输出都走 ASCII 路径，规避 Java 按 GBK 解析中文路径的问题
    temp_root, jar_path = make_ascii_workspace(class_dir)
    temp_output = os.path.join(temp_root, "out")
    if not os.path.isdir(temp_output):
        os.makedirs(temp_output)

    try:
        command = build_command(jar_path, temp_output)
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        output, _ = process.communicate()

        # 把结果搬回中文目录下
        produced = 0
        for root, dirs, files in os.walk(temp_output):
            dirs[:] = sorted(dirs)
            relative = os.path.relpath(root, temp_output)
            target_dir = output_dir if relative == "." else os.path.join(output_dir,
                                                                        relative)
            for name in files:
                if not name.endswith(".java"):
                    continue
                if not os.path.isdir(target_dir):
                    os.makedirs(target_dir)
                shutil.copy2(os.path.join(root, name),
                             os.path.join(target_dir, name))
                produced += 1
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    print(u"")
    print(u"反编译完成：产出 {} 个 .java".format(produced))
    if produced == 0:
        print(u"[错误] 没有产出任何 .java，CFR 的输出如下：")
        text = output.decode("utf-8", "replace") if output else u"(无输出)"
        for line in text.splitlines()[:30]:
            print(u"  " + line)
        return 1

    print(u"目录：{}".format(output_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
