package com.example.scanner

import android.Manifest
import android.annotation.SuppressLint
import android.content.pm.PackageManager
import android.os.Bundle
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : ComponentActivity() {

    private val CAMERA_PERMISSION_CODE = 100
    private lateinit var webView: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        webView = WebView(this)
        setContentView(webView)

        val webSettings: WebSettings = webView.settings
        webSettings.javaScriptEnabled = true
        webSettings.domStorageEnabled = true
        webSettings.mediaPlaybackRequiresUserGesture = false
        
        // Autoriser l'accès aux fichiers locaux (nécessaire pour la caméra sur file://)
        webSettings.allowFileAccess = true
        webSettings.allowContentAccess = true
        try {
            webSettings.allowFileAccessFromFileURLs = true
            webSettings.allowUniversalAccessFromFileURLs = true
        } catch (e: Exception) {}

        webView.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                // On accorde automatiquement l'accès vidéo à la WebView
                if (request.resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE)) {
                    request.grant(request.resources)
                } else {
                    super.onPermissionRequest(request)
                }
            }
        }
        
        webView.webViewClient = WebViewClient()

        // Vérifier les permissions Android natives avant de charger la page
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), CAMERA_PERMISSION_CODE)
        } else {
            // Si on a déjà la permission, on charge
            webView.loadUrl("file:///android_asset/index.html")
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == CAMERA_PERMISSION_CODE) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                // Dès que l'utilisateur accepte, on charge la page web qui va utiliser la caméra
                webView.loadUrl("file:///android_asset/index.html")
            } else {
                // Refusé... on peut charger quand même, mais la caméra marchera pas
                webView.loadUrl("file:///android_asset/index.html")
            }
        }
    }
}
