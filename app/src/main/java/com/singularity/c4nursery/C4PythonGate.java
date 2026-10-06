package com.singularity.c4nursery;

import android.content.Context;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

public final class C4PythonGate {
 private C4PythonGate(){}
 public static synchronized String call(Context context,String fn,Object... args)throws Exception{
  if(!Python.isStarted())Python.start(new AndroidPlatform(context.getApplicationContext()));
  return Python.getInstance().getModule("c4_mobile_bridge").callAttr(fn,args).toString();
 }
}
