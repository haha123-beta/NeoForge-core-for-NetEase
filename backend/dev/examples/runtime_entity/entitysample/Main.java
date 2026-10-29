package entitysample;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.Level;

@Mod("runtime_entity_example")
public class Main {
    public int ticks;
    public Main() { NeoForge.EVENT_BUS.addListener(this::onTick); }
    private void onTick(ServerTickEvent.Post event) { ticks++; }
    public CounterEntity create(EntityType type, Level level) { return new CounterEntity(type,level); }
}
