package other;
import net.minecraft.world.entity.Entity;import net.minecraft.world.entity.EntityType;import net.minecraft.world.level.Level;
import net.minecraft.network.syncher.SynchedEntityData;import net.minecraft.nbt.CompoundTag;
public class Counter extends Entity {
 public int value=7;public int ticks;
 public Counter(EntityType type,Level level){super(type,level);}
 protected void defineSynchedData(SynchedEntityData.Builder builder){}
 protected void readAdditionalSaveData(CompoundTag tag){value=tag.getInt("v");}
 protected void addAdditionalSaveData(CompoundTag tag){tag.putInt("v",value);}
 public void tick(){super.tick();ticks++;value++;}
}