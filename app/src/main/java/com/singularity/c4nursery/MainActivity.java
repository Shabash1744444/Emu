package com.singularity.c4nursery;

import android.app.*;import android.os.*;import android.webkit.*;import android.graphics.Color;
import android.content.*;import android.content.pm.PackageManager;import android.content.res.Configuration;
import android.net.Uri;import android.provider.MediaStore;import android.media.MediaRecorder;import android.media.projection.MediaProjection;import android.media.projection.MediaProjectionManager;import android.media.Image;import android.media.ImageReader;import android.hardware.display.DisplayManager;import android.hardware.display.VirtualDisplay;import android.graphics.Bitmap;import android.util.DisplayMetrics;
import org.json.JSONObject;import java.io.*;import java.util.*;

public class MainActivity extends Activity {
 private WebView web; private SharedPreferences prefs; private MediaRecorder recorder;
 private File audioFile; private Uri cameraUri;
 private static final int PICK=4101,CAMERA=4102,MIC=4103,SCREEN=4104; private MediaProjectionManager projectionManager;

 @Override public void onCreate(Bundle b){
  super.onCreate(b); prefs=getSharedPreferences("c4_nursery",MODE_PRIVATE);
  web=new WebView(this); web.setBackgroundColor(Color.rgb(13,18,25));
  WebSettings s=web.getSettings(); s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);s.setAllowFileAccess(false);s.setAllowContentAccess(false);
  web.addJavascriptInterface(new NurseryBridge(),"NurseryNative");web.setWebViewClient(new WebViewClient());
  projectionManager=(MediaProjectionManager)getSystemService(MEDIA_PROJECTION_SERVICE);web.loadUrl("file:///android_asset/index.html");setContentView(web);
 }
 private void emit(String type,JSONObject payload){try{final String js="window.C4HostEvent&&window.C4HostEvent("+JSONObject.quote(type)+","+payload.toString()+")";runOnUiThread(()->web.evaluateJavascript(js,null));}catch(Exception ignored){}}
 private JSONObject attachment(String kind,String name,String mime,long size,String uri)throws Exception{JSONObject o=new JSONObject();o.put("kind",kind);o.put("name",name);o.put("mime",mime);o.put("size",size);o.put("uri",uri);o.put("capturedAt",System.currentTimeMillis());return o;}

 public final class NurseryBridge {
  @JavascriptInterface public String loadState(){return prefs.getString("state","{}");}
  @JavascriptInterface public boolean commitState(String json){try{new JSONObject(json);return prefs.edit().putString("state",json).commit();}catch(Exception e){return false;}}
  @JavascriptInterface public long now(){return System.currentTimeMillis();}
  @JavascriptInterface public String hostInfo(){try{JSONObject o=new JSONObject();o.put("sdk",Build.VERSION.SDK_INT);o.put("device",Build.MANUFACTURER+" "+Build.MODEL);o.put("orientation",getResources().getConfiguration().orientation==Configuration.ORIENTATION_LANDSCAPE?"landscape":"portrait");return o.toString();}catch(Exception e){return "{}";}}
  @JavascriptInterface public String capabilities(){try{JSONObject o=new JSONObject();o.put("files",true);o.put("camera",getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY));o.put("microphone",getPackageManager().hasSystemFeature(PackageManager.FEATURE_MICROPHONE));o.put("screenCapture",Build.VERSION.SDK_INT>=21);o.put("c4Transport",false);return o.toString();}catch(Exception e){return "{}";}}
  @JavascriptInterface public void pickFile(){runOnUiThread(()->{Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("*/*");startActivityForResult(i,PICK);});}
  @JavascriptInterface public void capturePhoto(){runOnUiThread(()->{try{ContentValues v=new ContentValues();v.put(MediaStore.Images.Media.DISPLAY_NAME,"c4_"+System.currentTimeMillis()+".jpg");v.put(MediaStore.Images.Media.MIME_TYPE,"image/jpeg");cameraUri=getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI,v);Intent i=new Intent(MediaStore.ACTION_IMAGE_CAPTURE);i.putExtra(MediaStore.EXTRA_OUTPUT,cameraUri);i.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION);startActivityForResult(i,CAMERA);}catch(Exception e){JSONObject p=new JSONObject();try{p.put("error",e.getClass().getSimpleName());}catch(Exception ignored){}emit("MEDIA_ERROR",p);}});}
  @JavascriptInterface public void startAudio(){runOnUiThread(()->startRecording());}
  @JavascriptInterface public void stopAudio(){runOnUiThread(()->stopRecording());}
  @JavascriptInterface public void captureScreen(){runOnUiThread(()->startActivityForResult(projectionManager.createScreenCaptureIntent(),SCREEN));}
 }
 private void startRecording(){try{
  if(checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{android.Manifest.permission.RECORD_AUDIO},MIC);return;}
  audioFile=new File(getFilesDir(),"audio_"+System.currentTimeMillis()+".m4a");recorder=new MediaRecorder();
  recorder.setAudioSource(MediaRecorder.AudioSource.MIC);recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);recorder.setOutputFile(audioFile.getAbsolutePath());recorder.prepare();recorder.start();
  JSONObject p=new JSONObject();p.put("startedAt",System.currentTimeMillis());emit("AUDIO_STARTED",p);
 }catch(Exception e){recorder=null;JSONObject p=new JSONObject();try{p.put("error",e.getClass().getSimpleName());}catch(Exception ignored){}emit("MEDIA_ERROR",p);}}
 private void stopRecording(){if(recorder==null)return;try{recorder.stop();recorder.release();recorder=null;emit("ATTACHMENT_READY",attachment("audio",audioFile.getName(),"audio/mp4",audioFile.length(),Uri.fromFile(audioFile).toString()));}catch(Exception e){try{recorder.release();}catch(Exception ignored){}recorder=null;}}
 @Override public void onRequestPermissionsResult(int r,String[] p,int[] g){super.onRequestPermissionsResult(r,p,g);if(r==MIC&&g.length>0&&g[0]==PackageManager.PERMISSION_GRANTED)startRecording();}
 @Override protected void onActivityResult(int r,int c,Intent d){super.onActivityResult(r,c,d);try{
  if(r==PICK&&c==RESULT_OK&&d!=null&&d.getData()!=null){Uri u=d.getData();try{getContentResolver().takePersistableUriPermission(u,d.getFlags()&(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION));}catch(SecurityException ignored){}String mime=getContentResolver().getType(u);emit("ATTACHMENT_READY",attachment("file","Документ",mime==null?"application/octet-stream":mime,-1,u.toString()));}
  if(r==CAMERA){if(c==RESULT_OK&&cameraUri!=null)emit("ATTACHMENT_READY",attachment("image","Фото","image/jpeg",-1,cameraUri.toString()));else if(cameraUri!=null)getContentResolver().delete(cameraUri,null,null);cameraUri=null;}
  if(r==SCREEN&&c==RESULT_OK&&d!=null)captureOneScreen(c,d);
 }catch(Exception e){JSONObject p=new JSONObject();try{p.put("error",e.getClass().getSimpleName());}catch(Exception ignored){}emit("MEDIA_ERROR",p);}}
 private void captureOneScreen(int resultCode,Intent data){try{
  final MediaProjection mp=projectionManager.getMediaProjection(resultCode,data);DisplayMetrics dm=new DisplayMetrics();getWindowManager().getDefaultDisplay().getRealMetrics(dm);
  final int w=dm.widthPixels,h=dm.heightPixels,dpi=dm.densityDpi;final ImageReader ir=ImageReader.newInstance(w,h,android.graphics.PixelFormat.RGBA_8888,2);
  final VirtualDisplay vd=mp.createVirtualDisplay("C4ScreenShot",w,h,dpi,DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,ir.getSurface(),null,null);
  ir.setOnImageAvailableListener(reader->{Image image=null;try{image=reader.acquireLatestImage();if(image==null)return;Image.Plane p=image.getPlanes()[0];java.nio.ByteBuffer buf=p.getBuffer();int pixelStride=p.getPixelStride(),rowStride=p.getRowStride(),rowPadding=rowStride-pixelStride*w;Bitmap padded=Bitmap.createBitmap(w+rowPadding/pixelStride,h,Bitmap.Config.ARGB_8888);padded.copyPixelsFromBuffer(buf);Bitmap bmp=Bitmap.createBitmap(padded,0,0,w,h);padded.recycle();File f=new File(getFilesDir(),"screen_"+System.currentTimeMillis()+".png");FileOutputStream os=new FileOutputStream(f);bmp.compress(Bitmap.CompressFormat.PNG,92,os);os.close();bmp.recycle();emit("ATTACHMENT_READY",attachment("screen",f.getName(),"image/png",f.length(),Uri.fromFile(f).toString()));}catch(Exception e){JSONObject x=new JSONObject();try{x.put("error",e.getClass().getSimpleName());}catch(Exception ignored){}emit("MEDIA_ERROR",x);}finally{if(image!=null)image.close();vd.release();ir.close();mp.stop();}},new Handler(Looper.getMainLooper()));
 }catch(Exception e){JSONObject x=new JSONObject();try{x.put("error",e.getClass().getSimpleName());}catch(Exception ignored){}emit("MEDIA_ERROR",x);}}
 @Override protected void onPause(){super.onPause();if(recorder!=null)stopRecording();}
 @Override public void onBackPressed(){if(web!=null&&web.canGoBack())web.goBack();else super.onBackPressed();}
}