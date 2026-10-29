package generic;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;

@Mod("runtime_goal_example")
public class Main {
    public final ProbeGoal goal;
    public Main() {
        goal = new ProbeGoal(2);
        NeoForge.EVENT_BUS.addListener(this::onTick);
    }
    private void onTick(ServerTickEvent.Post event) {
        if (goal.canUse()) { goal.tick(); }
    }
}
