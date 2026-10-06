package com.singularity.c4nursery;

import android.app.*;
import android.content.*;
import android.hardware.*;
import android.os.*;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;

public class BodySensorService extends Service implements SensorEventListener {
 public static final String ACTION_START="c4.body.START";
 public static final String ACTION_STOP="c4.body.STOP";
 public static final String ACTION_FRAME="c4.body.FRAME";
 private static final String CH="c4_body";
 private SensorManager sm;
 private ScheduledExecutorService exec;
 private String sessionId;
 private final Object lock=new Object();
 private float[] accel,gyro,rotation;
 private Float light,proximity;
 private long lastSensorAt=0;
 private int emitted=0;

 @Override public void onCreate(){
  super.onCreate();
  sm=(SensorManager)getSystemService(SENSOR_SERVICE);
  NotificationManager nm=getSystemService(NotificationManager.class);
  if(Build.VERSION.SDK_INT>=26)nm.createNotificationChannel(new NotificationChannel(CH,"C4 body senses",NotificationManager.IMPORTANCE_LOW));
 }
 private Notification note(){
  return new Notification.Builder(this,Build.VERSION.SDK_INT>=26?CH:"")
   .setContentTitle("C4 чувствует тело")
   .setContentText("Движение, вращение, свет и близость передаются как физические сенсоры")
   .setSmallIcon(android.R.drawable.ic_menu_compass)
   .setOngoing(true).build();
 }
 @Override public int onStartCommand(Intent i,int flags,int id){
  if(i==null)return START_NOT_STICKY;
  if(ACTION_STOP.equals(i.getAction())){shutdown("user");return START_NOT_STICKY;}
  if(ACTION_START.equals(i.getAction())){
   startForeground(94,note());
   if(sessionId==null)sessionId=UUID.randomUUID().toString();
   register();
   broadcast("START",null);
   if(exec==null||exec.isShutdown()){
    exec=Executors.newSingleThreadScheduledExecutor();
    exec.scheduleAtFixedRate(this::emitFrame,250,250,TimeUnit.MILLISECONDS);
   }
  }
  return START_NOT_STICKY;
 }
 private void register(){
  registerType(Sensor.TYPE_ACCELEROMETER);
  registerType(Sensor.TYPE_GYROSCOPE);
  registerType(Sensor.TYPE_LIGHT);
  registerType(Sensor.TYPE_PROXIMITY);
  registerType(Sensor.TYPE_ROTATION_VECTOR);
 }
 private void registerType(int type){
  try{Sensor s=sm.getDefaultSensor(type);if(s!=null)sm.registerListener(this,s,SensorManager.SENSOR_DELAY_GAME);}catch(Exception ignored){}
 }
 @Override public void onSensorChanged(SensorEvent e){
  synchronized(lock){
   float[] v=e.values==null?new float[0]:Arrays.copyOf(e.values,e.values.length);
   switch(e.sensor.getType()){
    case Sensor.TYPE_ACCELEROMETER: accel=v;break;
    case Sensor.TYPE_GYROSCOPE: gyro=v;break;
    case Sensor.TYPE_LIGHT: light=v.length>0?v[0]:null;break;
    case Sensor.TYPE_PROXIMITY: proximity=v.length>0?v[0]:null;break;
    case Sensor.TYPE_ROTATION_VECTOR: rotation=v;break;
   }
   lastSensorAt=System.currentTimeMillis();
  }
 }
 @Override public void onAccuracyChanged(Sensor s,int accuracy){}

 private JSONArray arr(float[] v)throws JSONException{
  JSONArray a=new JSONArray();if(v!=null)for(float x:v)a.put((double)x);return a;
 }
 private void emitFrame(){
  try{
   JSONObject f=new JSONObject();
   synchronized(lock){
    if(lastSensorAt==0)return;
    f.put("schema","C4_BODY_SENSOR_V1");
    f.put("modality","BODY");
    f.put("representation","DEVICE_PHYSICAL_SENSORS");
    f.put("semanticLabels",false);
    f.put("capturedAt",System.currentTimeMillis());
    f.put("sensorAgeMs",System.currentTimeMillis()-lastSensorAt);
    if(accel!=null)f.put("accelerationMps2",arr(accel));
    if(gyro!=null)f.put("angularVelocityRadS",arr(gyro));
    if(rotation!=null)f.put("rotationVector",arr(rotation));
    if(light!=null)f.put("ambientLightLux",(double)light);
    if(proximity!=null)f.put("proximity",(double)proximity);
   }
   f.put("seq",++emitted);
   broadcast("FRAME",f);
  }catch(Exception ignored){}
 }
 private void broadcast(String phase,JSONObject frame){
  Intent e=new Intent(ACTION_FRAME).setPackage(getPackageName());
  e.putExtra("phase",phase);e.putExtra("sessionId",sessionId);e.putExtra("capturedAt",System.currentTimeMillis());
  if(frame!=null)e.putExtra("frame",frame.toString());
  sendBroadcast(e);
 }
 private void shutdown(String why){
  try{if(sm!=null)sm.unregisterListener(this);}catch(Exception ignored){}
  if(exec!=null){exec.shutdownNow();exec=null;}
  if(sessionId!=null)broadcast("STOP",null);
  sessionId=null;
  stopForeground(true);stopSelf();
 }
 @Override public void onDestroy(){try{if(sm!=null)sm.unregisterListener(this);}catch(Exception ignored){}if(exec!=null){exec.shutdownNow();exec=null;}super.onDestroy();}
 @Override public IBinder onBind(Intent i){return null;}
}
