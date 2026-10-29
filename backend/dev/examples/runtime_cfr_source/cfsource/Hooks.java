package cfsource;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
@Mixin(value={Target.class}) public class Hooks {
 @Inject(method={"run(I)I"},at={@At(value="RETURN")},cancellable=true)
 private static void after(int n,CallbackInfoReturnable<Integer> ci){ci.setReturnValue(ci.getReturnValueI()+3);}
}