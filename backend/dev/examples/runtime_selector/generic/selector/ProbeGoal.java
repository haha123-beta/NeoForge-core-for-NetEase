package generic.selector;
import net.minecraft.world.entity.ai.goal.Goal;
import java.util.EnumSet;

public class ProbeGoal extends Goal {
    public int ticks;
    public int starts;
    private int limit;
    public ProbeGoal(int limit) {
        super();
        this.limit = limit;
        setFlags(EnumSet.of(Goal.Flag.MOVE));
    }
    public boolean canUse() { return ticks < limit; }
    public boolean canContinueToUse() { return ticks < limit; }
    public void start() { starts++; }
    public void tick() { ticks++; }
}
