import com.singularity.c4nursery.PhysicsRoom;
public class PhysicsRoomTest {
 public static void main(String[] args){
  PhysicsRoom r=new PhysicsRoom();r.bodies[0][1]=2;r.bodies[1][1]=2;
  r.impulse(0,2,0,0);r.impulse(1,2,0,0);
  if(Math.abs(r.bodies[0][3]-2)>1e-10||Math.abs(r.bodies[1][3]-1)>1e-10)throw new AssertionError("mass response");
  for(int i=0;i<30;i++)r.advance(120);
  for(double[] b:r.bodies)if(!Double.isFinite(b[1])||b[1]<b[6]-.000001||Math.abs(b[0])>1.8||Math.abs(b[2])>1.8)throw new AssertionError("bounds");
  r.moveTeacher(1,-1);if(r.teacherX<=0||r.teacherZ>=1.3)throw new AssertionError("teacher motion");
  try{r.impulse(0,Double.NaN,0,0);throw new AssertionError("NaN accepted");}catch(IllegalArgumentException expected){}
  System.out.println("PHYSICS HOST PASS: mass, gravity, room bounds, teacher, invalid impulse");
 }
}
