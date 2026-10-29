package argdemo;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;
@Mixin(Target.class) public class Hooks {
 @Shadow private static int bias;
 @ModifyArg(method="run()I",at=@At(value="INVOKE",target="Largdemo/Sink;accept(II)I"),index=1)
 private static int change(int original){return original+bias;}
}