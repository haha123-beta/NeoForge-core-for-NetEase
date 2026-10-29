package generic.sets;
import java.util.Set;
import java.util.LinkedHashSet;
import java.util.Iterator;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
@Mod("runtime_set_example")
public class Main {
    public final Set<String> values = new LinkedHashSet<>();
    public final Set<String> fixed = Set.of("fixed");
    public int ticks;
    public Main() {
        values.add("initial");
        NeoForge.EVENT_BUS.addListener(this::onTick);
    }
    private void onTick(ServerTickEvent.Post event) {
        ticks++;
        values.add("tick");
        Iterator<String> cursor = values.iterator();
        while (cursor.hasNext()) {
            if (cursor.next().equals("initial")) {
                cursor.remove();
            }
        }
    }
}
