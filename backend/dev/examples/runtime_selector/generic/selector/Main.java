package generic.selector;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
import net.minecraft.world.entity.ai.goal.GoalSelector;
import net.minecraft.util.profiling.InactiveProfiler;

@Mod("runtime_selector_example")
public class Main {
    public final ProbeGoal goal;
    public final GoalSelector selector;
    public Main() {
        goal = new ProbeGoal(2);
        selector = new GoalSelector(() -> InactiveProfiler.INSTANCE);
        selector.addGoal(1, goal);
        NeoForge.EVENT_BUS.addListener(this::onTick);
    }
    private void onTick(ServerTickEvent.Post event) {
        selector.tick();
    }
}
