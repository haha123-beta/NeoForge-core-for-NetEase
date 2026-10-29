package sample;
import net.neoforged.fml.common.Mod;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.neoforge.registries.DeferredRegister;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
@Mod("entity_generic_example") public class Main {
 public final DeferredRegister types=DeferredRegister.createEntities("entity_generic_example");
 public Main(IEventBus bus){
  types.register("counter",()->EntityType.Builder.of(Counter::new,MobCategory.MISC).sized(0.6f,1.8f).build("entity_generic_example:counter"));
  types.register(bus);
 }
}