package com.singularity.c4nursery;

import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;
import org.json.JSONArray;
import org.json.JSONObject;
import java.security.MessageDigest;

public final class VocalActuator {
 private VocalActuator(){}

 public static final int SAMPLE_RATE=24000;

 public static final class Vocalization {
  public final short[] pcm;
  public final JSONObject params;
  public final String sha256;
  public final int durationMs;
  Vocalization(short[] pcm,JSONObject params,String sha256,int durationMs){
   this.pcm=pcm;this.params=params;this.sha256=sha256;this.durationMs=durationMs;
  }
 }

 private static double clamp(double v,double lo,double hi){return Math.max(lo,Math.min(hi,v));}
 private static int clampInt(int v,int lo,int hi){return Math.max(lo,Math.min(hi,v));}

 private static double formantWeight(double hz,double center,double bw){
  double d=(hz-center)/Math.max(1.0,bw);
  return Math.exp(-0.5*d*d);
 }

 private static long seedFrom(String s){
  long x=0x9E3779B97F4A7C15L;
  for(int i=0;i<s.length();i++){x^=s.charAt(i);x*=0xBF58476D1CE4E5B9L;x^=x>>>27;}
  return x==0?0xD1B54A32D192ED03L:x;
 }

 private static double noise(long[] state){
  long x=state[0];x^=x<<13;x^=x>>>7;x^=x<<17;state[0]=x;
  return ((x>>>11)*(1.0/(1L<<53)))*2.0-1.0;
 }

 public static Vocalization synthesize(String requestId,JSONObject command)throws Exception{
  JSONObject v=command.optJSONObject("voice");if(v==null)v=command;
  double f0=clamp(v.optDouble("f0Hz",220.0),70.0,700.0);
  double amplitude=clamp(v.optDouble("amplitude",0.18),0.0,0.35);
  int durationMs=clampInt(v.optInt("durationMs",520),60,2200);
  int harmonics=clampInt(v.optInt("harmonics",14),3,24);
  double breath=clamp(v.optDouble("breath",0.015),0.0,0.12);
  int attackMs=clampInt(v.optInt("attackMs",28),5,350);
  int releaseMs=clampInt(v.optInt("releaseMs",90),10,550);
  if(attackMs+releaseMs>durationMs-20){
   double k=Math.max(0.15,(durationMs-20.0)/(attackMs+releaseMs));
   attackMs=Math.max(5,(int)Math.round(attackMs*k));
   releaseMs=Math.max(10,(int)Math.round(releaseMs*k));
  }

  double[] formants={800.0,1150.0,2900.0};
  JSONArray fa=v.optJSONArray("formantsHz");
  if(fa!=null)for(int i=0;i<Math.min(3,fa.length());i++)formants[i]=clamp(fa.optDouble(i,formants[i]),180.0,5000.0);
  double[] bw={105.0,145.0,260.0};

  int count=Math.max(1,(int)Math.round(SAMPLE_RATE*durationMs/1000.0));
  short[] pcm=new short[count];
  long[] rng={seedFrom(requestId)};
  double attack=Math.max(1e-4,attackMs/1000.0),release=Math.max(1e-4,releaseMs/1000.0),dur=durationMs/1000.0;

  for(int n=0;n<count;n++){
   double t=n/(double)SAMPLE_RATE;
   double env=Math.min(1.0,t/attack);
   env=Math.min(env,Math.max(0.0,(dur-t)/release));
   env=clamp(env,0.0,1.0);
   double sum=0.0,norm=0.0;
   for(int k=1;k<=harmonics;k++){
    double hz=f0*k;if(hz>=SAMPLE_RATE*0.49)break;
    double spectral=0.08/Math.pow(k,0.72);
    spectral+=1.25*formantWeight(hz,formants[0],bw[0]);
    spectral+=0.92*formantWeight(hz,formants[1],bw[1]);
    spectral+=0.66*formantWeight(hz,formants[2],bw[2]);
    double w=spectral/Math.pow(k,0.36);
    sum+=Math.sin(2.0*Math.PI*hz*t)*w;norm+=Math.abs(w);
   }
   double voiced=norm>1e-9?sum/norm:0.0;
   double breathNoise=noise(rng)*breath;
   double sample=clamp(amplitude*env*(0.97*voiced+breathNoise),-0.96,0.96);
   pcm[n]=(short)Math.round(sample*32767.0);
  }

  MessageDigest md=MessageDigest.getInstance("SHA-256");
  for(short x:pcm){md.update((byte)(x&0xff));md.update((byte)((x>>>8)&0xff));}
  StringBuilder hs=new StringBuilder();for(byte x:md.digest())hs.append(String.format("%02x",x));

  JSONObject normalized=new JSONObject();
  normalized.put("schema","C4_PARAMETRIC_VOICE_V1");
  normalized.put("sampleRate",SAMPLE_RATE);
  normalized.put("f0Hz",f0);
  normalized.put("amplitude",amplitude);
  normalized.put("durationMs",durationMs);
  normalized.put("harmonics",harmonics);
  normalized.put("breath",breath);
  normalized.put("attackMs",attackMs);
  normalized.put("releaseMs",releaseMs);
  JSONArray ff=new JSONArray();for(double x:formants)ff.put(x);normalized.put("formantsHz",ff);
  normalized.put("semanticLabels",false);
  return new Vocalization(pcm,normalized,hs.toString(),durationMs);
 }

 public static boolean playBlocking(Vocalization v)throws Exception{
  int bytes=v.pcm.length*2;
  AudioTrack track=new AudioTrack.Builder()
   .setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
   .setAudioFormat(new AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT).setSampleRate(SAMPLE_RATE).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
   .setTransferMode(AudioTrack.MODE_STATIC)
   .setBufferSizeInBytes(Math.max(bytes,AudioTrack.getMinBufferSize(SAMPLE_RATE,AudioFormat.CHANNEL_OUT_MONO,AudioFormat.ENCODING_PCM_16BIT)))
   .build();
  try{
   if(track.getState()!=AudioTrack.STATE_INITIALIZED)return false;
   int wrote=track.write(v.pcm,0,v.pcm.length,AudioTrack.WRITE_BLOCKING);if(wrote!=v.pcm.length)return false;
   track.play();
   long deadline=System.currentTimeMillis()+v.durationMs+900L;
   while(System.currentTimeMillis()<deadline&&track.getPlaybackHeadPosition()<v.pcm.length){
    try{Thread.sleep(12);}catch(InterruptedException ie){Thread.currentThread().interrupt();return false;}
   }
   return track.getPlaybackHeadPosition()>=Math.max(1,v.pcm.length-64);
  }finally{
   try{track.stop();}catch(Exception ignored){}
   try{track.flush();}catch(Exception ignored){}
   try{track.release();}catch(Exception ignored){}
  }
 }
}
