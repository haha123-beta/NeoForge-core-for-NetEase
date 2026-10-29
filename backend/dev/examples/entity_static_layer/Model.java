package visuals;
import net.minecraft.client.model.geom.builders.MeshDefinition;
import net.minecraft.client.model.geom.builders.PartDefinition;
import net.minecraft.client.model.geom.builders.CubeListBuilder;
import net.minecraft.client.model.geom.builders.CubeDeformation;
import net.minecraft.client.model.geom.builders.LayerDefinition;
import net.minecraft.client.model.geom.PartPose;
public class Model {
 public static LayerDefinition layer(){
  MeshDefinition mesh=new MeshDefinition();PartDefinition root=mesh.getRoot();
  PartDefinition torso=root.addOrReplaceChild("torso",CubeListBuilder.create().texOffs(0,0).addBox(-2,0,-1,4,4,2),PartPose.offset(0,16,0));
  torso.addOrReplaceChild("hand",CubeListBuilder.create().texOffs(8,0).mirror().addBox(-1,-1,-1,2,3,2,new CubeDeformation(0.5f)).mirror(false).addBox(1,1,0,0,2,2),PartPose.offsetAndRotation(3,1,0,0,0.5f,0));
  return LayerDefinition.create((MeshDefinition)mesh,(int)16,(int)16);
 }
}