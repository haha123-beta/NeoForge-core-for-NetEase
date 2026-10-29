package other;
import net.neoforged.fml.common.Mod;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.neoforge.registries.DeferredRegister;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
@Mod("another_example") public class Main {
 public final DeferredRegister types=DeferredRegister.createEntities("another_example");
 public Main(IEventBus bus){
  types.register("counter",()->EntityType.Builder.of(Counter::new,MobCategory.MISC).sized(0.6f,1.8f).build("another_example:counter"));
  types.register(bus);
 }
}