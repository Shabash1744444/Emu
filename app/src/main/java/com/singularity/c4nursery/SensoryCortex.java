package com.singularity.c4nursery;

import android.graphics.Bitmap;
import android.graphics.Color;
import org.json.JSONArray;
import org.json.JSONObject;

public final class SensoryCortex {
 private SensoryCortex(){}

 private static double clamp01(double x){return Math.max(0.0,Math.min(1.0,x));}

 public static JSONObject audioFrame(short[] samples,int count,int sampleRate,long seq,long capturedAt)throws Exception{
  JSONObject o=new JSONObject();
  o.put("schema","C4_SENSORY_FEATURES_V1");
  o.put("modality","AUDIO");
  o.put("representation","PCM_PHYSICAL_FEATURES");
  o.put("semanticLabels",false);
  o.put("capturedAt",capturedAt);
  o.put("seq",seq);
  o.put("sampleRate",sampleRate);
  o.put("sampleCount",count);
  o.put("durationMs",count*1000.0/sampleRate);
  if(count<=0){o.put("empty",true);return o;}
  double sum2=0,abs=0,peak=0;int zc=0;short prev=samples[0];
  for(int i=0;i<count;i++){
   double v=samples[i]/32768.0;sum2+=v*v;abs+=Math.abs(v);peak=Math.max(peak,Math.abs(v));
   if(i>0&&((samples[i]>=0)!=(prev>=0)))zc++;
   prev=samples[i];
  }
  o.put("rms",Math.sqrt(sum2/count));
  o.put("meanAbs",abs/count);
  o.put("peak",peak);
  o.put("zeroCrossingRate",count>1?zc/(double)(count-1):0.0);
  int[] hz={125,250,500,1000,2000,3000,4000,6000};
  JSONArray probes=new JSONArray();double best=-1,bestHz=0,weighted=0,total=0;
  for(int f:hz){
   if(f>=sampleRate/2)continue;
   double p=goertzel(samples,count,sampleRate,f);
   double db=10.0*Math.log10(Math.max(1e-12,p));
   JSONObject q=new JSONObject();q.put("hz",f);q.put("relativePowerDb",db);probes.put(q);
   double lin=Math.max(0,p);total+=lin;weighted+=lin*f;if(lin>best){best=lin;bestHz=f;}
  }
  o.put("spectralProbes",probes);
  o.put("dominantProbeHz",bestHz);
  o.put("probeCentroidHz",total>0?weighted/total:0);
  return o;
 }

 private static double goertzel(short[] x,int n,int sampleRate,double freq){
  double w=2.0*Math.PI*freq/sampleRate, coeff=2.0*Math.cos(w),s0,s1=0,s2=0;
  for(int i=0;i<n;i++){double v=x[i]/32768.0;s0=v+coeff*s1-s2;s2=s1;s1=s0;}
  double power=s1*s1+s2*s2-coeff*s1*s2;
  return Math.max(0,power/(Math.max(1,n)*(double)Math.max(1,n)));
 }

 public static JSONObject visualFrame(Bitmap input,String source,long seq,long capturedAt)throws Exception{
  final int gw=12,gh=8;
  Bitmap b=Bitmap.createScaledBitmap(input,gw,gh,true);
  JSONArray cells=new JSONArray();double sum=0,sum2=0,edge=0;int edgeN=0;
  double[][] lum=new double[gh][gw];
  for(int y=0;y<gh;y++)for(int x=0;x<gw;x++){
   int c=b.getPixel(x,y);int r=Color.red(c),g=Color.green(c),bl=Color.blue(c);
   double l=(0.2126*r+0.7152*g+0.0722*bl)/255.0;lum[y][x]=l;sum+=l;sum2+=l*l;
   JSONArray cell=new JSONArray();cell.put(r);cell.put(g);cell.put(bl);cell.put(Math.round(l*1000.0)/1000.0);cells.put(cell);
  }
  for(int y=0;y<gh;y++)for(int x=0;x<gw;x++){
   if(x+1<gw){edge+=Math.abs(lum[y][x]-lum[y][x+1]);edgeN++;}
   if(y+1<gh){edge+=Math.abs(lum[y][x]-lum[y+1][x]);edgeN++;}
  }
  double mean=sum/(gw*gh),variance=Math.max(0,sum2/(gw*gh)-mean*mean);
  JSONObject o=new JSONObject();
  o.put("schema","C4_SENSORY_FEATURES_V1");
  o.put("modality","VISION");
  o.put("representation","RETINAL_LATTICE");
  o.put("semanticLabels",false);
  o.put("source",source);
  o.put("capturedAt",capturedAt);
  o.put("seq",seq);
  o.put("inputWidth",input.getWidth());o.put("inputHeight",input.getHeight());
  o.put("gridWidth",gw);o.put("gridHeight",gh);
  o.put("meanLuma",clamp01(mean));o.put("lumaVariance",variance);
  o.put("edgeChangeMean",edgeN>0?edge/edgeN:0);
  o.put("cellsRGBL",cells);
  if(b!=input)b.recycle();
  return o;
 }
}
