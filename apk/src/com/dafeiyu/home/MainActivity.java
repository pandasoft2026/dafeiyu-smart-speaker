package com.dafeiyu.home;

import android.app.Activity;
import android.content.Context;
import android.database.ContentObserver;
import android.graphics.Color;
import android.media.AudioManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
    private WebView web;
    private AudioManager am;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        am = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
        // 打开 WebView 远程调试：出问题能直接连上去看真实状态
        WebView.setWebContentsDebuggingEnabled(true);
        watchVolume();

        // 不再常亮：10 分钟没人碰就按系统息屏超时熄屏（语音服务另靠
        // /sys/power/wake_lock 保持麦克风不中断，唤醒了会自己把屏幕点亮）
        getWindow().setStatusBarColor(Color.TRANSPARENT);

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#E9F5FF"));

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setAllowFileAccessFromFileURLs(true);
        s.setAllowUniversalAccessFromFileURLs(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView v, String u) {
                if (getIntent() != null && getIntent().getBooleanExtra("test", false)) {
                    v.evaluateJavascript("setTimeout(function(){ micTurn(); }, 2000);", null);
                }
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(android.webkit.ConsoleMessage m) {
                android.util.Log.i("DFY", m.message() + " @" + m.lineNumber());
                return true;
            }
        });

        setContentView(web);
        hideSystemUi();
        String url = getIntent() != null ? getIntent().getStringExtra("url") : null;
        if (url == null || url.isEmpty()) url = "file:///android_asset/index.html";
        web.loadUrl(url);
    }

    private void hideSystemUi() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideSystemUi();
    }

    @Override
    public void onBackPressed() {
        // 作为桌面时不响应返回，避免退出
    }

    /** 调试用：adb 再发一次带 url 的 Intent 即可在页面里执行（支持 javascript:） */
    @Override
    protected void onNewIntent(android.content.Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        String url = intent != null ? intent.getStringExtra("url") : null;
        if (url != null && !url.isEmpty() && web != null) {
            web.loadUrl(url);
        }
    }

    /**
     * 盯着音量设置项，一变就把当前音量推给界面自己画条。
     * 为什么不靠 dispatchKeyEvent：本机固件没有 SystemUI，音量键在
     * PhoneWindowManager 那一层就被吃掉了，实测按键确实把系统音量从 5 调到 6，
     * 但 Activity 的 dispatchKeyEvent 一次都没进来，界面自然没反应。
     * 改用 ContentObserver 后，不管音量是按键、adb 注入还是别的应用改的，都能弹条。
     */
    private void watchVolume() {
        try {
            getContentResolver().registerContentObserver(
                    Settings.System.CONTENT_URI, true,
                    new ContentObserver(new Handler(Looper.getMainLooper())) {
                        @Override
                        public void onChange(boolean self) {
                            pushVolume();
                        }
                    });
        } catch (Exception e) {
            android.util.Log.i("DFY", "watchVolume 失败: " + e);
        }
    }

    /**
     * 本机固件没有 SystemUI，按音量键既不弹条、音量也不一定能变（实测：按键被应用消费后
     * 系统就不再兜底处理）。所以这里自己调音量、自己画条。
     */
    /** 上一次上报活动的时间：手一直点也别每秒都发请求 */
    private long lastPoke = 0;

    /**
     * 告诉语音服务「有人在操作」，用来重置 10 分钟息屏倒计时。
     * 熄屏由服务端做（它有 root，能注入 POWER 键），这里只负责报点。
     */
    private void poke() {
        long now = System.currentTimeMillis();
        if (now - lastPoke < 10000) return;
        lastPoke = now;
        new Thread(new Runnable() {
            public void run() {
                java.net.HttpURLConnection c = null;
                try {
                    c = (java.net.HttpURLConnection)
                            new java.net.URL("http://127.0.0.1:8899/api/activity").openConnection();
                    c.setRequestMethod("POST");
                    c.setDoOutput(true);
                    c.setConnectTimeout(1500);
                    c.setReadTimeout(1500);
                    c.getOutputStream().write("{}".getBytes());
                    c.getResponseCode();
                } catch (Exception e) {
                    // 服务没起来也不影响界面
                } finally {
                    if (c != null) c.disconnect();
                }
            }
        }).start();
    }

    @Override
    public boolean dispatchTouchEvent(MotionEvent ev) {
        if (ev.getAction() == MotionEvent.ACTION_DOWN) poke();
        return super.dispatchTouchEvent(ev);
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent e) {
        int k = e.getKeyCode();
        if (e.getAction() == KeyEvent.ACTION_DOWN) {
            poke();
            android.util.Log.i("DFY", "key " + k + " (" + KeyEvent.keyCodeToString(k) + ")");
        }
        if (k == KeyEvent.KEYCODE_VOLUME_UP || k == KeyEvent.KEYCODE_VOLUME_DOWN) {
            if (e.getAction() == KeyEvent.ACTION_DOWN) {
                adjustVolume(k == KeyEvent.KEYCODE_VOLUME_UP);
            }
            return true;
        }
        if (k == KeyEvent.KEYCODE_VOLUME_MUTE) {
            if (e.getAction() == KeyEvent.ACTION_DOWN) {
                toggleMute();
            }
            return true;
        }
        return super.dispatchKeyEvent(e);
    }

    private void adjustVolume(boolean up) {
        if (am == null) return;
        am.adjustStreamVolume(AudioManager.STREAM_MUSIC,
                up ? AudioManager.ADJUST_RAISE : AudioManager.ADJUST_LOWER, 0);
        pushVolume();
    }

    private void toggleMute() {
        if (am == null) return;
        boolean muted = am.isStreamMute(AudioManager.STREAM_MUSIC);
        am.adjustStreamVolume(AudioManager.STREAM_MUSIC,
                muted ? AudioManager.ADJUST_UNMUTE : AudioManager.ADJUST_MUTE, 0);
        pushVolume();
    }

    private void pushVolume() {
        if (am == null || web == null) return;
        int cur = am.getStreamVolume(AudioManager.STREAM_MUSIC);
        int max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
        boolean muted = am.isStreamMute(AudioManager.STREAM_MUSIC);
        web.evaluateJavascript("window.onVolume&&window.onVolume(" + cur + "," + max
                + "," + muted + ")", null);
    }

    @Override
    protected void onResume() {
        super.onResume();
        hideSystemUi();
        if (web != null) web.onResume();
    }

    @Override
    protected void onPause() {
        if (web != null) web.onPause();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.loadUrl("about:blank");
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
