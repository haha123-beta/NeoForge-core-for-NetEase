package demo;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
@Mixin(Target.class) public class Hooks {
 @Inject(method="run(I)I",at=@At("HEAD"),cancellable=true)
 private static void before$run(int n,CallbackInfoReturnable<Integer> ci){Audit.head();if(n<0)ci.setReturnValue(40);}
 @Inject(method="run(I)I",at=@At("RETURN"),cancellable=true)
 private static void after$run(CallbackInfoReturnable<Integer> ci){Audit.tail();ci.setReturnValue(ci.getReturnValueI()+3);}
}