package com.singularity.c4nursery;
import android.app.*;import android.os.*;import android.webkit.*;import android.graphics.Color;
public class MainActivity extends Activity{
 public void onCreate(Bundle b){super.onCreate(b); WebView w=new WebView(this); w.setBackgroundColor(Color.rgb(16,21,28)); w.getSettings().setJavaScriptEnabled(true); w.loadUrl("file:///android_asset/index.html"); setContentView(w);}
}