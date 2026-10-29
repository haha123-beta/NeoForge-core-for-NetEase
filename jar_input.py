"""JAR metadata inspection shared with the 0.8.7 conversion workbench."""
from __future__ import annotations
import hashlib
import json
import re
import uuid
import zipfile
from pathlib import Path, PurePosixPath
import tomllib

VERSION = '0.8.7'
CORE_UUID = 'b7747bdd-4788-5bb6-a00a-503718895642'
MAX_ENTRIES = 50000
MAX_EXPANDED = 512 * 1024 * 1024
MAX_MEMBER = 64 * 1024 * 1024


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def valid_entries(archive):
    entries = archive.infolist()
    if len(entries) > MAX_ENTRIES:
        raise ValueError('文件条目过多，无法生成格式样包')
    total = 0
    names = set()
    for entry in entries:
        name = entry.filename
        path = PurePosixPath(name)
        if ('\\' in name or name.startswith('/') or ':' in name or '\x00' in name
                or '..' in path.parts or not path.parts):
            raise ValueError('JAR 内存在不安全路径：' + name)
        key = name.rstrip('/').casefold()
        if key in names:
            raise ValueError('JAR 内存在重复或大小写冲突路径：' + name)
        names.add(key)
        if entry.flag_bits & 1:
            raise ValueError('暂不支持加密 JAR')
        total += entry.file_size
        if entry.file_size > MAX_MEMBER or total > MAX_EXPANDED:
            raise ValueError('JAR 解压后超过格式预览大小上限')
    return entries


def manifest_values(raw):
    lines = raw.decode('utf-8', errors='replace').replace('\r\n', '\n').splitlines()
    joined = []
    for line in lines:
        if line.startswith(' ') and joined:
            joined[-1] += line[1:]
        else:
            joined.append(line)
    return dict(line.split(': ', 1) for line in joined if ': ' in line)


def inspect_jar(path, original_name=None):
    path = Path(path)
    sha = digest(path)
    with zipfile.ZipFile(path) as archive:
        entries = valid_entries(archive)
        names = {entry.filename for entry in entries}
        platform, metadata_path, mods, dependencies, warnings = '未知', '', [], [], []
        for filename, loader in [('META-INF/neoforge.mods.toml', 'NeoForge'),
                                 ('META-INF/mods.toml', 'Forge')]:
            if filename not in names:
                continue
            metadata_path, platform = filename, loader
            if archive.getinfo(filename).file_size > 1024 * 1024:
                raise ValueError('模组元数据过大')
            data = tomllib.loads(archive.read(filename).decode('utf-8-sig'))
            manifest = manifest_values(archive.read('META-INF/MANIFEST.MF')) if 'META-INF/MANIFEST.MF' in names else {}
            for mod in data.get('mods', []):
                mod_id = str(mod.get('modId', '')).strip()
                if not mod_id:
                    raise ValueError('模组声明缺少 modId')
                version = str(mod.get('version', '未声明'))
                if version == '${file.jarVersion}':
                    version = manifest.get('Implementation-Version', version)
                mods.append({'id': mod_id, 'name': str(mod.get('displayName', mod_id)), 'version': version})
            for owner, items in data.get('dependencies', {}).items():
                for item in items:
                    dependencies.append(dict(item, owner=owner))
            break
        if not metadata_path and 'fabric.mod.json' in names:
            metadata_path, platform = 'fabric.mod.json', 'Fabric'
            if archive.getinfo(metadata_path).file_size > 1024 * 1024:
                raise ValueError('模组元数据过大')
            data = json.loads(archive.read(metadata_path))
            if not data.get('id'):
                raise ValueError('Fabric 元数据缺少 id')
            mods = [{'id': str(data['id']), 'name': str(data.get('name', data['id'])), 'version': str(data.get('version', '未声明'))}]
            dependencies = [{'modId': name, 'versionRange': value, 'owner': data['id'], 'type': 'required'}
                            for name, value in data.get('depends', {}).items()]
        if not mods:
            mods = [{'id': 'unknown_' + sha[:8], 'name': original_name or path.name, 'version': '未识别'}]
            warnings.append('未识别有效模组声明，使用占位身份，仅供目录检查。')
        if platform != 'NeoForge':
            warnings.append('来源为' + platform + '；当前实际转换仅接入 NeoForge。')
        warnings.append('导入仅识别信息；点击实际转换后查看结果，不以打包成功计实机兼容。')
        raw_id = mods[0]['id']
        safe_id = re.sub('[^a-zA-Z0-9_]', '_', raw_id)[:48] or 'unknown'
        pack = 'behavior_pack-' + safe_id
        script = 'nc_' + safe_id + '_' + sha[:8] + 'Scripts'
        classes = [e.filename for e in entries if e.filename.endswith('.class') and not e.is_dir()]
        source_files = [e.filename for e in entries if e.filename.endswith('.java') and not e.is_dir()]
        resources = [e.filename for e in entries if not e.is_dir() and not e.filename.endswith(('.class', '.java', '.jar'))]
        mc = [item.get('versionRange') for item in dependencies if item.get('modId') == 'minecraft']
        return {'sha256': sha, 'filename': original_name or path.name, 'size': path.stat().st_size,
                'platform': platform, 'metadata_path': metadata_path, 'mods': mods, 'dependencies': dependencies,
                'minecraft': ', '.join(str(v) for v in mc) or '未声明', 'pack': pack, 'script': script,
                'classes': len(classes), 'java_sources': len(source_files), 'resource_files': len(resources),
                'class_paths': classes, 'resource_paths': resources[:30], 'warnings': warnings,
                'format_preview_only': False, 'translated': False, 'engine_verified': False}



def preview_tree(info):
    return '\n'.join([info['pack']+'/', '├─ manifest.json', '├─ entities/', '└─ <自动生成的唯一脚本目录>/', '   ├─ modMain.py [转换成功后生成]', '   └─ resources/', '      ├─ 原包路径/*.py [实际机械转换]', '      └─ META-INF / assets / data [存在时保留]', '', '当前为目标布局；实际结果见转换记录。'])
