package entitysample;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.Level;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.nbt.CompoundTag;

public class CounterEntity extends Entity {
    public int constructorObserved;
    public int value=7;
    public int ticks;
    public CounterEntity(EntityType type, Level level) { super(type,level); }
    protected void defineSynchedData(SynchedEntityData.Builder builder) { constructorObserved=value; }
    protected void addAdditionalSaveData(CompoundTag tag) { tag.putInt("CounterValue",value); }
    protected void readAdditionalSaveData(CompoundTag tag) { value=tag.getInt("CounterValue"); }
    public void tick() { super.tick(); ticks++; value++; }
}
