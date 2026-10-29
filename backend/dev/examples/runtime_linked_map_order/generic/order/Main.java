package generic.order;
import java.util.Map;
import java.util.LinkedHashMap;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
@Mod("runtime_linked_map_example")
public class Main {
    public final Map<String,Integer> values = new LinkedHashMap<>(16,1,true);
    public int ticks;
    public Main() {
        values.put("a",1);
        values.put("b",2);
        NeoForge.EVENT_BUS.addListener(this::onTick);
    }
    private void onTick(ServerTickEvent.Post event) {
        ticks++;
        values.get("a");
    }
    public String order() {
        String result="";
        for (String key : values.keySet()) {
            result=result+key;
        }
        return result;
    }
}
