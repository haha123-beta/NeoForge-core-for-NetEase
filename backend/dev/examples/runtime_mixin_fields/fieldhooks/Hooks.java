package fieldhooks;
import fielddemo.Target;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mutable;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
@Mixin(Target.class) public class Hooks {
 @Shadow @Final @Mutable private int value;
 @Inject(method="<init>(I)V",at=@At("TAIL"))
 private void after$init(int n,CallbackInfo ci){this.value=this.value+3;}
 @Inject(method="enabled(I)Z",at=@At("RETURN"),cancellable=true)
 private void after$enabled(int n,CallbackInfoReturnable<Boolean> ci){ci.setReturnValue(!ci.getReturnValueZ());}
}
