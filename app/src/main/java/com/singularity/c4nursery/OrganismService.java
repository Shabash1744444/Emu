package com.singularity.c4nursery;

import android.app.*;
import android.content.*;
import android.os.*;
import org.json.*;
import java.util.concurrent.*;

public class OrganismService extends Service {
 public static final String ACTION_START="c4.organism.START";
 public static final String ACTION_STOP="c4.organism.STOP";
 public static final String ACTION_EVENT="c4.organism.EVENT";
 private static final String CH="c4_organism";
 private ScheduledExecutorService exec;
 private SharedPreferences prefs;
 private long ticks=0;

 @Override public void onCreate(){
  super.onCreate();
  prefs=getSharedPreferences("c4_nursery",MODE_PRIVATE);
  NotificationManager nm=getSystemService(NotificationManager.class);
  if(Build.VERSION.SDK_INT>=26)nm.createNotificationChannel(new NotificationChannel(CH,"C4 organism",NotificationManager.IMPORTANCE_LOW));
 }
 private Notification note(){
  return new Notification.Builder(this,Build.VERSION.SDK_INT>=26?CH:"")
    .setContentTitle("C4 живёт")
    .setContentText("Локальный организм продолжает автономные циклы")
    .setSmallIcon(android.R.drawable.ic_media_play)
    .setOngoing(true)
    .build();
 }
 @Override public int onStartCommand(Intent i,int flags,int id){
  if(i==null)return START_NOT_STICKY;
  if(ACTION_STOP.equals(i.getAction())){shutdown(false);return START_NOT_STICKY;}
  if(ACTION_START.equals(i.getAction())){
   if(!prefs.getBoolean("runtime_running",false)){stopSelf();return START_NOT_STICKY;}
   startForeground(91,note());
   prefs.edit().putLong("organism_service_heartbeat",System.currentTimeMillis()).apply();
   if(exec==null||exec.isShutdown()){
    exec=Executors.newSingleThreadScheduledExecutor();
    exec.scheduleAtFixedRate(this::tick,300,1500,TimeUnit.MILLISECONDS);
   }
  }
  return START_NOT_STICKY;
 }
 private void tick(){
  if(!prefs.getBoolean("runtime_running",false)){shutdown(false);return;}
  prefs.edit().putLong("organism_service_heartbeat",System.currentTimeMillis()).apply();
  try{
   JSONObject py=new JSONObject(C4PythonGate.call(this,"command","TICK","{\"n\":1}"));
   if(!py.optBoolean("accepted",false))throw new IllegalStateException(py.optString("error","TICK_REJECTED"));
   JSONArray ev=py.optJSONArray("events");
   boolean emitted=false;
   if(ev!=null)for(int n=0;n<ev.length();n++){
    JSONObject e=ev.optJSONObject(n);if(e==null)continue;emitted=true;
    String type=e.optString("type",e.optString("kind","STATUS"));
    broadcast(type,e);
   }
   ticks++;
   if(emitted||ticks%20==0){
    try{
     JSONObject cp=new JSONObject(C4PythonGate.call(this,"checkpoint"));
     if(cp.optBoolean("saved",false))broadcast("CHECKPOINT_COMMITTED",cp);
    }catch(Exception ignored){}
   }
  }catch(Exception e){
   prefs.edit().putBoolean("runtime_running",false).putString("runtime_last_error","SERVICE_TICK:"+e.getClass().getSimpleName()+":"+String.valueOf(e.getMessage())).commit();
   try{broadcast("ERROR",new JSONObject().put("error","BRAIN_TICK_FAILED").put("detail",String.valueOf(e.getMessage())));}catch(Exception ignored){}
   shutdown(false);
  }
 }
 private void broadcast(String type,JSONObject payload){
  Intent e=new Intent(ACTION_EVENT).setPackage(getPackageName());
  e.putExtra("type",type);e.putExtra("payload",payload.toString());sendBroadcast(e);
 }
 private void shutdown(boolean checkpoint){
  if(checkpoint&&prefs.getBoolean("runtime_running",false))try{C4PythonGate.call(this,"checkpoint");}catch(Exception ignored){}
  if(exec!=null){exec.shutdownNow();exec=null;}
  stopForeground(true);stopSelf();
 }
 @Override public void onTaskRemoved(Intent rootIntent){try{C4PythonGate.call(this,"checkpoint");}catch(Exception ignored){}super.onTaskRemoved(rootIntent);}
 @Override public void onDestroy(){prefs.edit().putLong("organism_service_heartbeat",0).apply();if(exec!=null){exec.shutdownNow();exec=null;}super.onDestroy();}
 @Override public IBinder onBind(Intent i){return null;}
}
