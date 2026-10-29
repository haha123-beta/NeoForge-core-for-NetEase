"""JDK language oracle using explicitly labelled contract doubles, not Minecraft boot."""
from pathlib import Path
import subprocess
import tempfile
from workspace_paths import DEV_ROOT
JAVA = Path(r'E:\Java\jdk-21.0.10\bin\java.exe')
JAVAC = JAVA.with_name('javac.exe')
STUBS = DEV_ROOT / 'references/entity-superclass-r48/oracle-stubs'


def compare(source, class_name='A'):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / 'Probe.java'
        path.write_text(source + '''
public class Probe {public static void main(String[] args){
    TYPE a=new TYPE(new net.minecraft.world.entity.EntityType(),new net.minecraft.world.level.Level());
    a.tick();net.minecraft.nbt.CompoundTag tag=new net.minecraft.nbt.CompoundTag();
    a.capture(tag);a.value=20;a.restore(tag);
    System.out.print(a.observed+":"+a.value+":"+a.ticks+":"+a.tickCount+":"+tag.getInt("Value"));
}}'''.replace('TYPE', class_name), encoding='utf-8')
        compiled = subprocess.run([str(JAVAC), '-encoding', 'UTF-8', '-d', directory] +
            [str(p) for p in sorted(STUBS.rglob('*.java'))] + [str(path)], capture_output=True, text=True)
        assert compiled.returncode == 0, compiled.stderr
        result = subprocess.run([str(JAVA), '-cp', directory, 'Probe'], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return result.stdout
