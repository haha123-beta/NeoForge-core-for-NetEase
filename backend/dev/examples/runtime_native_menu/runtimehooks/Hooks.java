package runtimehooks;
import runtimecontent.Audit;import runtimecontent.Example;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.inventory.MenuType;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mutable;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(AbstractContainerMenu.class) public class Hooks {
 @Shadow @Final @Mutable private MenuType<?> menuType;
 @SuppressWarnings("DataFlowIssue")
 @Inject(method="<init>",at=@At("TAIL"))
 private void onInit(MenuType<?> type,int windowId,CallbackInfo ci){AbstractContainerMenu menu=(AbstractContainerMenu)(Object)this;if(menu instanceof Example){this.menuType=null;Audit.tails=Audit.tails+1;Audit.seen=windowId;}}
}