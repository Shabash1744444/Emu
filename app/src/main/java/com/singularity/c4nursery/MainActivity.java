package com.singularity.c4nursery;

import android.app.*;
import android.os.*;
import android.webkit.*;
import android.graphics.Color;
import android.content.*;
import android.content.res.Configuration;
import org.json.JSONObject;

public class MainActivity extends Activity {
  private WebView web;
  private SharedPreferences prefs;

  @Override public void onCreate(Bundle b) {
    super.onCreate(b);
    prefs=getSharedPreferences("c4_nursery",MODE_PRIVATE);
    web=new WebView(this);
    web.setBackgroundColor(Color.rgb(13,18,25));
    WebSettings s=web.getSettings();
    s.setJavaScriptEnabled(true);
    s.setDomStorageEnabled(true);
    s.setAllowFileAccess(false);
    s.setAllowContentAccess(false);
    web.addJavascriptInterface(new NurseryBridge(),"NurseryNative");
    web.setWebViewClient(new WebViewClient());
    web.loadUrl("file:///android_asset/index.html");
    setContentView(web);
  }

  public final class NurseryBridge {
    @JavascriptInterface public String loadState() {
      return prefs.getString("state","{}");
    }
    @JavascriptInterface public boolean commitState(String json) {
      try {
        new JSONObject(json);
        return prefs.edit().putString("state",json).commit();
      } catch(Exception e) { return false; }
    }
    @JavascriptInterface public long now() { return System.currentTimeMillis(); }
    @JavascriptInterface public String hostInfo() {
      try {
        JSONObject o=new JSONObject();
        o.put("sdk",Build.VERSION.SDK_INT);
        o.put("device",Build.MANUFACTURER+" "+Build.MODEL);
        o.put("orientation",getResources().getConfiguration().orientation==Configuration.ORIENTATION_LANDSCAPE?"landscape":"portrait");
        return o.toString();
      } catch(Exception e){ return "{}"; }
    }
  }

  @Override public void onBackPressed() {
    if(web!=null && web.canGoBack()) web.goBack(); else super.onBackPressed();
  }
}