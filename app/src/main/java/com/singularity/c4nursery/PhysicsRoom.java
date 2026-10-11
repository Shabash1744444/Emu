package com.singularity.c4nursery;

/** Host-only fixed-step rigid spheres. No cognitive labels or learning here.
 * Metres, kilograms, seconds. Semi-implicit Euler, gravity, floor/wall and
 * sphere contact impulses. It is a sandbox, not a model of external reality. */
public final class PhysicsRoom {
 public static final double DT=1.0/120.0;
 public final double[][] bodies={{-.6,1.2,0,0,0,0,.16,1},{.6,.2,0,0,0,0,.2,2}};
 public double teacherX=0,teacherZ=1.3;
 public long step=0;
 public synchronized void impulse(int id,double x,double y,double z){
  if(id<0||id>=bodies.length||!Double.isFinite(x)||!Double.isFinite(y)||!Double.isFinite(z)||Math.abs(x)+Math.abs(y)+Math.abs(z)>12)throw new IllegalArgumentException("INVALID_IMPULSE");
  double[] b=bodies[id];b[3]+=x/b[7];b[4]+=y/b[7];b[5]+=z/b[7];
 }
 public synchronized void advance(int n){
  if(n<0||n>120)throw new IllegalArgumentException("INVALID_STEPS");
  for(int k=0;k<n;k++){
   for(double[] b:bodies){
    b[4]-=9.81*DT;for(int j=0;j<3;j++)b[j]+=b[j+3]*DT;
    if(b[1]<b[6]){b[1]=b[6];if(b[4]<0)b[4]=-b[4]*.55;if(Math.abs(b[4])<.08)b[4]=0;double drag=Math.exp(-1.1*DT);b[3]*=drag;b[5]*=drag;}
    for(int j:new int[]{0,2}){double bound=1.8-b[6];if(Math.abs(b[j])>bound){b[j]=Math.copySign(bound,b[j]);b[j+3]=-Math.copySign(Math.abs(b[j+3])*.7,b[j]);}}
   }
   double[] a=bodies[0],b=bodies[1];double dx=b[0]-a[0],dy=b[1]-a[1],dz=b[2]-a[2];double d=Math.sqrt(dx*dx+dy*dy+dz*dz),radius=a[6]+b[6];
   if(d<radius&&d>1e-9){double[] normal={dx/d,dy/d,dz/d};double ia=1/a[7],ib=1/b[7],sum=ia+ib;
    for(int j=0;j<3;j++){a[j]-=normal[j]*(radius-d)*ia/sum;b[j]+=normal[j]*(radius-d)*ib/sum;}
    double v=0;for(int j=0;j<3;j++)v+=(b[j+3]-a[j+3])*normal[j];
    if(v<0){double impulse=-(1+.65)*v/sum;for(int j=0;j<3;j++){a[j+3]-=impulse*ia*normal[j];b[j+3]+=impulse*ib*normal[j];}}
   }
   step++;
  }
 }
 public synchronized void moveTeacher(double x,double z){
  if(!Double.isFinite(x)||!Double.isFinite(z)||Math.abs(x)>1||Math.abs(z)>1)throw new IllegalArgumentException("INVALID_TEACHER_MOTION");
  teacherX=Math.max(-1.6,Math.min(1.6,teacherX+x*.08));teacherZ=Math.max(-1.6,Math.min(1.6,teacherZ+z*.08));
 }
}
