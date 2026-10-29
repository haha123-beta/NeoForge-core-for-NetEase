import copy,json,math,struct,sys,tempfile,unittest,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from java_entity_geometry import convert,GeometryError
from build_entity_visuals import build,png_dimensions

MODEL='''package visuals;
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
}'''

def png(w=16,h=16):
 def chunk(name,raw):return struct.pack('>I',len(raw))+name+raw+struct.pack('>I',zlib.crc32(name+raw)&0xffffffff)
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\x00'+b'\x55\x99\x44\xff'*w)*h))+chunk(b'IEND',b'')

def declaration():
 return {'schema_version':1,'pack_id':'visual_test','entities':[
  {'identifier':name,'model_source':'model.java','layer_method':'layer','texture':'texture.png','collision':[0.6,1.8],'health':20}
  for name in ('first:creature','second:creature')]}

class EntityVisualTests(unittest.TestCase):
 def test_static_hierarchy_coordinates_rotations_mirror_inflate_and_planes(self):
  result=convert(MODEL,'model.java','layer','geometry.test.creature')
  self.assertEqual((result['bones'],result['cubes']),(3,3))
  bones=result['geometry']['minecraft:geometry'][0]['bones'];torso,hand=bones[1:]
  self.assertEqual(torso['pivot'],[0,8,0]);self.assertEqual(torso['cubes'][0]['origin'],[-2,4,-1])
  self.assertEqual(hand['pivot'],[3,7,0]);self.assertEqual(hand['parent'],'torso')
  self.assertAlmostEqual(hand['rotation'][1],math.degrees(0.5));self.assertEqual(hand['cubes'][0]['origin'],[2,5,-1])
  self.assertEqual(hand['cubes'][0]['inflate'],0.5);self.assertTrue(hand['cubes'][0]['mirror'])
  self.assertNotIn('mirror',hand['cubes'][1]);self.assertEqual(hand['cubes'][1]['size'][0],0)
  changed=convert(MODEL.replace('torso','body2').replace('hand','arm2').replace('visuals','another'),'new.java','layer','geometry.another.creature')
  self.assertEqual((changed['bones'],changed['cubes']),(3,3))
  cancelled=MODEL.replace('PartPose.offset(0,16,0)','PartPose.offsetAndRotation(64,16,0,0,0,3.1415927f)').replace('PartPose.offsetAndRotation(3,1,0','PartPose.offsetAndRotation(-64,1,0')
  large=convert(cancelled,'cancelled.java','layer','geometry.test.cancelled')
  # After a half turn, the child near unrotated x=0 moves near x=128 pixels.
  # Bounding only the summed, unrotated pivots would clip this valid model.
  description=large['geometry']['minecraft:geometry'][0]['description']
  self.assertGreaterEqual(description['visible_bounds_width'],21)
 def test_unknown_calls_flow_types_replacements_and_empty_models_reject(self):
  for original,replacement in [('MeshDefinition mesh=new MeshDefinition();','MeshDefinition mesh=new MeshDefinition();if(true){}'),
      ('texOffs(0,0)','unknown(0,0)'),('"hand"','"torso"'),('builders.MeshDefinition','fake.MeshDefinition'),
      ('4,4,2','-4,4,2'),('PartPose.offset(0,16,0)','PartPose.offsetAndRotation(0,16,0,0,0)'),
      ('PartPose.offset(0,16,0)','PartPose.offset(0,16,0).unknown()')]:
   with self.subTest(replacement=replacement),self.assertRaises(GeometryError):convert(MODEL.replace(original,replacement),'model.java','layer','geometry.test.creature')
 def test_two_namespaces_bound_geometry_texture_controller_manifest_and_inputs(self):
  with tempfile.TemporaryDirectory() as tmp:
   source=Path(tmp)/'input';source.mkdir();(source/'model.java').write_text(MODEL,encoding='utf-8');(source/'texture.png').write_bytes(png())
   output=Path(tmp)/'output';report=build(source,output,declaration());self.assertEqual(report['status'],'STATIC_VISUAL_TEST_ONLY')
   resource=output/'resource_pack-visual_test';behavior=output/'behavior_pack-visual_test'
   r=json.loads((resource/'manifest.json').read_bytes());b=json.loads((behavior/'manifest.json').read_bytes())
   self.assertEqual(b['dependencies'],[{key:r['header'][key] for key in ('uuid','version')}])
   for namespace in ('first','second'):
    client=json.loads((resource/'entity'/f'{namespace}__creature.entity.json').read_bytes())['minecraft:client_entity']['description']
    geometry=json.loads((resource/'models/entity'/f'{namespace}__creature.geo.json').read_bytes())['minecraft:geometry'][0]
    self.assertEqual(client['identifier'],namespace+':creature');self.assertEqual(client['geometry']['default'],geometry['description']['identifier'])
    self.assertEqual((resource/(client['textures']['default']+'.png')).read_bytes(),png())
   self.assertEqual((source/'model.java').read_text(encoding='utf-8'),MODEL)
   with self.assertRaises(ValueError):build(source,output,declaration())
 def test_invalid_inputs_never_publish_and_png_length_crc_are_checked(self):
  with tempfile.TemporaryDirectory() as tmp:
   source=Path(tmp)/'input';source.mkdir();(source/'model.java').write_text(MODEL,encoding='utf-8');(source/'texture.png').write_bytes(png())
   variants=[]
   for key,value in [('model_source','../model.java'),('texture','C:/texture.png'),('identifier','minecraft:pig'),('health',float('nan')),('collision',[0,1])]:
    config=declaration();config['entities'][0][key]=value;variants.append(config)
   config=declaration();config['entities'].append(copy.deepcopy(config['entities'][0]));variants.append(config)
   for index,config in enumerate(variants):
    output=Path(tmp)/str(index)
    with self.subTest(config=config),self.assertRaises(ValueError):build(source,output,config)
    self.assertFalse(output.exists())
   for invalid in (png()[:-1],png()+b'extra',png()[:40]+b'wrong'+png()[45:]):
    with self.assertRaises(ValueError):png_dimensions(invalid)
   (source/'texture.png').write_bytes(png(8,8))
   with self.assertRaises(ValueError):build(source,Path(tmp)/'mismatch',declaration())
   self.assertFalse((Path(tmp)/'mismatch').exists())

if __name__=='__main__':unittest.main()
