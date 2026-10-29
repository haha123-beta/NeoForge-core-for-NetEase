package generic;
import net.minecraft.world.entity.ai.goal.Goal;

public class ProbeGoal extends Goal {
    public int ticks;
    private int limit;
    public ProbeGoal(int limit) {
        super();
        this.limit = limit;
    }
    public boolean canUse() { return ticks < limit; }
    public boolean canContinueToUse() { return ticks < limit; }
    public void tick() { ticks++; }
}
