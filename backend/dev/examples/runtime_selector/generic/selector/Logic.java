package generic.selector;
import net.minecraft.world.entity.ai.goal.GoalSelector;
import net.minecraft.util.profiling.InactiveProfiler;

public class Logic {
    public static int run() {
        GoalSelector selector = new GoalSelector(() -> InactiveProfiler.INSTANCE);
        ProbeGoal goal = new ProbeGoal(2);
        selector.addGoal(1, goal);
        selector.tick();
        selector.tick();
        selector.tick();
        return goal.starts * 10 + goal.ticks;
    }
}
