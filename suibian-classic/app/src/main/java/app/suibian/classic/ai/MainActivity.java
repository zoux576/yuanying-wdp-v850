package app.suibian.classic.ai;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ContentValues;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.widget.Toast;

import org.json.JSONException;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.security.KeyStore;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final String OFFICIAL_PACKAGE = "com.ss.android.spark";
    private static final int FILE_PICK_REQUEST = 1491;
    private static final String KEYSTORE_ALIAS = "classic_studio_private_api_key";
    private static final String CREDENTIALS_PREFS = "classic_studio_credentials";
    private static final int MAX_RESPONSE_BYTES = 48 * 1024 * 1024;
    private WebView webView;
    private final LinkedHashMap<String, File> mediaFiles = new LinkedHashMap<>();
    private static final String MEDIA_HOST = "appassets.androidplatform.net";
    private static final String MEDIA_PREFIX = "/classic-ai-media/";
    private static final int MAX_IMAGE_BYTES = 26 * 1024 * 1024;
    private ValueCallback<Uri[]> filePicker;
    private final ExecutorService background = Executors.newSingleThreadExecutor();

    @SuppressLint("SetJavaScriptEnabled")
    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(9, 17, 17));
        getWindow().setNavigationBarColor(Color.rgb(9, 17, 17));
        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(9, 17, 17));
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(true);
        webView.getSettings().setAllowContentAccess(true); // required for Android photo picker content:// URIs
        webView.getSettings().setAllowFileAccessFromFileURLs(false);
        webView.getSettings().setAllowUniversalAccessFromFileURLs(false);
        webView.getSettings().setJavaScriptCanOpenWindowsAutomatically(false);
        webView.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        if (Build.VERSION.SDK_INT >= 26) webView.getSettings().setSafeBrowsingEnabled(true);
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                return uri == null || !"file".equals(uri.getScheme()) || uri.getPath() == null
                        || !uri.getPath().startsWith("/android_asset/");
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (uri != null && "https".equalsIgnoreCase(uri.getScheme())
                        && MEDIA_HOST.equalsIgnoreCase(uri.getHost()) && uri.getPath() != null
                        && uri.getPath().startsWith(MEDIA_PREFIX)) {
                    String id = uri.getPath().substring(MEDIA_PREFIX.length());
                    File file;
                    synchronized (mediaFiles) { file = mediaFiles.get(id); }
                    if (file != null && file.isFile()) {
                        try { return new WebResourceResponse(sniffMime(file), null, new FileInputStream(file)); }
                        catch (Exception ignored) { }
                    }
                    return new WebResourceResponse("text/plain", "UTF-8",
                            new java.io.ByteArrayInputStream(new byte[0]));
                }
                return super.shouldInterceptRequest(view, request);
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                    FileChooserParams params) {
                if (filePicker != null) filePicker.onReceiveValue(null);
                filePicker = callback;
                Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("image/*");
                try {
                    startActivityForResult(Intent.createChooser(intent, "Choose reference image"), FILE_PICK_REQUEST);
                    return true;
                } catch (Exception ex) {
                    filePicker = null;
                    return false;
                }
            }
        });
        webView.addJavascriptInterface(new NativeBridge(), "Native");
        setContentView(webView);
        webView.loadUrl("file:///android_asset/index.html");
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_PICK_REQUEST && filePicker != null) {
            Uri[] values = resultCode == RESULT_OK && data != null && data.getData() != null
                    ? new Uri[]{data.getData()} : null;
            filePicker.onReceiveValue(values);
            filePicker = null;
        }
    }

    @Override protected void onDestroy() {
        if (filePicker != null) { filePicker.onReceiveValue(null); filePicker = null; }
        background.shutdownNow();
        if (webView != null) { webView.removeJavascriptInterface("Native"); webView.destroy(); }
        synchronized (mediaFiles) {
            for (File f : mediaFiles.values()) { if (f != null) f.delete(); }
            mediaFiles.clear();
        }
        super.onDestroy();
    }

    private void postJs(String expression) {
        runOnUiThread(() -> { if (webView != null) webView.evaluateJavascript(expression, null); });
    }

    private void postResult(JSONObject response) {
        postJs("window.classicReceive(" + JSONObject.quote(response.toString()) + ");");
    }

    private void postMessage(String message, boolean isError) {
        postJs("window.classicNativeToast(" + JSONObject.quote(message) + "," + isError + ");");
    }

    private final class NativeBridge {
        // Credentials are never placed in HTML localStorage. Android Keystore
        // encrypts the optional remembered key; by default it remains RAM-only.
        @JavascriptInterface public boolean persistKey(String key, boolean remember) {
            try {
                SharedPreferences prefs = getSharedPreferences(CREDENTIALS_PREFS, Context.MODE_PRIVATE);
                if (!remember || key == null || key.isEmpty()) {
                    return prefs.edit().remove("iv").remove("data").commit();
                }
                if (key.length() > 4096) return false;
                Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(Cipher.ENCRYPT_MODE, secureAesKey());
                byte[] ciphertext = cipher.doFinal(key.getBytes(StandardCharsets.UTF_8));
                return prefs.edit()
                        .putString("iv", android.util.Base64.encodeToString(cipher.getIV(), android.util.Base64.NO_WRAP))
                        .putString("data", android.util.Base64.encodeToString(ciphertext, android.util.Base64.NO_WRAP))
                        .commit();
            } catch (Exception ex) { return false; }
        }

        @JavascriptInterface public String restoreKey() {
            try {
                SharedPreferences prefs = getSharedPreferences(CREDENTIALS_PREFS, Context.MODE_PRIVATE);
                String iv = prefs.getString("iv", "");
                String data = prefs.getString("data", "");
                if (iv.isEmpty() || data.isEmpty()) return "";
                Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(Cipher.DECRYPT_MODE, secureAesKey(),
                        new GCMParameterSpec(128, android.util.Base64.decode(iv, android.util.Base64.NO_WRAP)));
                return new String(cipher.doFinal(android.util.Base64.decode(data, android.util.Base64.NO_WRAP)),
                        StandardCharsets.UTF_8);
            } catch (Exception ex) { return ""; }
        }

        @JavascriptInterface public void openOfficial() {
            runOnUiThread(() -> {
                try {
                    Intent launch = getPackageManager().getLaunchIntentForPackage(OFFICIAL_PACKAGE);
                    if (launch == null) {
                        Toast.makeText(MainActivity.this, "Official Suibian is not installed", Toast.LENGTH_LONG).show();
                        return;
                    }
                    launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    startActivity(launch);
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, "Cannot open official app: " + e.getMessage(), Toast.LENGTH_LONG).show();
                }
            });
        }

        @JavascriptInterface public void perform(String requestJson) {
            if (requestJson == null || requestJson.length() > 16 * 1024 * 1024) {
                postResult(error("generate", "Invalid or oversized request"));
                return;
            }
            background.execute(() -> {
                String type = "generate";
                try {
                    JSONObject input = new JSONObject(requestJson);
                    type = input.optString("type", "generate");
                    JSONObject reply = makeRequest(input);
                    reply.put("type", type);
                    reply.put("kind", input.optString("kind", "image"));
                    reply.put("requestId", input.optString("requestId", ""));
                    postResult(reply);
                } catch (Exception ex) {
                    String explanation = safeError(ex);
                    JSONObject failure;
                    try { JSONObject input = new JSONObject(requestJson);
                        String secret = input.optString("apiKey", "");
                        if (!secret.isEmpty()) explanation = explanation.replace(secret, "[redacted]");
                        failure = error(type, explanation);
                        failure.put("kind", input.optString("kind", "image"));
                        failure.put("requestId", input.optString("requestId", ""));
                    } catch (JSONException ignored) { failure = error(type, explanation); }
                    postResult(failure);
                }
            });
        }

        @JavascriptInterface public void saveImage(String uri, String filename) {
            background.execute(() -> {
                try {
                    if (uri == null || uri.isEmpty()) throw new Exception("No image to save");
                    byte[] bytes;
                    String mime = "image/png";
                    if (uri.startsWith("https://" + MEDIA_HOST + MEDIA_PREFIX)) {
                        String id = uri.substring(("https://" + MEDIA_HOST + MEDIA_PREFIX).length());
                        File local;
                        synchronized (mediaFiles) { local = mediaFiles.get(id); }
                        if (local == null || !local.isFile()) throw new Exception("Result image no longer available");
                        try (InputStream stream = new FileInputStream(local)) { bytes = readBytes(stream, MAX_IMAGE_BYTES); }
                        mime = sniffMime(bytes);
                    } else if (uri.startsWith("data:image/")) {
                        int comma = uri.indexOf(',');
                        if (comma < 0 || !uri.substring(0, comma).contains(";base64"))
                            throw new Exception("Unsupported image data");
                        if (uri.startsWith("data:image/jpeg")) mime = "image/jpeg";
                        else if (uri.startsWith("data:image/webp")) mime = "image/webp";
                        bytes = android.util.Base64.decode(uri.substring(comma + 1), android.util.Base64.DEFAULT);
                        if (bytes.length > MAX_IMAGE_BYTES) throw new Exception("Image exceeds 26 MB");
                        mime = sniffMime(bytes);
                    } else {
                        URL imageUrl = verifyHttps(uri);
                        HttpURLConnection conn = (HttpURLConnection) imageUrl.openConnection();
                        conn.setConnectTimeout(20000);
                        conn.setReadTimeout(70000);
                        conn.setInstanceFollowRedirects(false);
                        try {
                            int status = conn.getResponseCode();
                            if (status < 200 || status >= 300) throw new Exception("Image download HTTP " + status);
                            String contentType = conn.getContentType();
                            if (contentType != null && contentType.startsWith("image/")) mime = contentType.split(";")[0];
                            try (InputStream stream = conn.getInputStream()) { bytes = readBytes(stream, MAX_IMAGE_BYTES); }
                            mime = sniffMime(bytes);
                        } finally { conn.disconnect(); }
                    }
                    if (bytes.length == 0) throw new Exception("Empty image");
                    if ("application/octet-stream".equals(mime)) throw new Exception("Unsupported image content");
                    String extension = "image/jpeg".equals(mime) ? ".jpg" : "image/webp".equals(mime) ? ".webp" : ".png";
                    String base = (filename == null ? "classic-ai" : filename).replaceAll("[^A-Za-z0-9_.-]", "_");
                    if (base.length() > 64) base = base.substring(0, 64);
                    if (base.endsWith(".png") || base.endsWith(".jpg") || base.endsWith(".webp"))
                        base = base.substring(0, base.lastIndexOf('.'));
                    String name = base + extension;
                    if (Build.VERSION.SDK_INT >= 29) {
                        ContentValues values = new ContentValues();
                        values.put(MediaStore.Images.Media.DISPLAY_NAME, name);
                        values.put(MediaStore.Images.Media.MIME_TYPE, mime);
                        values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/ClassicAI");
                        values.put(MediaStore.Images.Media.IS_PENDING, 1);
                        Uri destination = getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
                        if (destination == null) throw new Exception("Cannot create gallery entry");
                        boolean succeeded = false;
                        try (OutputStream out = getContentResolver().openOutputStream(destination)) {
                            if (out == null) throw new Exception("Cannot open gallery output");
                            out.write(bytes);
                            succeeded = true;
                        } finally {
                            if (!succeeded) getContentResolver().delete(destination, null, null);
                        }
                        values.clear(); values.put(MediaStore.Images.Media.IS_PENDING, 0);
                        getContentResolver().update(destination, values, null, null);
                    } else {
                        File dir = new File(getExternalFilesDir(Environment.DIRECTORY_PICTURES), "ClassicAI");
                        if (!dir.exists() && !dir.mkdirs()) throw new Exception("Cannot create pictures folder");
                        try (FileOutputStream out = new FileOutputStream(new File(dir, name))) { out.write(bytes); }
                    }
                    postMessage("Image saved to Pictures/ClassicAI", false);
                } catch (Exception ex) { postMessage("Save failed: " + safeError(ex), true); }
            });
        }
    }

    private SecretKey secureAesKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        KeyStore.Entry entry = store.getEntry(KEYSTORE_ALIAS, null);
        if (entry instanceof KeyStore.SecretKeyEntry)
            return ((KeyStore.SecretKeyEntry) entry).getSecretKey();
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(KEYSTORE_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true).build());
        return generator.generateKey();
    }

    private JSONObject makeRequest(JSONObject input) throws Exception {
        String type = input.optString("type", "generate");
        URL url = verifyHttps(input.optString("url", ""));
        String apiKey = input.optString("apiKey", "");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setConnectTimeout(20000);
        conn.setReadTimeout(180000);
        conn.setInstanceFollowRedirects(false);
        conn.setRequestProperty("Accept", "application/json");
        if (!apiKey.isEmpty()) conn.setRequestProperty("Authorization", "Bearer " + apiKey);
        try {
            if ("test".equals(type)) {
                conn.setRequestMethod("GET");
            } else {
                String kind = input.optString("kind", "image");
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                if ("edit".equals(kind)) {
                    writeMultipart(conn, input);
                } else {
                    JSONObject data = new JSONObject();
                    data.put("model", input.optString("model"));
                    data.put("prompt", input.optString("prompt"));
                    if ("video".equals(kind)) {
                        data.put("duration", input.optInt("duration", 5));
                        data.put("aspect_ratio", input.optString("aspect_ratio", "16:9"));
                    } else {
                        data.put("size", input.optString("size", "1024x1024"));
                    }
                    byte[] body = data.toString().getBytes(StandardCharsets.UTF_8);
                    conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                    conn.setFixedLengthStreamingMode(body.length);
                    try (OutputStream out = conn.getOutputStream()) { out.write(body); }
                }
            }
            int status = conn.getResponseCode();
            try (InputStream stream = status >= 200 && status < 300 ? conn.getInputStream() : conn.getErrorStream()) {
                if (stream == null) throw new Exception("HTTP " + status + " empty response");
                byte[] body = readBytes(stream, MAX_RESPONSE_BYTES);
                String text = new String(body, StandardCharsets.UTF_8);
                if (status < 200 || status >= 300) {
                    String explanation = text.length() > 750 ? text.substring(0, 750) : text;
                    try {
                        JSONObject err = new JSONObject(text).optJSONObject("error");
                        if (err != null) explanation = err.optString("message", explanation);
                    } catch (JSONException ignored) { }
                    throw new Exception("HTTP " + status + ": " + explanation);
                }
                JSONObject result = new JSONObject(text);
                if (!"test".equals(type)) cacheInlineImages(result);
                JSONObject reply = new JSONObject();
                reply.put("ok", true); reply.put("result", result);
                return reply;
            }
        } finally { conn.disconnect(); }
    }

    // Android WebView evaluateJavascript has practical string/heap limits. Transfer large
    // generated images as app-local URLs, never as multi-MB JavaScript literals.
    private void cacheInlineImages(JSONObject result) throws Exception {
        // UI displays one result. Never leave extra base64 payloads in the JS bridge.
        JSONArray data = result.optJSONArray("data");
        if (data != null) {
            for (int i = 0; i < data.length(); i++) {
                JSONObject item = data.optJSONObject(i);
                if (item != null) {
                    if (i == 0) replaceInlineImage(item);
                    else item.remove("b64_json");
                }
            }
        }
        JSONArray images = result.optJSONArray("images");
        if (images != null) {
            for (int i = 0; i < images.length(); i++) {
                JSONObject item = images.optJSONObject(i);
                if (item != null) {
                    if (i == 0) replaceInlineImage(item);
                    else item.remove("b64_json");
                }
            }
        }
        replaceInlineImage(result);
        JSONObject output = result.optJSONObject("output");
        if (output != null) replaceInlineImage(output);
    }

    private void replaceInlineImage(JSONObject image) throws Exception {
        String encoded = image.optString("b64_json", "");
        if (encoded.isEmpty()) return;
        byte[] bytes = android.util.Base64.decode(encoded, android.util.Base64.DEFAULT);
        if (bytes.length == 0 || bytes.length > MAX_IMAGE_BYTES)
            throw new Exception("Generated image exceeds supported size");
        if ("application/octet-stream".equals(sniffMime(bytes)))
            throw new Exception("Unsupported image format from provider");
        String id = UUID.randomUUID().toString() + ".img";
        File local = new File(getCacheDir(), "classic-result-" + id);
        try (FileOutputStream out = new FileOutputStream(local)) { out.write(bytes); }
        synchronized (mediaFiles) {
            mediaFiles.put(id, local);
            while (mediaFiles.size() > 3) {
                Map.Entry<String, File> oldest = mediaFiles.entrySet().iterator().next();
                if (oldest.getValue() != null) oldest.getValue().delete();
                mediaFiles.remove(oldest.getKey());
            }
        }
        image.remove("b64_json");
        image.put("url", "https://" + MEDIA_HOST + MEDIA_PREFIX + id);
    }

    private static String sniffMime(File file) throws Exception {
        try (InputStream in = new FileInputStream(file)) {
            byte[] bytes = new byte[12];
            int count = in.read(bytes);
            if (count < 4) return "image/png";
            return sniffMime(bytes);
        }
    }

    private static String sniffMime(byte[] bytes) {
        if (bytes.length >= 3 && (bytes[0] & 255) == 0xFF && (bytes[1] & 255) == 0xD8 && (bytes[2] & 255) == 0xFF)
            return "image/jpeg";
        if (bytes.length >= 12 && bytes[0]=='R' && bytes[1]=='I' && bytes[2]=='F' && bytes[3]=='F'
                && bytes[8]=='W' && bytes[9]=='E' && bytes[10]=='B' && bytes[11]=='P')
            return "image/webp";
        if (bytes.length >= 8 && (bytes[0] & 255)==0x89 && bytes[1]=='P' && bytes[2]=='N'
                && bytes[3]=='G' && bytes[4]==0x0D && bytes[5]==0x0A) return "image/png";
        return "application/octet-stream";
    }

    private static void writeMultipart(HttpURLConnection conn, JSONObject input) throws Exception {
        String dataUrl = input.optString("imageData", "");
        int comma = dataUrl.indexOf(',');
        if (comma < 0 || !dataUrl.substring(0, comma).startsWith("data:image/")
                || !dataUrl.substring(0, comma).contains(";base64"))
            throw new Exception("Missing or invalid reference image");
        byte[] image = android.util.Base64.decode(dataUrl.substring(comma + 1), android.util.Base64.DEFAULT);
        if (image.length > 8 * 1024 * 1024) throw new Exception("Compressed image exceeds 8 MB");
        String boundary = "----ClassicAI" + UUID.randomUUID().toString().replace("-", "");
        conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
        try (DataOutputStream out = new DataOutputStream(conn.getOutputStream())) {
            part(out, boundary, "model", input.optString("model", ""));
            part(out, boundary, "prompt", input.optString("prompt", ""));
            part(out, boundary, "size", input.optString("size", "1024x1024"));
            out.writeBytes("--" + boundary + "\r\n");
            out.writeBytes("Content-Disposition: form-data; name=\"image\"; filename=\"reference.jpg\"\r\n");
            out.writeBytes("Content-Type: image/jpeg\r\n\r\n");
            out.write(image); out.writeBytes("\r\n--" + boundary + "--\r\n");
        }
    }

    private static void part(DataOutputStream out, String boundary, String name, String value) throws Exception {
        out.writeBytes("--" + boundary + "\r\nContent-Disposition: form-data; name=\"" + name + "\"\r\n\r\n");
        out.write(value.getBytes(StandardCharsets.UTF_8));
        out.writeBytes("\r\n");
    }

    private static URL verifyHttps(String value) throws Exception {
        if (value == null || value.length() > 2000 || value.contains("\r") || value.contains("\n"))
            throw new Exception("Invalid API URL");
        URL url = new URL(value);
        if (!"https".equalsIgnoreCase(url.getProtocol()) || url.getHost().isEmpty() || url.getUserInfo() != null)
            throw new Exception("HTTPS API URL required");
        return url;
    }

    private static byte[] readBytes(InputStream in, int max) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] block = new byte[32768]; int count; int total = 0;
        while ((count = in.read(block)) != -1) {
            total += count;
            if (total > max) throw new Exception("Response exceeds allowed size");
            out.write(block, 0, count);
        }
        return out.toByteArray();
    }

    private static JSONObject error(String type, String message) {
        JSONObject object = new JSONObject();
        try { object.put("ok", false).put("type", type).put("error", message); }
        catch (JSONException ignored) { }
        return object;
    }

    private static String safeError(Exception ex) {
        String message = ex.getMessage();
        if (message == null) message = ex.getClass().getSimpleName();
        return message.length() > 750 ? message.substring(0, 750) : message;
    }
}
