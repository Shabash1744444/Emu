package com.singularity.c4nursery;

import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.ImageFormat;
import android.hardware.camera2.*;
import android.media.Image;
import android.media.ImageReader;
import android.net.Uri;
import android.os.*;
import java.io.*;
import java.nio.ByteBuffer;
import java.util.*;

public class CameraStreamService extends Service {
 public static final String ACTION_START="c4.camera.START";
 public static final String ACTION_STOP="c4.camera.STOP";
 public static final String ACTION_FRAME="c4.camera.FRAME";
 private static final String CH="c4_camera";
 private HandlerThread thread; private Handler handler; private CameraDevice camera; private CameraCaptureSession session; private ImageReader reader;
 private String sessionId; private long lastFrame=0; private int intervalMs=800;

 @Override public void onCreate(){
  super.onCreate();
  thread=new HandlerThread("c4-camera");thread.start();handler=new Handler(thread.getLooper());
  NotificationManager nm=getSystemService(NotificationManager.class);
  if(Build.VERSION.SDK_INT>=26)nm.createNotificationChannel(new NotificationChannel(CH,"C4 live vision",NotificationManager.IMPORTANCE_LOW));
 }
 private Notification note(){
  return new Notification.Builder(this,Build.VERSION.SDK_INT>=26?CH:"")
   .setContentTitle("C4 смотрит")
   .setContentText("Камера используется как зрительный сенсор")
   .setSmallIcon(android.R.drawable.ic_menu_camera)
   .setOngoing(true).build();
 }
 @Override public int onStartCommand(Intent i,int flags,int id){
  if(i==null)return START_NOT_STICKY;
  if(ACTION_STOP.equals(i.getAction())){stopCamera("user");return START_NOT_STICKY;}
  if(ACTION_START.equals(i.getAction())){
   if(checkSelfPermission(android.Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED){stopSelf();return START_NOT_STICKY;}
   startForeground(92,note());openBackCamera();
  }
  return START_NOT_STICKY;
 }
 private void openBackCamera(){
  try{
   CameraManager cm=(CameraManager)getSystemService(CAMERA_SERVICE);
   String chosen=null;
   for(String id:cm.getCameraIdList()){
    CameraCharacteristics cc=cm.getCameraCharacteristics(id);
    Integer facing=cc.get(CameraCharacteristics.LENS_FACING);
    if(facing!=null&&facing==CameraCharacteristics.LENS_FACING_BACK){chosen=id;break;}
    if(chosen==null)chosen=id;
   }
   if(chosen==null)throw new IllegalStateException("NO_CAMERA");
   sessionId=UUID.randomUUID().toString();
   reader=ImageReader.newInstance(640,480,ImageFormat.JPEG,2);
   reader.setOnImageAvailableListener(this::onImage,handler);
   broadcast("START",null,0);
   cm.openCamera(chosen,new CameraDevice.StateCallback(){
    @Override public void onOpened(CameraDevice c){camera=c;createSession();}
    @Override public void onDisconnected(CameraDevice c){c.close();camera=null;stopCamera("disconnected");}
    @Override public void onError(CameraDevice c,int error){c.close();camera=null;stopCamera("camera_error_"+error);}
   },handler);
  }catch(Exception e){broadcastError("CAMERA_OPEN:"+e.getClass().getSimpleName()+":"+String.valueOf(e.getMessage()));stopCamera("open_error");}
 }
 private void createSession(){
  try{
   final CameraDevice c=camera;if(c==null||reader==null)return;
   c.createCaptureSession(Collections.singletonList(reader.getSurface()),new CameraCaptureSession.StateCallback(){
    @Override public void onConfigured(CameraCaptureSession s){
     session=s;
     try{
      CaptureRequest.Builder b=c.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
      b.addTarget(reader.getSurface());
      b.set(CaptureRequest.CONTROL_AF_MODE,CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE);
      b.set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_ON);
      s.setRepeatingRequest(b.build(),null,handler);
     }catch(Exception e){broadcastError("CAMERA_REPEAT:"+e.getClass().getSimpleName());stopCamera("repeat_error");}
    }
    @Override public void onConfigureFailed(CameraCaptureSession s){broadcastError("CAMERA_CONFIG_FAILED");stopCamera("config_error");}
   },handler);
  }catch(Exception e){broadcastError("CAMERA_SESSION:"+e.getClass().getSimpleName());stopCamera("session_error");}
 }
 private void onImage(ImageReader r){
  Image im=null;
  try{
   im=r.acquireLatestImage();if(im==null)return;
   long now=System.currentTimeMillis();if(now-lastFrame<intervalMs)return;lastFrame=now;
   ByteBuffer bb=im.getPlanes()[0].getBuffer();byte[] data=new byte[bb.remaining()];bb.get(data);
   File dir=new File(getCacheDir(),"camerastream");if(!dir.exists())dir.mkdirs();
   File[] old=dir.listFiles();if(old!=null)for(File f:old)if(now-f.lastModified()>20000)f.delete();
   File f=new File(dir,"frame_"+now+".jpg");try(FileOutputStream out=new FileOutputStream(f)){out.write(data);out.getFD().sync();}
   broadcast("FRAME",Uri.fromFile(f).toString(),f.length());
  }catch(Exception e){broadcastError("CAMERA_FRAME:"+e.getClass().getSimpleName());}
  finally{if(im!=null)im.close();}
 }
 private void broadcast(String phase,String uri,long size){
  Intent e=new Intent(ACTION_FRAME).setPackage(getPackageName());
  e.putExtra("phase",phase);e.putExtra("sessionId",sessionId);e.putExtra("capturedAt",System.currentTimeMillis());
  if(uri!=null)e.putExtra("uri",uri);e.putExtra("size",size);sendBroadcast(e);
 }
 private void broadcastError(String error){
  Intent e=new Intent(ACTION_FRAME).setPackage(getPackageName());
  e.putExtra("phase","ERROR");e.putExtra("sessionId",sessionId);e.putExtra("error",error);sendBroadcast(e);
 }
 private void stopCamera(String why){
  try{if(session!=null){session.stopRepeating();session.abortCaptures();}}catch(Exception ignored){}
  try{if(session!=null)session.close();}catch(Exception ignored){}session=null;
  try{if(camera!=null)camera.close();}catch(Exception ignored){}camera=null;
  try{if(reader!=null)reader.close();}catch(Exception ignored){}reader=null;
  if(sessionId!=null)broadcast("STOP",null,0);
  stopForeground(true);stopSelf();
 }
 @Override public void onDestroy(){stopCamera("destroy");if(thread!=null){thread.quitSafely();thread=null;}super.onDestroy();}
 @Override public IBinder onBind(Intent i){return null;}
}
